"""
Network discovery: which devices answer ARP inside each watched network.

ARP is the one thing every IPv4 device on the LAN must answer, firewalls
included, and the reply carries the MAC, which is what identifies a device
(its IP changes whenever DHCP feels like it). Needs raw sockets, so the
container runs with network_mode: host (or attached to a macvlan per VLAN).

ARP does not cross routers: a network is only visible from an interface that
sits on it. Each network is swept through the interface its addresses route
to, so one container watches as many VLANs as it has legs in.

The routing table only picks the interface, it never rules addresses out:
scapy reads the local and main tables alone, so on hosts with policy routing
the LAN itself looks reachable only through the router. Whether a network is
really out of reach is decided by nobody answering.

A network nobody answers on, behind a router, is pinged instead (as 1.x did):
the kernel sends the echoes, routing with every table, and the router forwards
them. No MAC comes back across a router, so those devices are identified by
their IP, and the ones that ignore ping (phones asleep, firewalls) stay unseen.
The same happens when the interface the routing table picks does not exist.
"""

import errno
import random
import select
import socket
import struct
import time
from concurrent.futures import ThreadPoolExecutor, wait
from ipaddress import ip_address, ip_network

from config import ARP_RETRIES, ARP_TIMEOUT, HOSTNAME_LOOKUP_TIMEOUT, MAX_SCAN_ADDRESSES
from logger import debug, warning

# scapy prints its own warnings (missing IPv6 routes and the like) on import
import logging
logging.getLogger("scapy.runtime").setLevel(logging.ERROR)
from scapy.all import ARP, Ether, conf, srp  # noqa: E402


class RangeError(ValueError):
	pass


class NetworksError(ValueError):
	pass


class NotConnectedError(Exception):
	"""No address of the network is on a link of this host: they are only
	reachable through a router, which answers ARP for none of them, and none
	answers ping either"""
	def __init__(self, gateway):
		super().__init__(f"reachable only through the router {gateway}")
		self.gateway = gateway


class Network:
	def __init__(self, index, name, range_text, addresses, interface=None):
		self.index = index  # Position in the configuration, used in callback_data
		self.name = name
		self.range_text = range_text
		self.addresses = addresses
		self.address_set = set(addresses)
		self.interface = interface


def parse_ip_range(text):
	"""Sorted list of the IPv4 addresses in a range. Accepts comma separated
	blocks, each one a range (192.168.1.1-192.168.1.254), a network in CIDR
	notation (192.168.1.0/24) or a single address. Raises RangeError with the
	offending block when one cannot be understood"""
	if not text or not text.strip():
		raise RangeError("")
	addresses = set()
	for block in text.split(","):
		block = block.strip()
		if not block:
			continue
		try:
			if "-" in block:
				start_text, end_text = (part.strip() for part in block.split("-", 1))
				start, end = ip_address(start_text), ip_address(end_text)
				if start.version != 4 or end.version != 4 or end < start:
					raise ValueError
				if int(end) - int(start) + 1 > MAX_SCAN_ADDRESSES:
					raise RangeError(block)
				addresses.update(ip_address(i) for i in range(int(start), int(end) + 1))
			elif "/" in block:
				network = ip_network(block, strict=False)
				if network.version != 4 or network.num_addresses > MAX_SCAN_ADDRESSES:
					raise ValueError
				# hosts() leaves out the network and broadcast addresses
				addresses.update(network.hosts())
			else:
				address = ip_address(block)
				if address.version != 4:
					raise ValueError
				addresses.add(address)
		except ValueError:
			raise RangeError(block)
		if len(addresses) > MAX_SCAN_ADDRESSES:
			raise RangeError(block)
	if not addresses:
		raise RangeError(text)
	return [str(address) for address in sorted(addresses)]


def parse_networks(networks_text, ip_range_text, interface, default_name):
	"""Watched networks. NETWORKS holds 'name=range[@interface]' entries
	separated by ';'. Without it, IP_RANGE (and NETWORK_INTERFACE) make a single
	network called default_name, as in the versions before VLAN support.
	Raises NetworksError or RangeError explaining what is wrong"""
	if not networks_text or not networks_text.strip():
		if not ip_range_text or not ip_range_text.strip():
			raise NetworksError("missing")
		return [Network(0, default_name, ip_range_text.strip(), parse_ip_range(ip_range_text), interface or None)]

	networks = []
	seen = {}
	total = 0
	for entry in networks_text.split(";"):
		entry = entry.strip()
		if not entry:
			continue
		if "=" not in entry:
			raise NetworksError(f"'{entry}' has no name")
		name, spec = (part.strip() for part in entry.split("=", 1))
		if not name:
			raise NetworksError(f"'{entry}' has an empty name")
		if name.lower() in (n.name.lower() for n in networks):
			raise NetworksError(f"the name '{name}' is used twice")
		entry_interface = None
		if "@" in spec:
			spec, entry_interface = (part.strip() for part in spec.rsplit("@", 1))
			if not entry_interface:
				raise NetworksError(f"'{entry}' has an empty interface after @")
		addresses = parse_ip_range(spec)
		for address in addresses:
			if address in seen:
				raise NetworksError(f"{address} is in both '{seen[address]}' and '{name}'")
			seen[address] = name
		total += len(addresses)
		if total > MAX_SCAN_ADDRESSES:
			raise NetworksError(f"the networks add up to more than {MAX_SCAN_ADDRESSES} addresses")
		networks.append(Network(len(networks), name, spec, addresses, entry_interface))
	if not networks:
		raise NetworksError("missing")
	return networks


def is_mac(device_id):
	"""Devices found by ping are identified by their IP instead of a MAC"""
	return ":" in device_id


def is_random_mac(mac):
	"""Locally administered MAC: phones and laptops make one up per network
	(private Wi-Fi address), so the vendor cannot be known from it"""
	try:
		return bool(int(mac.split(":")[0], 16) & 0x02)
	except (ValueError, IndexError):
		return False


def get_vendor(mac):
	"""Manufacturer registered for the MAC prefix, None when unknown"""
	if not is_mac(mac) or is_random_mac(mac):
		return None
	try:
		_, vendor = conf.manufdb.lookup(mac)
	except Exception:
		return None
	if not vendor or vendor.lower() == mac.lower():
		return None
	return vendor


def _hostname(ip):
	try:
		name = socket.gethostbyaddr(ip)[0]
	except (OSError, UnicodeError):
		return None
	return name if name and name != ip else None


def resolve_hostnames(ips):
	"""Reverse DNS for every address, in parallel and bounded in time:
	gethostbyaddr has no timeout of its own and a router without PTR records
	can keep each lookup hanging for seconds. Lookups still pending when the
	time is up are left behind"""
	if not ips:
		return {}
	executor = ThreadPoolExecutor(max_workers=min(32, len(ips)))
	futures = {executor.submit(_hostname, ip): ip for ip in ips}
	done, _ = wait(futures, timeout=HOSTNAME_LOOKUP_TIMEOUT)
	executor.shutdown(wait=False, cancel_futures=True)
	return {futures[future]: future.result() for future in done if future.result()}


def group_by_interface(network):
	"""{interface: addresses} to sweep, plus the addresses whose route goes
	through a router (with the first such router). Those are swept anyway
	through that route's interface, see the module docstring. The addresses of
	this machine are left out: it never answers its own ARP. An interface set
	in the configuration is trusted as is: it may be a VLAN leg with no IP of
	its own, which the routing table knows nothing about"""
	if network.interface:
		return {network.interface: network.addresses}, [], None
	conf.route.resync()  # Interfaces may have come up after the bot started
	groups = {}
	routed = []
	gateway = None
	for address in network.addresses:
		interface, source, route_gateway = conf.route.route(address)
		if interface == conf.loopback_name or address == source:
			continue
		if route_gateway != "0.0.0.0":
			routed.append(address)
			gateway = gateway or route_gateway
		groups.setdefault(interface, []).append(address)
	return groups, routed, gateway


def _sweep(addresses, interface):
	answered, _ = srp(Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=addresses), iface=interface,
					timeout=ARP_TIMEOUT, retry=ARP_RETRIES, verbose=False)
	return [(reply[ARP].hwsrc.lower(), reply[ARP].psrc) for _, reply in answered]


def _checksum(data):
	if len(data) % 2:
		data += b"\0"
	total = sum(struct.unpack(f"!{len(data) // 2}H", data))
	total = (total >> 16) + (total & 0xFFFF)
	total += total >> 16
	return ~total & 0xFFFF


def _collect_echo_replies(sock, ident, addresses, alive, deadline):
	"""Reads replies to our echoes until the deadline. A raw ICMP socket gets
	every ICMP packet the host receives: ident tells ours apart, and the source
	keeps each network to its own addresses when several are pinged at once"""
	while True:
		remaining = deadline - time.monotonic()
		if not select.select([sock], [], [], max(0, remaining))[0]:
			if remaining <= 0:
				return
			continue
		packet, (source, _) = sock.recvfrom(1024)
		header_length = (packet[0] & 0x0F) * 4
		if len(packet) < header_length + 8:
			continue
		icmp_type, _, _, reply_ident, _ = struct.unpack("!BBHHH", packet[header_length:header_length + 8])
		if icmp_type == 0 and reply_ident == ident and source in addresses:
			alive.add(source)


def _ping_sweep(addresses):
	"""Addresses answering an ICMP echo, all pinged at once with the same
	timeout and retries as ARP"""
	address_set = set(addresses)
	ident = random.getrandbits(16)
	alive = set()
	with socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP) as sock:
		for _ in range(ARP_RETRIES + 1):
			pending = [address for address in addresses if address not in alive]
			if not pending:
				break
			for sequence, address in enumerate(pending):
				header = struct.pack("!BBHHH", 8, 0, 0, ident, sequence & 0xFFFF)
				packet = struct.pack("!BBHHH", 8, 0, _checksum(header), ident, sequence & 0xFFFF)
				try:
					sock.sendto(packet, (address, 0))
				except PermissionError:
					raise
				except OSError:
					pass  # No route or host unreachable: it just does not answer
				_collect_echo_replies(sock, ident, address_set, alive, time.monotonic())
			_collect_echo_replies(sock, ident, address_set, alive, time.monotonic() + ARP_TIMEOUT)
	return [address for address in addresses if address in alive]


def arp_scan(network):
	"""{device id: ip} of every address of the network that answers, the id
	being its MAC or, for networks behind a router, its IP (see the module
	docstring). Raises NotConnectedError when nothing answers and every address
	routes through a router, PermissionError without raw socket access and
	ValueError/OSError when the configured interface does not exist"""
	groups, routed, gateway = group_by_interface(network)
	swept = sum(len(addresses) for addresses in groups.values())
	found = {}
	interface_error = None
	for interface, addresses in groups.items():
		try:
			replies = _sweep(addresses, interface)
		except OSError as e:
			# The error alone ("No such device") does not say which interface
			warning(f"Cannot sweep {network.name} through {interface}: {e}")
			if network.interface or e.errno != errno.ENODEV:
				raise
			interface_error = e
			continue
		for mac, ip in replies:
			# A reply from outside the range: a device answering for an address
			# it does not own (proxy ARP)
			if ip not in network.address_set:
				continue
			if mac in found and found[mac] != ip:
				# One MAC answering for several addresses: a router doing proxy
				# ARP or a host with aliases. Keep the first one, the rest is noise
				warning(f"{mac} answers for {found[mac]} and {ip} in {network.name}")
				continue
			found[mac] = ip
	if found or not (interface_error or (routed and len(routed) == swept)):
		return found
	addresses = [address for group in groups.values() for address in group]
	alive = _ping_sweep(addresses)
	if not alive:
		raise interface_error or NotConnectedError(gateway)
	debug(f"{network.name} does not answer ARP, {len(alive)} addresses answered ping")
	return {ip: ip for ip in alive}
