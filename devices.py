"""
Known devices, persisted in DATA_PATH/devices.json.

A device is a MAC inside a watched network. 1.x keyed them by IP, which broke
as soon as DHCP handed an address to a different device: the newcomer went
unnoticed and the old one was reported as new. The network is part of the key
because routers and switches answer with the same MAC on every VLAN, and
because a known laptop showing up in the IoT VLAN is news worth reporting.
The 1.x file is migrated here (see _load_legacy).

On networks behind a router no MAC is visible and the scanner finds devices
by ping: their "mac" holds their IP instead (see scanner.is_mac). When the
same network is later seen with ARP, or the other way round, a device is
matched by its IP so it keeps its name and is not reported again.
"""

import copy
import json
import os
import threading
import time
from ipaddress import ip_address

from config import DATA_PATH, DEVICES_FILE, LEGACY_DEVICES_FILE, MAX_NAME_LENGTH
from logger import debug, error, warning
from scanner import is_mac

DEVICES_PATH = os.path.join(DATA_PATH, DEVICES_FILE)
LEGACY_PATH = os.path.join(DATA_PATH, LEGACY_DEVICES_FILE)

# Names 1.x stored when the device had no hostname
LEGACY_UNKNOWN_NAMES = ("desconocido", "unknown")

_lock = threading.Lock()
_devices = {}  # "network|mac" -> device dict
_networks = {}  # network name -> {"last_scan": epoch or None, "muted": bool}
_legacy = {}  # ip -> name ("" when it had none), 1.x devices not matched to a MAC yet

# Problem found while loading, reported to the admin once the bot is up
load_problem = None


def _key(network, mac):
	return f"{network}|{mac}"


def _ip_sort_key(device):
	try:
		return int(ip_address(device.get("ip") or "0.0.0.0"))
	except ValueError:
		return 0


def _network_state(name):
	return _networks.setdefault(name, {"last_scan": None, "muted": False})


def _save():
	"""Writes the file atomically, so a crash mid-write never leaves it half done"""
	try:
		os.makedirs(DATA_PATH, exist_ok=True)
		tmp_path = DEVICES_PATH + ".tmp"
		with open(tmp_path, "w", encoding="utf-8") as file:
			json.dump({"version": 2, "networks": _networks, "devices": _devices, "legacy": _legacy}, file, indent=4, ensure_ascii=False)
		os.replace(tmp_path, DEVICES_PATH)
	except Exception as e:
		error(f"Cannot write {DEVICES_PATH}: {e}")


def _load_legacy():
	"""IP -> name map from 1.x. Every address is kept, so the devices it already
	knew are not reported as new, but 'unknown' is not worth keeping as a name"""
	with open(LEGACY_PATH, "r", encoding="utf-8") as file:
		data = json.load(file)
	if not isinstance(data, dict):
		raise ValueError("not a JSON object")
	return {str(ip): "" if str(name).strip().lower() in LEGACY_UNKNOWN_NAMES else str(name).strip() for ip, name in data.items()}


def _adopt_orphans(networks):
	"""Devices of a network no longer configured (renamed, or IP_RANGE turned
	into NETWORKS) move to the configured network holding their IP, so they
	keep their name and are not reported again. The ones that fit nowhere stay
	in the file, out of sight, in case the network comes back"""
	names = {network.name for network in networks}
	moved = 0
	for key, device in list(_devices.items()):
		if device["network"] in names:
			continue
		target = next((n for n in networks if device.get("ip") in n.address_set), None)
		if target is None or _key(target.name, device["mac"]) in _devices:
			continue
		old_state = _networks.get(device["network"], {})
		del _devices[key]
		device["network"] = target.name
		_devices[_key(target.name, device["mac"])] = device
		state = _network_state(target.name)
		state["last_scan"] = state["last_scan"] or old_state.get("last_scan")
		moved += 1
	if moved:
		debug(f"{moved} devices moved to the network holding their IP")
		_save()


def load(networks):
	"""Reads the devices file. A file that cannot be parsed is moved aside
	instead of being overwritten, and the bot starts from scratch"""
	global _devices, _networks, _legacy, load_problem
	with _lock:
		if os.path.exists(DEVICES_PATH):
			try:
				with open(DEVICES_PATH, "r", encoding="utf-8") as file:
					data = json.load(file)
				_devices = {_key(d["network"], d["mac"].lower()): d for d in data.get("devices", {}).values()}
				_networks = data.get("networks", {}) or {}
				_legacy = data.get("legacy", {}) or {}
				debug(f"Loaded {len(_devices)} known devices")
			except Exception as e:
				_devices, _networks, _legacy = {}, {}, {}
				backup = f"{DEVICES_PATH}.broken-{int(time.time())}"
				try:
					os.replace(DEVICES_PATH, backup)
				except OSError:
					backup = DEVICES_PATH
				error(f"Cannot read {DEVICES_PATH} ({e}), starting with no devices. The file was kept as {backup}")
				load_problem = ("broken", backup)
			_adopt_orphans(networks)
			return

		if os.path.exists(LEGACY_PATH):
			try:
				_legacy = _load_legacy()
				os.replace(LEGACY_PATH, LEGACY_PATH + ".bak")
				_save()
				debug(f"Migrated {len(_legacy)} devices from {LEGACY_PATH}")
				load_problem = ("migrated", len(_legacy))
			except Exception as e:
				warning(f"Cannot migrate {LEGACY_PATH}: {e}")


def is_first_scan(network):
	"""True until a scan of the network has registered something: the first
	sweep records it silently instead of reporting each device. A network with
	1.x addresses pending is not new, those devices were already known"""
	with _lock:
		if _network_state(network.name)["last_scan"] is not None:
			return False
		if any(d["network"] == network.name for d in _devices.values()):
			return False
		return not any(ip in network.address_set for ip in _legacy)


def last_scan(network_name=None):
	"""Epoch of the last scan of a network, or of any network"""
	with _lock:
		if network_name is not None:
			return _network_state(network_name)["last_scan"]
		scans = [state["last_scan"] for state in _networks.values() if state.get("last_scan")]
		return max(scans) if scans else None


def is_muted(network_name):
	with _lock:
		return bool(_network_state(network_name)["muted"])


def toggle_muted(network_name):
	with _lock:
		state = _network_state(network_name)
		state["muted"] = not state["muted"]
		_save()
		return state["muted"]


def _same_ip_other_kind(network_name, device_id, ip):
	"""Known device of the network at that IP identified the other way (MAC
	when device_id is an IP, and vice versa)"""
	for device in _devices.values():
		if device["network"] == network_name and device.get("ip") == ip and is_mac(device["mac"]) != is_mac(device_id):
			return device
	return None


def apply_scan(network_name, found, hostnames, vendor_of):
	"""Updates the known devices of a network with a scan result ({mac: ip})
	and returns the devices seen for the first time. The ones matching a 1.x
	entry by IP get its name and are not reported as new, and so do the ones
	matching by IP a device known the other way (ping or ARP)"""
	now = int(time.time())
	new_devices = []
	with _lock:
		for device in _devices.values():
			if device["network"] == network_name:
				device["online"] = False
		for mac, ip in found.items():
			device = _devices.get(_key(network_name, mac))
			if device is None:
				known = _same_ip_other_kind(network_name, mac, ip)
				if known is not None and not is_mac(mac):
					# Seen by ping now: the device known by its MAC is still the best record
					device = known
				elif known is not None:
					# Its MAC is visible at last: it replaces the record keyed by its IP
					del _devices[_key(network_name, known["mac"])]
					known["mac"] = mac
					known["vendor"] = vendor_of(mac)
					_devices[_key(network_name, mac)] = known
					device = known
			if device is None:
				legacy_name = _legacy.pop(ip, None)
				device = {
					"network": network_name,
					"mac": mac,
					"ip": ip,
					"name": (legacy_name or "")[:MAX_NAME_LENGTH],
					"hostname": None,
					"vendor": vendor_of(mac),
					"first_seen": now,
				}
				_devices[_key(network_name, mac)] = device
				if legacy_name is None:
					new_devices.append(device)
			elif device.get("ip") != ip:
				debug(f"{mac} moved from {device.get('ip')} to {ip} in {network_name}")
				device["ip"] = ip
			if hostnames.get(ip):
				device["hostname"] = hostnames[ip]
			device["last_seen"] = now
			device["online"] = True
		_network_state(network_name)["last_scan"] = now
		_save()
		return [copy.deepcopy(device) for device in new_devices]


def get(network_name, mac):
	with _lock:
		device = _devices.get(_key(network_name, mac))
		return copy.deepcopy(device) if device else None


def get_all(network_names):
	"""Every known device of the given networks, sorted by IP"""
	with _lock:
		chosen = [d for d in _devices.values() if d["network"] in network_names]
		return sorted((copy.deepcopy(d) for d in chosen), key=_ip_sort_key)


def rename(network_name, mac, name):
	with _lock:
		device = _devices.get(_key(network_name, mac))
		if device is None:
			return False
		device["name"] = name.strip()[:MAX_NAME_LENGTH]
		_save()
		return True


def forget(network_name, mac):
	"""Removes a device: if it is still connected, the next scan reports it again"""
	with _lock:
		if _devices.pop(_key(network_name, mac), None) is None:
			return False
		_save()
		return True


def forget_all(networks):
	"""Clears the devices of the given networks. Their next scan registers them
	silently again, as on a fresh install"""
	with _lock:
		names = {network.name for network in networks}
		keys = [key for key, device in _devices.items() if device["network"] in names]
		for key in keys:
			del _devices[key]
		for ip in [ip for ip in _legacy if any(ip in network.address_set for network in networks)]:
			del _legacy[ip]
		for name in names:
			_network_state(name)["last_scan"] = None
		_save()
		return len(keys)
