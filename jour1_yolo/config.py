"""Configuration for Day 1 - YOLO Chat System"""

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5000
HOST_BIND = "0.0.0.0"

MAX_MESSAGE_SIZE = 4096
MESSAGE_BUFFER_SIZE = 4096
ENCODING = "utf-8"

CONNECTION_TIMEOUT = 30
SOCKET_TIMEOUT = None  # blocking

SERVER_BACKLOG = 10
SHUTDOWN_TIMEOUT = 5

# Auth
PASSWORD_FILE = "this_is_safe.txt"
PASSWORD_RULES_FILE = "password_rules.json"

# Default room
DEFAULT_ROOM = "general"

# ANSI colors assigned to users deterministically
COLORS = ['\033[31m', '\033[32m', '\033[33m', '\033[34m', '\033[35m', '\033[36m',
          '\033[91m', '\033[92m', '\033[93m', '\033[94m', '\033[95m', '\033[96m']
RESET = '\033[0m'
COLOR_SYSTEM = '\033[90m'  # dark grey for system messages
COLOR_ERROR = '\033[31m'   # red for errors

LOG_FORMAT = "[%(asctime)s] %(levelname)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
