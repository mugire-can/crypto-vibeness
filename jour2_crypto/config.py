"""
Configuration for Jour 2 - Symmetric Cryptography
Encryption settings for symmetric crypto implementation
"""

# Default server configuration (same as Jour 1)
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5000

# Encryption configuration
DEFAULT_PASSWORD = "password123"  # Default password for encryption

# PBKDF2 Key Derivation
PBKDF2_ITERATIONS = 480000  # NIST recommendation as of 2023
PBKDF2_SALT_LENGTH = 16  # 16 bytes = 128 bits
PBKDF2_ALGORITHM = "SHA256"

# AES Encryption
AES_KEY_SIZE = 32  # 256 bits for AES-256
AES_BLOCK_SIZE = 16  # 128 bits (standard for AES)
AES_MODE = "CBC"  # Cipher Block Chaining

# HMAC Authentication
HMAC_ALGORITHM = "SHA256"

# Message configuration
MESSAGE_BUFFER_SIZE = 4096  # Larger buffer for encrypted messages
ENCODING = "utf-8"  # Character encoding for all messages

# Connection configuration
CONNECTION_TIMEOUT = 30
SOCKET_TIMEOUT = 5

# Server-specific
SERVER_BACKLOG = 5
SHUTDOWN_TIMEOUT = 5

# Commands
QUIT_COMMAND = "/quit"
LIST_COMMAND = "/list"
HELP_COMMAND = "/help"

# Notification messages
NOTIFICATION_JOINED = "has joined"
NOTIFICATION_LEFT = "has left"

# Logging
LOG_FORMAT = "[%(asctime)s] %(levelname)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Encryption log format
ENCRYPTED_MESSAGE_PREFIX = "[encrypted: "
ENCRYPTED_MESSAGE_SUFFIX = "]"
