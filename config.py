import os

# DOCKER ENVIRONMENT VARIABLES
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_ADMIN = os.environ.get("TELEGRAM_ADMIN")
TELEGRAM_GROUP = os.environ.get("TELEGRAM_GROUP")
TELEGRAM_THREAD = os.environ.get("TELEGRAM_THREAD", "1")
LANGUAGE = os.environ.get("LANGUAGE", "ES")
NETWORKS = os.environ.get("NETWORKS")  # "name=range[@interface]; ..." to watch several networks/VLANs
IP_RANGE = os.environ.get("IP_RANGE")  # Single network, used when NETWORKS is empty
HOURS_BETWEEN_SCANS = os.environ.get("HOURS_BETWEEN_SCANS", "1")
NETWORK_INTERFACE = os.environ.get("NETWORK_INTERFACE")  # Interface for IP_RANGE. Empty = the one routing it

# CONSTANTS
VERSION = "2.0.1"
ANONYMOUS_USER_ID = "1087968824"
DONORS_URL = "https://donate.dgongut.com/donors.json"
LOCALE_PATH = os.environ.get("LOCALE_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "locale"))
DATA_PATH = os.environ.get("DATA_PATH", "/app/data")  # Persistent data (mapped as a volume)
DEVICES_FILE = "devices.json"
LEGACY_DEVICES_FILE = "known_devices.json"  # IP -> name map written by 1.x
MAX_SCAN_ADDRESSES = 65536  # Bigger ranges (all networks together) are refused: an ARP sweep over them would never end
ARP_TIMEOUT = 2  # Seconds to wait for ARP answers after the last request
ARP_RETRIES = 2  # Extra rounds for the addresses that did not answer (sleeping phones)
HOSTNAME_LOOKUP_TIMEOUT = 5  # Seconds the reverse DNS lookups of a scan may take in total
DEVICES_PER_PAGE = 10  # Devices listed per page
MAX_NAME_LENGTH = 40  # Custom names are cut to this length
MAX_NAME_LENGTH_IN_BUTTON = 30
MAX_CALLBACK_DATA_BYTES = 64  # Telegram hard limit for inline button callback_data
MAX_MESSAGE_LENGTH = 4096  # Telegram hard limit for a message body
REQUEST_TIMEOUT = 10  # Seconds before aborting an HTTP request (donors list)
HEARTBEAT_PATH = "/tmp/intrubot.heartbeat"  # Touched on every successful poll, read by the Docker HEALTHCHECK (keep both in sync)
