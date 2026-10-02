import html
import json
import math
import os
import requests
import sys
import telebot
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from config import *
from datetime import datetime
from telebot.types import ForceReply
from telebot.types import InlineKeyboardButton
from telebot.types import InlineKeyboardMarkup
from logger import debug, error, warning
from message_queue import MessageQueue, describe_error
import devices
import scanner

if LANGUAGE.lower() not in ("es", "en"):
	error("LANGUAGE only can be ES/EN")
	sys.exit(1)

# MODULO DE TRADUCCIONES
_locale_cache = {}

def load_locale(locale):
	"""Load locale with caching to avoid repeated file I/O"""
	if locale not in _locale_cache:
		with open(f"{LOCALE_PATH}/{locale}.json", "r", encoding="utf-8") as file:
			_locale_cache[locale] = json.load(file)
	return _locale_cache[locale]

def get_text(key, *args):
	"""Get translated text with caching"""
	messages = load_locale(LANGUAGE.lower())
	if key in messages:
		translated_text = messages[key]
	else:
		messages_en = load_locale("en")
		if key in messages_en:
			warning(f"key ['{key}'] is not in locale {LANGUAGE}")
			translated_text = messages_en[key]
		else:
			error(f"key ['{key}'] is not in locale {LANGUAGE} or EN")
			return f"key ['{key}'] is not in locale {LANGUAGE} or EN"

	if args:
		for i, arg in enumerate(args, start=1):
			translated_text = translated_text.replace(f"${i}", str(arg))

	return translated_text


# Initial variable validation
if not TELEGRAM_TOKEN:
	error("You need to configure the bot token with the TELEGRAM_TOKEN variable")
	sys.exit(1)
if not TELEGRAM_ADMIN:
	error("You need to configure the chatId of the user who will interact with the bot with the TELEGRAM_ADMIN variable")
	sys.exit(1)
if str(ANONYMOUS_USER_ID) in str(TELEGRAM_ADMIN).split(','):
	error("You cannot be anonymous to control the bot. In the variable TELEGRAM_ADMIN you have to put your user id.")
	sys.exit(1)
if not TELEGRAM_GROUP:
	if len(str(TELEGRAM_ADMIN).split(',')) > 1:
		error("Multiple administrators can only be specified if used in a group (using the TELEGRAM_GROUP variable)")
		sys.exit(1)

try:
	TELEGRAM_THREAD = int(str(TELEGRAM_THREAD).strip()) if str(TELEGRAM_THREAD).strip() else 1
except ValueError:
	error(f"The variable TELEGRAM_THREAD is the thread within a supergroup, it is a numeric value. It has been set to {TELEGRAM_THREAD}.")
	sys.exit(1)

try:
	SCAN_INTERVAL_SECONDS = round(float(str(HOURS_BETWEEN_SCANS).replace(",", ".")) * 3600)
	if SCAN_INTERVAL_SECONDS < 60:
		raise ValueError
except ValueError:
	error(f"The variable HOURS_BETWEEN_SCANS must be a number of hours of at least one minute (0.02), for example 1 or 0.5. It has been set to {HOURS_BETWEEN_SCANS}.")
	sys.exit(1)

if NETWORKS and NETWORKS.strip() and IP_RANGE and IP_RANGE.strip():
	warning("Both NETWORKS and IP_RANGE are set: IP_RANGE (and NETWORK_INTERFACE) are ignored")
try:
	WATCHED_NETWORKS = scanner.parse_networks(NETWORKS, IP_RANGE, NETWORK_INTERFACE, get_text("DEFAULT_NETWORK_NAME"))
except scanner.RangeError as e:
	error(f"The network range is not valid near '{e}'. Use ranges (192.168.1.1-192.168.1.254), networks (192.168.1.0/24) or single addresses, separated by commas, up to {MAX_SCAN_ADDRESSES} addresses in total.")
	sys.exit(1)
except scanner.NetworksError as e:
	if str(e) == "missing":
		error("You need to configure the addresses to watch with the IP_RANGE variable (for example 192.168.1.0/24) or, for several networks/VLANs, with NETWORKS (for example Casa=192.168.1.0/24; IoT=192.168.20.0/24)")
	else:
		error(f"The variable NETWORKS is not valid: {e}. Write it as name=range[@interface] entries separated by ';', for example Casa=192.168.1.0/24; IoT=192.168.20.0/24@eth0.20")
	sys.exit(1)

MULTI_NETWORK = len(WATCHED_NETWORKS) > 1
ALL_NETWORKS = "a"  # Network filter code for "every network" in callback_data
ADMIN_IDS = [x.strip() for x in str(TELEGRAM_ADMIN).split(',')]

bot = telebot.TeleBot(TELEGRAM_TOKEN)
message_queue = MessageQueue(delay_between_messages=0.3)
devices.load(WATCHED_NETWORKS)


# ---------------------------------------------------------------------------
# GENERIC HELPERS
# ---------------------------------------------------------------------------

def build_call(command, *args):
	call = "|".join([command] + [str(a) for a in args])
	# Telegram rejects the whole keyboard with BUTTON_DATA_INVALID over 64 bytes
	size = len(call.encode("utf-8"))
	if size > MAX_CALLBACK_DATA_BYTES:
		warning(f"callback_data too long ({size} bytes), Telegram will reject the keyboard: {call}")
	return call


def mac_id(mac):
	"""MAC without separators, to keep callback_data short"""
	return mac.replace(":", "")


def mac_from_id(mac_short):
	return ":".join(mac_short[i:i + 2] for i in range(0, len(mac_short), 2))


def network_by_index(index):
	"""Configured network from its position, None when the configuration
	changed since the button was sent"""
	try:
		return WATCHED_NETWORKS[int(index)]
	except (ValueError, IndexError):
		return None


def network_by_name(name):
	return next((n for n in WATCHED_NETWORKS if n.name == name), None)


def filtered_networks(network_filter):
	"""Networks a list screen shows: all of them or the one in the filter"""
	if network_filter == ALL_NETWORKS:
		return WATCHED_NETWORKS
	network = network_by_index(network_filter)
	return [network] if network else []


def network_names(networks):
	return {network.name for network in networks}


def truncate(text, length=MAX_NAME_LENGTH_IN_BUTTON):
	return text if len(text) <= length else text[:length - 1] + "…"


def is_authorized(user_id, chat_id):
	if str(user_id) not in ADMIN_IDS:
		return False
	if TELEGRAM_GROUP and str(chat_id) != str(TELEGRAM_GROUP) and str(chat_id) not in ADMIN_IDS:
		return False
	return True


def normalize_thread(thread_id):
	"""Telegram addresses the General topic of a forum by omitting the thread,
	so both it (thread 1) and a chat without topics normalize to None"""
	try:
		thread_id = int(thread_id)
	except (TypeError, ValueError):
		return None
	return thread_id if thread_id > 1 else None


def send_message(chat_id, text, reply_markup=None, thread_id=None):
	kwargs = {"parse_mode": "HTML", "reply_markup": reply_markup, "disable_web_page_preview": True}
	thread_id = normalize_thread(thread_id)
	if thread_id:
		kwargs["message_thread_id"] = thread_id
	return message_queue.enqueue_and_wait(bot.send_message, chat_id, text, **kwargs)


def edit_message(chat_id, message_id, text, reply_markup=None):
	try:
		return bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML", reply_markup=reply_markup, disable_web_page_preview=True)
	except Exception as e:
		if "message is not modified" not in str(e):
			warning(f"Cannot edit message {message_id}: {describe_error(e)}")
		return None


def delete_message(chat_id, message_id):
	try:
		bot.delete_message(chat_id, message_id)
	except Exception:
		pass


def notify(text, reply_markup=None):
	"""Sends a bot-initiated notification to the configured destination: the
	group (and its TELEGRAM_THREAD) if set, or the admin"""
	target = TELEGRAM_GROUP if TELEGRAM_GROUP else ADMIN_IDS[0]
	send_message(target, text, reply_markup=reply_markup, thread_id=TELEGRAM_THREAD)


def format_datetime(timestamp):
	if not timestamp:
		return "-"
	return datetime.fromtimestamp(timestamp).strftime(get_text("DATETIME_FORMAT"))


def format_time(timestamp):
	if not timestamp:
		return "-"
	moment = datetime.fromtimestamp(timestamp)
	if moment.date() == datetime.now().date():
		return moment.strftime("%H:%M")
	return moment.strftime(get_text("DATETIME_FORMAT"))


def format_ago(timestamp):
	if not timestamp:
		return "-"
	seconds = max(0, int(time.time() - timestamp))
	if seconds < 60:
		return get_text("AGO_NOW")
	if seconds < 3600:
		return get_text("AGO_MINUTES", seconds // 60)
	if seconds < 86400:
		return get_text("AGO_HOURS", seconds // 3600)
	return get_text("AGO_DAYS", seconds // 86400)


def format_interval(seconds):
	hours, minutes = divmod(round(seconds / 60), 60)
	if hours and minutes:
		return f"{hours} h {minutes} min"
	if hours:
		return f"{hours} h"
	return f"{minutes} min"


def network_label(network):
	"""How messages refer to a network: by name only when there are several"""
	if MULTI_NETWORK:
		return get_text("NETWORK_LABEL", html.escape(network.name))
	return get_text("NETWORK_LABEL_SINGLE")


def display_name(device):
	"""What the user calls the device: their name, else what the network says"""
	return device.get("name") or device.get("hostname") or device.get("vendor") or get_text("UNKNOWN_DEVICE")


def device_lines(device):
	"""Common detail lines (network, IP, MAC, vendor, hostname) of a device, as HTML"""
	lines = []
	if MULTI_NETWORK:
		lines.append(get_text("DEVICE_NETWORK", html.escape(device["network"])))
	lines.append(get_text("DEVICE_IP", html.escape(device["ip"])))
	mac_line = get_text("DEVICE_MAC", html.escape(device["mac"]))
	if scanner.is_random_mac(device["mac"]):
		mac_line += f" {get_text('DEVICE_MAC_RANDOM')}"
	lines.append(mac_line)
	if device.get("vendor"):
		lines.append(get_text("DEVICE_VENDOR", html.escape(device["vendor"])))
	if device.get("hostname"):
		lines.append(get_text("DEVICE_HOSTNAME", html.escape(device["hostname"])))
	return lines


def close_markup():
	markup = InlineKeyboardMarkup()
	markup.add(InlineKeyboardButton(get_text("BUTTON_CLOSE"), callback_data=build_call("close")))
	return markup


def back_close_markup(back_call):
	markup = InlineKeyboardMarkup(row_width=2)
	markup.add(
		InlineKeyboardButton(get_text("BUTTON_BACK"), callback_data=back_call),
		InlineKeyboardButton(get_text("BUTTON_CLOSE"), callback_data=build_call("close")),
	)
	return markup


def devices_call():
	"""Entry point of the devices screens: the network picker when there are several"""
	return build_call("nets") if MULTI_NETWORK else build_call("list", 0, 0)


# ---------------------------------------------------------------------------
# SCANNING
# ---------------------------------------------------------------------------

_scan_lock = threading.Lock()
_next_scan_at = None
_scan_errors = {}  # network name -> error text last reported, so a failing scan is not reported every round
MAX_NEW_DEVICE_MESSAGES = 5  # Above this, the new devices of a scan go in one summary


class ScanBusy(Exception):
	pass


def scan_error_text(network, e):
	label = network_label(network)
	if isinstance(e, PermissionError):
		return get_text("SCAN_ERROR_PERMISSION")
	if isinstance(e, scanner.NotConnectedError):
		return get_text("SCAN_ERROR_NOT_CONNECTED", label, html.escape(str(e.gateway)))
	if network.interface and isinstance(e, (OSError, ValueError)):
		return get_text("SCAN_ERROR_INTERFACE", label, html.escape(network.interface), html.escape(str(e)))
	return get_text("SCAN_ERROR", label, html.escape(str(e)))


def scan_network(network):
	"""Scans one network. Returns (network, first_scan, connected, new_devices,
	error_text)"""
	first_scan = devices.is_first_scan(network)
	try:
		found = scanner.arp_scan(network)
	except Exception as e:
		error(f"Error scanning {network.name}: {e}")
		return network, first_scan, 0, [], scan_error_text(network, e)
	hostnames = scanner.resolve_hostnames(list(found.values()))
	new_devices = devices.apply_scan(network.name, found, hostnames, scanner.get_vendor)
	return network, first_scan, len(found), new_devices, None


def run_scan():
	"""Sweeps every network at once, updates the known devices and reports the
	new ones. Returns (connected, new, error texts) or raises ScanBusy when a
	scan is already running"""
	if not _scan_lock.acquire(blocking=False):
		raise ScanBusy()
	try:
		started = time.time()
		with ThreadPoolExecutor(max_workers=len(WATCHED_NETWORKS)) as executor:
			results = list(executor.map(scan_network, WATCHED_NETWORKS))
		connected = sum(r[2] for r in results)
		new_count = sum(len(r[3]) for r in results)
		debug(f"Scan finished in {time.time() - started:.1f}s: {connected} connected, {new_count} new")

		report_scan_errors(results)
		first_scans = [(network, len(new)) for network, first, _, new, failure in results
					if first and not failure and not devices.is_muted(network.name)]
		if first_scans:
			notify_first_scan(first_scans)
		reported = [device for network, first, _, new, _ in results
					if not first and not devices.is_muted(network.name) for device in new]
		notify_new_devices(reported)
		return connected, new_count, [r[4] for r in results if r[4]]
	finally:
		_scan_lock.release()


def report_scan_errors(results):
	"""Notifies an error only when it differs from the last one of that network
	(and once per scan: a missing permission fails every network alike), and
	gathers the networks that work again in a single message"""
	sent = set()
	recovered = []
	for network, _, _, _, failure in results:
		previous = _scan_errors.get(network.name)
		if failure:
			_scan_errors[network.name] = failure
			if failure != previous and failure not in sent:
				sent.add(failure)
				notify(failure)
		elif previous:
			del _scan_errors[network.name]
			recovered.append(network)
	if recovered:
		notify(get_text("SCAN_RECOVERED", ", ".join(network_label(n) for n in recovered)))


def notify_first_scan(first_scans):
	markup = InlineKeyboardMarkup()
	markup.add(InlineKeyboardButton(get_text("BUTTON_DEVICES"), callback_data=devices_call()))
	if MULTI_NETWORK:
		lines = "\n".join(get_text("FIRST_SCAN_NETWORK", html.escape(n.name), count) for n, count in first_scans)
		notify(get_text("FIRST_SCAN_NETWORKS", lines), reply_markup=markup)
	else:
		notify(get_text("FIRST_SCAN", first_scans[0][1]), reply_markup=markup)


def notify_new_devices(new_devices):
	for device in new_devices:
		warning(f"New device detected in {device['network']}: {device['ip']} {device['mac']}")
	if len(new_devices) > MAX_NEW_DEVICE_MESSAGES:
		lines = []
		for device in new_devices:
			network = f"<b>{html.escape(device['network'])}</b> · " if MULTI_NETWORK else ""
			lines.append(f"· {network}<code>{html.escape(device['ip'])}</code> {html.escape(display_name(device))}")
		markup = InlineKeyboardMarkup()
		markup.add(InlineKeyboardButton(get_text("BUTTON_DEVICES"), callback_data=devices_call()))
		notify(get_text("NEW_DEVICES_SUMMARY", len(new_devices), "\n".join(lines)), reply_markup=markup)
		return
	for device in new_devices:
		network = network_by_name(device["network"])
		markup = InlineKeyboardMarkup(row_width=2)
		markup.add(
			InlineKeyboardButton(get_text("BUTTON_RENAME"), callback_data=build_call("rename", network.index, mac_id(device["mac"]))),
			InlineKeyboardButton(get_text("BUTTON_DETAILS"), callback_data=build_call("dev", network.index, mac_id(device["mac"]), network.index, 0)),
		)
		notify(get_text("NEW_DEVICE", "\n".join(device_lines(device))), reply_markup=markup)


def scan_loop():
	"""Scans now and every SCAN_INTERVAL_SECONDS. A manual scan does not move
	the schedule"""
	global _next_scan_at
	while True:
		_next_scan_at = time.time() + SCAN_INTERVAL_SECONDS
		try:
			run_scan()
		except ScanBusy:
			debug("Scheduled scan skipped, another one is running")
		except Exception as e:
			error(f"Error scanning the networks: {e}")
		time.sleep(max(0, _next_scan_at - time.time()))


# ---------------------------------------------------------------------------
# SCREENS
# ---------------------------------------------------------------------------

def count_devices(networks):
	known = devices.get_all(network_names(networks))
	return len(known), sum(1 for d in known if d.get("online"))


def build_dashboard(status_line=None):
	lines = [get_text("DASHBOARD_TITLE"), ""]
	if MULTI_NETWORK:
		for network in WATCHED_NETWORKS:
			known, online = count_devices([network])
			muted = " 🔕" if devices.is_muted(network.name) else ""
			lines.append(get_text("DASHBOARD_NETWORK", html.escape(network.name), muted, html.escape(network.range_text)))
			lines.append(f"      {get_text('DASHBOARD_DEVICES', known, online)}")
			if network.name in _scan_errors:
				lines.append(f"      {get_text('DASHBOARD_NETWORK_FAILING')}")
		lines.append("")
	else:
		network = WATCHED_NETWORKS[0]
		known, online = count_devices([network])
		lines.append(get_text("DASHBOARD_RANGE", html.escape(network.range_text), len(network.addresses)))
		lines.append(get_text("DASHBOARD_DEVICES", known, online))
		if network.name in _scan_errors:
			lines.append(get_text("DASHBOARD_NETWORK_FAILING"))
	lines.append(get_text("DASHBOARD_LAST_SCAN", format_time(devices.last_scan())))
	if _scan_lock.locked():
		lines.append(get_text("DASHBOARD_SCANNING"))
	elif _next_scan_at:
		lines.append(get_text("DASHBOARD_NEXT_SCAN", format_time(_next_scan_at)))
	if status_line:
		lines += ["", status_line]

	markup = InlineKeyboardMarkup(row_width=2)
	markup.add(
		InlineKeyboardButton(get_text("BUTTON_DEVICES"), callback_data=devices_call()),
		InlineKeyboardButton(get_text("BUTTON_SCAN"), callback_data=build_call("scan")),
	)
	if MULTI_NETWORK:
		markup.add(InlineKeyboardButton(get_text("BUTTON_ALERTS"), callback_data=build_call("alerts")))
	markup.add(
		InlineKeyboardButton(get_text("BUTTON_REFRESH"), callback_data=build_call("dashboard")),
		InlineKeyboardButton(get_text("BUTTON_CLOSE"), callback_data=build_call("close")),
	)
	return "\n".join(lines), markup


def build_network_picker():
	markup = InlineKeyboardMarkup(row_width=1)
	for network in WATCHED_NETWORKS:
		known, online = count_devices([network])
		markup.add(InlineKeyboardButton(get_text("PICKER_NETWORK", truncate(network.name), known, online), callback_data=build_call("list", network.index, 0)))
	known, online = count_devices(WATCHED_NETWORKS)
	markup.add(InlineKeyboardButton(get_text("PICKER_ALL", known, online), callback_data=build_call("list", ALL_NETWORKS, 0)))
	markup.row(
		InlineKeyboardButton(get_text("BUTTON_BACK"), callback_data=build_call("dashboard")),
		InlineKeyboardButton(get_text("BUTTON_CLOSE"), callback_data=build_call("close")),
	)
	return get_text("PICKER_TITLE"), markup


def list_title(network_filter):
	if not MULTI_NETWORK:
		return get_text("LIST_DEVICES")
	if network_filter == ALL_NETWORKS:
		return get_text("LIST_ALL_NETWORKS")
	return html.escape(network_by_index(network_filter).name)


def build_list(network_filter, page):
	networks = filtered_networks(network_filter)
	back_call = devices_call() if MULTI_NETWORK else build_call("dashboard")
	if not networks:
		return get_text("NETWORK_NOT_FOUND"), back_close_markup(back_call)
	known = devices.get_all(network_names(networks))
	if not known:
		return get_text("LIST_EMPTY"), back_close_markup(back_call)
	pages = max(1, math.ceil(len(known) / DEVICES_PER_PAGE))
	page = min(max(0, int(page)), pages - 1)
	online = sum(1 for d in known if d.get("online"))
	text = get_text("LIST_TITLE", list_title(network_filter), len(known), online)
	if pages > 1:
		text += f"\n{get_text('LIST_PAGE', page + 1, pages)}"

	markup = InlineKeyboardMarkup(row_width=1)
	for device in known[page * DEVICES_PER_PAGE:(page + 1) * DEVICES_PER_PAGE]:
		network = network_by_name(device["network"])
		status = "🟢" if device.get("online") else "⚪"
		label = f"{status} {device['ip']} · {truncate(display_name(device))}"
		markup.add(InlineKeyboardButton(label, callback_data=build_call("dev", network.index, mac_id(device["mac"]), network_filter, page)))
	if pages > 1:
		markup.row(
			InlineKeyboardButton("⬅️", callback_data=build_call("list", network_filter, page - 1) if page > 0 else build_call("noop")),
			InlineKeyboardButton(f"{page + 1}/{pages}", callback_data=build_call("noop")),
			InlineKeyboardButton("➡️", callback_data=build_call("list", network_filter, page + 1) if page < pages - 1 else build_call("noop")),
		)
	markup.row(InlineKeyboardButton(get_text("BUTTON_FORGET_ALL"), callback_data=build_call("forgetAllAsk", network_filter, page)))
	markup.row(
		InlineKeyboardButton(get_text("BUTTON_BACK"), callback_data=back_call),
		InlineKeyboardButton(get_text("BUTTON_CLOSE"), callback_data=build_call("close")),
	)
	return text, markup


def build_detail(network, mac, network_filter, page):
	device = devices.get(network.name, mac) if network else None
	if device is None:
		return get_text("DEVICE_NOT_FOUND"), back_close_markup(build_call("list", network_filter, page))
	lines = [f"📱 <b>{html.escape(display_name(device))}</b>", ""]
	lines += device_lines(device)
	lines.append("")
	if device.get("online"):
		lines.append(get_text("DEVICE_ONLINE"))
	else:
		lines.append(get_text("DEVICE_LAST_SEEN", format_ago(device.get("last_seen")), format_datetime(device.get("last_seen"))))
	lines.append(get_text("DEVICE_FIRST_SEEN", format_datetime(device.get("first_seen"))))

	ids = (network.index, mac_id(mac), network_filter, page)
	markup = InlineKeyboardMarkup(row_width=2)
	markup.add(
		InlineKeyboardButton(get_text("BUTTON_RENAME"), callback_data=build_call("rename", *ids)),
		InlineKeyboardButton(get_text("BUTTON_FORGET"), callback_data=build_call("forgetAsk", *ids)),
	)
	markup.add(
		InlineKeyboardButton(get_text("BUTTON_BACK"), callback_data=build_call("list", network_filter, page)),
		InlineKeyboardButton(get_text("BUTTON_CLOSE"), callback_data=build_call("close")),
	)
	return "\n".join(lines), markup


def build_alerts():
	markup = InlineKeyboardMarkup(row_width=1)
	for network in WATCHED_NETWORKS:
		key = "ALERTS_MUTED" if devices.is_muted(network.name) else "ALERTS_ON"
		markup.add(InlineKeyboardButton(get_text(key, truncate(network.name)), callback_data=build_call("mute", network.index)))
	markup.row(
		InlineKeyboardButton(get_text("BUTTON_BACK"), callback_data=build_call("dashboard")),
		InlineKeyboardButton(get_text("BUTTON_CLOSE"), callback_data=build_call("close")),
	)
	return get_text("ALERTS_TITLE"), markup


def confirm_markup(confirm_call, cancel_call, confirm_key="BUTTON_CONFIRM_FORGET"):
	markup = InlineKeyboardMarkup(row_width=2)
	markup.add(
		InlineKeyboardButton(get_text(confirm_key), callback_data=confirm_call),
		InlineKeyboardButton(get_text("BUTTON_CANCEL"), callback_data=cancel_call),
	)
	return markup


def show(chat_id, message_id, screen, thread_id=None):
	"""Edits message_id with a (text, markup) screen, or sends it when there is
	no message to edit"""
	text, markup = screen
	if message_id:
		edit_message(chat_id, message_id, text, markup)
	else:
		send_message(chat_id, text, reply_markup=markup, thread_id=thread_id)


def manual_scan(chat_id, message_id):
	"""Runs a scan requested from the dashboard and shows the result there"""
	try:
		connected, new, failures = run_scan()
		if len(failures) == len(WATCHED_NETWORKS):
			status = "\n\n".join(dict.fromkeys(failures))
		elif failures:
			status = get_text("SCAN_DONE_WITH_ERRORS", connected, new, len(failures))
		else:
			status = get_text("SCAN_DONE", connected, new)
	except ScanBusy:
		status = get_text("SCAN_BUSY")
	except Exception as e:
		error(f"Error scanning the networks: {e}")
		status = get_text("ERROR_GENERIC", html.escape(str(e)))
	show(chat_id, message_id, build_dashboard(status))


# ---------------------------------------------------------------------------
# TEXT INPUT (RENAME)
# ---------------------------------------------------------------------------

_inputs_lock = threading.Lock()
pending_inputs = {}  # (chat_id, user_id) -> {"network", "mac", "filter", "page", "prompt_message_id"}


def ask_rename(chat_id, user_id, network, mac, network_filter, page, thread_id=None):
	device = devices.get(network.name, mac) if network else None
	if device is None:
		send_message(chat_id, get_text("DEVICE_NOT_FOUND"), reply_markup=close_markup(), thread_id=thread_id)
		return
	prompt = get_text("RENAME_ASK", html.escape(display_name(device)), MAX_NAME_LENGTH)
	sent = send_message(chat_id, prompt, reply_markup=ForceReply(input_field_placeholder=truncate(display_name(device))), thread_id=thread_id)
	with _inputs_lock:
		pending_inputs[(chat_id, user_id)] = {"network": network, "mac": mac, "filter": network_filter, "page": page,
											"prompt_message_id": sent.message_id if sent else None}


def pop_pending_input(chat_id, user_id):
	with _inputs_lock:
		return pending_inputs.pop((chat_id, user_id), None)


def handle_rename_input(message, pending):
	chat_id = message.chat.id
	thread_id = normalize_thread(message.message_thread_id)
	delete_message(chat_id, message.message_id)
	if pending.get("prompt_message_id"):
		delete_message(chat_id, pending["prompt_message_id"])
	new_name = " ".join(message.text.split())
	if new_name == "-":
		new_name = ""  # Back to the name the network gives it
	elif new_name.startswith("/"):
		send_message(chat_id, get_text("RENAME_CANCELLED"), reply_markup=close_markup(), thread_id=thread_id)
		return
	network = pending["network"]
	if not devices.rename(network.name, pending["mac"], new_name):
		send_message(chat_id, get_text("DEVICE_NOT_FOUND"), reply_markup=close_markup(), thread_id=thread_id)
		return
	text, markup = build_detail(network, pending["mac"], pending["filter"], pending["page"])
	send_message(chat_id, f"{get_text('RENAME_DONE')}\n\n{text}", reply_markup=markup, thread_id=thread_id)


# ---------------------------------------------------------------------------
# COMMANDS
# ---------------------------------------------------------------------------

_bot_username = None


def bot_username():
	"""Username of this bot, asked to Telegram once. None while it cannot be
	known, and then every command is taken as addressed to this bot"""
	global _bot_username
	if _bot_username is None:
		try:
			_bot_username = bot.get_me().username.lower()
		except Exception as e:
			warning(f"Cannot get the bot username: {describe_error(e)}")
	return _bot_username


def is_for_another_bot(message):
	"""True for /command@OtherBot. telebot drops the @mention when matching
	commands, so in a group with several bots every one of them would answer"""
	if not message.text or not message.text.startswith("/"):
		return False
	command = message.text.split(maxsplit=1)[0]
	if "@" not in command:
		return False
	mentioned = command.split("@", 1)[1].lower()
	own = bot_username()
	return own is not None and mentioned != own


def for_me(message):
	return not is_for_another_bot(message)


def check_auth(message):
	if not is_authorized(message.from_user.id, message.chat.id):
		warning(f"Unauthorized access attempt: user {message.from_user.id} (@{message.from_user.username}) in chat {message.chat.id}")
		send_message(message.chat.id, get_text("USER_NOT_ALLOWED", message.from_user.id), thread_id=message.message_thread_id)
		return False
	return True


def command_reply(message, screen):
	if not check_auth(message):
		return
	# A command cancels a rename left waiting for its answer
	pop_pending_input(message.chat.id, message.from_user.id)
	delete_message(message.chat.id, message.message_id)
	text, markup = screen() if callable(screen) else (screen, close_markup())
	send_message(message.chat.id, text, reply_markup=markup, thread_id=message.message_thread_id)


@bot.message_handler(func=for_me, commands=["start"])
def command_start(message):
	command_reply(message, build_dashboard)


@bot.message_handler(func=for_me, commands=["list"])
def command_list(message):
	command_reply(message, build_network_picker if MULTI_NETWORK else lambda: build_list(0, 0))


@bot.message_handler(func=for_me, commands=["scan"])
def command_scan(message):
	if not check_auth(message):
		return
	pop_pending_input(message.chat.id, message.from_user.id)
	delete_message(message.chat.id, message.message_id)
	sent = send_message(message.chat.id, get_text("SCANNING"), thread_id=message.message_thread_id)
	if sent:
		threading.Thread(target=manual_scan, args=(message.chat.id, sent.message_id), daemon=True).start()


@bot.message_handler(func=for_me, commands=["help"])
def command_help(message):
	command_reply(message, get_text("HELP"))


@bot.message_handler(func=for_me, commands=["version"])
def command_version(message):
	command_reply(message, get_text("VERSION_TEXT", VERSION))


@bot.message_handler(func=for_me, commands=["donate"])
def command_donate(message):
	command_reply(message, get_text("DONATE"))


@bot.message_handler(func=for_me, commands=["donors"])
def command_donors(message):
	donors = get_donors_online()
	if donors:
		text = get_text("DONORS_LIST", "\n".join(f"· {html.escape(d)}" for d in donors))
	else:
		text = get_text("ERROR_GETTING_DONORS")
	command_reply(message, text)


def get_donors_online():
	"""Sorted list of donor names, empty when the list cannot be retrieved"""
	try:
		response = requests.get(DONORS_URL, timeout=REQUEST_TIMEOUT, headers={"Cache-Control": "no-cache", "Pragma": "no-cache"})
		response.raise_for_status()
		data = response.json()
		if isinstance(data, list):
			return sorted({str(d) for d in data}, key=str.lower)
		warning("The donors list has an unexpected format")
	except Exception as e:
		warning(f"Cannot get the donors list: {describe_error(e)}")
	return []


@bot.message_handler(func=lambda message: True)
def handle_text(message):
	if not message.text or is_for_another_bot(message) or not is_authorized(message.from_user.id, message.chat.id):
		return
	pending = pop_pending_input(message.chat.id, message.from_user.id)
	if pending:
		handle_rename_input(message, pending)


# ---------------------------------------------------------------------------
# CALLBACK HANDLER
# ---------------------------------------------------------------------------

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
	if not is_authorized(call.from_user.id, call.message.chat.id):
		try:
			bot.answer_callback_query(call.id, get_text("USER_NOT_ALLOWED_SHORT"), show_alert=True)
		except Exception:
			pass
		return

	chat_id = call.message.chat.id
	message_id = call.message.message_id
	thread_id = normalize_thread(call.message.message_thread_id)
	parts = call.data.split("|")
	command, args = parts[0], parts[1:]

	tooltip = None
	if command == "scan" and _scan_lock.locked():
		tooltip = get_text("SCAN_BUSY")
	try:
		bot.answer_callback_query(call.id, tooltip)
	except Exception:
		pass

	try:
		if command == "noop":
			pass

		elif command == "close":
			delete_message(chat_id, message_id)

		elif command == "dashboard":
			show(chat_id, message_id, build_dashboard())

		elif command == "scan":
			if not _scan_lock.locked():
				edit_message(chat_id, message_id, get_text("SCANNING"))
				# A scan takes a few seconds: off the handler thread, so the
				# other buttons keep answering meanwhile
				threading.Thread(target=manual_scan, args=(chat_id, message_id), daemon=True).start()

		elif command == "nets":
			show(chat_id, message_id, build_network_picker())

		elif command == "list":
			show(chat_id, message_id, build_list(args[0], args[1]))

		elif command == "dev":
			show(chat_id, message_id, build_detail(network_by_index(args[0]), mac_from_id(args[1]), args[2], args[3]))

		elif command == "rename":
			# From a new device notification the button keeps its message; from
			# the detail screen the prompt replaces it
			network = network_by_index(args[0])
			from_detail = len(args) > 2
			network_filter, page = (args[2], args[3]) if from_detail else (args[0], 0)
			if from_detail:
				delete_message(chat_id, message_id)
			ask_rename(chat_id, call.from_user.id, network, mac_from_id(args[1]), network_filter, page, thread_id=thread_id)

		elif command == "forgetAsk":
			network, mac, network_filter, page = network_by_index(args[0]), mac_from_id(args[1]), args[2], args[3]
			device = devices.get(network.name, mac) if network else None
			if device is None:
				show(chat_id, message_id, (get_text("DEVICE_NOT_FOUND"), back_close_markup(build_call("list", network_filter, page))))
			else:
				text = get_text("FORGET_CONFIRM", html.escape(display_name(device)), html.escape(device["ip"]))
				edit_message(chat_id, message_id, text, confirm_markup(build_call("forget", *args), build_call("dev", *args)))

		elif command == "forget":
			network, mac, network_filter, page = network_by_index(args[0]), mac_from_id(args[1]), args[2], args[3]
			device = devices.get(network.name, mac) if network else None
			if device and devices.forget(network.name, mac):
				text = get_text("FORGET_DONE", html.escape(display_name(device)))
			else:
				text = get_text("DEVICE_NOT_FOUND")
			edit_message(chat_id, message_id, text, back_close_markup(build_call("list", network_filter, page)))

		elif command == "forgetAllAsk":
			network_filter, page = args[0], args[1]
			networks = filtered_networks(network_filter)
			count = len(devices.get_all(network_names(networks)))
			scope = get_text("FORGET_ALL_SCOPE", list_title(network_filter)) if MULTI_NETWORK and network_filter != ALL_NETWORKS else ""
			edit_message(chat_id, message_id, get_text("FORGET_ALL_CONFIRM", count, scope),
						confirm_markup(build_call("forgetAll", network_filter), build_call("list", network_filter, page), "BUTTON_CONFIRM_FORGET_ALL"))

		elif command == "forgetAll":
			count = devices.forget_all(filtered_networks(args[0]))
			edit_message(chat_id, message_id, get_text("FORGET_ALL_DONE", count), back_close_markup(build_call("dashboard")))

		elif command == "alerts":
			show(chat_id, message_id, build_alerts())

		elif command == "mute":
			network = network_by_index(args[0])
			if network:
				devices.toggle_muted(network.name)
			show(chat_id, message_id, build_alerts())

		else:
			debug(f"Unknown callback: {call.data}")

	except Exception as e:
		error(f"Error handling callback {call.data}: {e}")
		edit_message(chat_id, message_id, get_text("ERROR_GENERIC", html.escape(str(e))), close_markup())


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def send_startup_message():
	if MULTI_NETWORK:
		lines = [get_text("STARTUP_NETWORKS", len(WATCHED_NETWORKS))]
		for network in WATCHED_NETWORKS:
			interface = f" · {html.escape(network.interface)}" if network.interface else ""
			lines.append(get_text("STARTUP_NETWORK", html.escape(network.name), html.escape(network.range_text), len(network.addresses), interface))
		networks_text = "\n".join(lines)
	else:
		network = WATCHED_NETWORKS[0]
		networks_text = get_text("STARTUP_NETWORK_SINGLE", html.escape(network.range_text), len(network.addresses))
	known, _ = count_devices(WATCHED_NETWORKS)
	parts = [get_text("STARTUP_MESSAGE", networks_text, format_interval(SCAN_INTERVAL_SECONDS), known, VERSION)]
	if devices.load_problem:
		kind, detail = devices.load_problem
		if kind == "broken":
			parts.append(get_text("STARTUP_DATA_BROKEN", html.escape(detail)))
		elif kind == "migrated":
			parts.append(get_text("STARTUP_MIGRATED", detail))
	notify("\n\n".join(parts))


def track_polling_heartbeat():
	"""Touches HEARTBEAT_PATH every time Telegram answers a poll. infinity_polling
	swallows every error and retries forever, so a bot that serves nobody (no
	network, or a 409 because another instance uses the same token) keeps the
	process alive; the Docker HEALTHCHECK looks at how old this file is instead"""
	get_updates = bot.get_updates
	def get_updates_with_heartbeat(*args, **kwargs):
		updates = get_updates(*args, **kwargs)
		try:
			with open(HEARTBEAT_PATH, "a"):
				os.utime(HEARTBEAT_PATH)
		except OSError as e:
			warning(f"Cannot update heartbeat file {HEARTBEAT_PATH}: {e}")
		return updates
	bot.get_updates = get_updates_with_heartbeat


if __name__ == "__main__":
	for network in WATCHED_NETWORKS:
		interface = f" through {network.interface}" if network.interface else ""
		debug(f"Watching {network.name}: {network.range_text} ({len(network.addresses)} addresses){interface}")
	debug(f"IntruBot {VERSION} started. Scanning every {format_interval(SCAN_INTERVAL_SECONDS)}")
	send_startup_message()
	threading.Thread(target=scan_loop, daemon=True).start()
	try:
		bot.set_my_commands([
			telebot.types.BotCommand("/start", get_text("MENU_START")),
			telebot.types.BotCommand("/list", get_text("MENU_LIST")),
			telebot.types.BotCommand("/scan", get_text("MENU_SCAN")),
			telebot.types.BotCommand("/help", get_text("MENU_HELP")),
			telebot.types.BotCommand("/version", get_text("MENU_VERSION")),
			telebot.types.BotCommand("/donate", get_text("MENU_DONATE")),
			telebot.types.BotCommand("/donors", get_text("MENU_DONORS")),
		])
	except Exception as e:
		warning(f"Cannot set bot commands: {describe_error(e)}")
	track_polling_heartbeat()
	bot.infinity_polling(timeout=60)
