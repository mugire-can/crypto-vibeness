"""
Configuration for Day 1 - YOLO Chat System
Shared constants used by both server and client
"""

# Default server configuration
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5000

# Message configuration
MAX_MESSAGE_SIZE = 4096  # Maximum message size in bytes
MESSAGE_BUFFER_SIZE = 1024  # Buffer size for receiving messages
ENCODING = "utf-8"  # Character encoding for all messages

# Connection configuration
CONNECTION_TIMEOUT = 30  # Seconds to wait for initial connection
SOCKET_TIMEOUT = 5  # Timeout for socket operations (0 = blocking)

# Server-specific
SERVER_BACKLOG = 5  # Number of pending connections server will accept
SHUTDOWN_TIMEOUT = 5  # Seconds to wait for clients to disconnect on shutdown

# Commands
QUIT_COMMAND = "/quit"
LIST_COMMAND = "/list"
HELP_COMMAND = "/help"

# Message types for internal use
MSG_TYPE_USER_MESSAGE = "message"
MSG_TYPE_NOTIFICATION = "notification"
MSG_TYPE_COMMAND = "command"

# Notification messages
NOTIFICATION_JOINED = "has joined"
NOTIFICATION_LEFT = "has left"

# Logging
LOG_FORMAT = "[%(asctime)s] %(levelname)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
