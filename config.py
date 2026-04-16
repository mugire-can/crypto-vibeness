"""
Unified Configuration for Crypto Vibeness - Progressive Cryptography Chat System

This configuration supports all security levels:
  - YOLO: No encryption, basic authentication (MD5)
  - SYMMETRIC: Per-user AES-256 encryption
  - ASYMMETRIC: RSA key exchange + E2EE
  - ECDH: Modern ECDH + ECDSA + AES-256-GCM (PFS)
"""

import os
from pathlib import Path

# ============================================================================
# SECURITY LEVELS
# ============================================================================
SECURITY_LEVELS = {
    'YOLO': {
        'port': 5000,
        'description': 'Day 1: Basic chat with MD5 authentication, no encryption',
        'features': ['rooms', 'authentication', 'colors', 'logging']
    },
    'SYMMETRIC': {
        'port': 5001,
        'description': 'Day 2: Per-user AES-256 symmetric encryption',
        'features': ['rooms', 'authentication', 'symmetric_encryption', 'colors', 'logging']
    },
    'ASYMMETRIC': {
        'port': 5002,
        'description': 'Day 3: RSA-based key exchange with E2EE',
        'features': ['rooms', 'authentication', 'asymmetric_encryption', 'e2ee', 'signatures', 'colors', 'logging']
    },
    'ECDH': {
        'port': 5003,
        'description': 'Day 4: Modern ECDH + ECDSA + AES-256-GCM (Perfect Forward Secrecy)',
        'features': ['rooms', 'authentication', 'ecdh_exchange', 'ecdsa_signing', 'aes_gcm_encryption', 'pfs', 'colors', 'logging']
    }
}

# ============================================================================
# NETWORK CONFIGURATION
# ============================================================================
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5000
DEFAULT_SECURITY_LEVEL = "YOLO"

HOST_BIND = "0.0.0.0"
MESSAGE_BUFFER_SIZE = 8192
ENCODING = "utf-8"
CONNECTION_TIMEOUT = 30
SOCKET_TIMEOUT = None  # blocking
SERVER_BACKLOG = 10
SHUTDOWN_TIMEOUT = 5

# ============================================================================
# AUTHENTICATION (All Levels)
# ============================================================================
DEFAULT_ROOM = "general"
PASSWORD_FILE = "this_is_safe.txt"
PASSWORD_RULES_FILE = "password_rules.json"

# MD5 (Jour 1 - YOLO)
USE_MD5 = False  # Set to True only for YOLO mode

# Modern hashing (Jour 2+ - SYMMETRIC, ASYMMETRIC, ECDH)
HASH_PURPOSE_PASSWORD = b'password'
HASH_PURPOSE_KEY = b'key_derivation'

# ============================================================================
# JOUR 1: YOLO - Terminal Colors & Logging
# ============================================================================
COLORS = [
    '\033[31m',   # Red
    '\033[32m',   # Green
    '\033[33m',   # Yellow
    '\033[34m',   # Blue
    '\033[35m',   # Magenta
    '\033[36m',   # Cyan
    '\033[91m',   # Bright Red
    '\033[92m',   # Bright Green
    '\033[93m',   # Bright Yellow
    '\033[94m',   # Bright Blue
    '\033[95m',   # Bright Magenta
    '\033[96m',   # Bright Cyan
]
RESET = '\033[0m'
COLOR_SYSTEM = '\033[90m'   # Dark grey for system messages
COLOR_ERROR = '\033[31m'    # Red for errors
COLOR_SUCCESS = '\033[92m'  # Green for success
COLOR_WARNING = '\033[93m'  # Yellow for warnings

LOG_FORMAT = "[%(asctime)s] %(levelname)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

def get_user_color(username: str) -> str:
    """Return deterministic ANSI color code for username."""
    idx = abs(hash(username)) % len(COLORS)
    return COLORS[idx]

# ============================================================================
# JOUR 2: SYMMETRIC ENCRYPTION (AES-256-CBC + HMAC)
# ============================================================================
PBKDF2_ITERATIONS = 480000  # NIST recommendation (2024)
PBKDF2_SALT_LENGTH = 16     # 128 bits
PBKDF2_ALGORITHM = "SHA256"

AES_KEY_SIZE = 32           # 256 bits
AES_BLOCK_SIZE = 16         # 128 bits (standard)
AES_CBC_MODE = "CBC"        # Cipher Block Chaining
AES_GCM_MODE = "GCM"        # Galois/Counter Mode
HMAC_ALGORITHM = "SHA256"

# User keys storage
USER_KEYS_FILE = "user_keys_do_not_steal_plz.txt"
USER_KEYS_DIR = "users"  # Local storage on client

# ============================================================================
# JOUR 3: ASYMMETRIC ENCRYPTION (RSA-2048)
# ============================================================================
RSA_KEY_SIZE = 2048
RSA_PUBLIC_EXPONENT = 65537
RSA_PADDING = 'OAEP'
RSA_HASH_ALGORITHM = 'SHA256'
SIGNATURE_ALGORITHM = 'RSA-PSS'
SIGNATURE_HASH = 'SHA256'

# Key file extensions
PRIVATE_KEY_EXTENSION = '.priv'
PUBLIC_KEY_EXTENSION = '.pub'
PUBLIC_KEYS_DIR = "public_keys"  # Server directory for public keys

# ============================================================================
# JOUR 4: ECDH + ECDSA (Modern Cryptography)
# ============================================================================
ECDH_CURVE = 'X25519'        # Key exchange
ECDSA_CURVE = 'P-256'        # Signing
HKDF_HASH = 'SHA256'         # Key derivation from shared secret
HKDF_SALT = b'crypto-vibeness'

# ============================================================================
# MESSAGE PROTOCOL
# ============================================================================
MESSAGE_TYPES = {
    'AUTH': 'Authentication',
    'AUTH_RESPONSE': 'Authentication response',
    'PUBLIC_KEY': 'Public key distribution',
    'SESSION_KEY': 'Session key establishment',
    'MESSAGE': 'Chat message',
    'ROOMS': 'List of rooms',
    'USERS': 'List of users',
    'ROOM_CHANGED': 'Room change notification',
    'SIGNATURE': 'Digital signature',
    'ERROR': 'Error message'
}

# ============================================================================
# COMMAND SYSTEM
# ============================================================================
COMMANDS = {
    'QUIT': '/quit',
    'ROOMS': '/rooms',
    'USERS': '/users',
    'JOIN': '/join',
    'CREATE': '/create',
    'KEY': '/key',         # Jour 3: fetch user's public key
    'SEND': '@',           # @ username message
    'HELP': '/help'
}

# ============================================================================
# STORAGE DIRECTORIES
# ============================================================================
STORAGE_BASE = Path.home() / ".crypto_vibeness"
STORAGE_KEYS = STORAGE_BASE / "keys"
STORAGE_LOGS = STORAGE_BASE / "logs"

# Create directories if they don't exist
for directory in [STORAGE_BASE, STORAGE_KEYS, STORAGE_LOGS]:
    directory.mkdir(parents=True, exist_ok=True)

# ============================================================================
# TIMEOUTS & LIMITS
# ============================================================================
CLIENT_TIMEOUT = 5.0
MAX_MESSAGE_SIZE = 10000
SESSION_TIMEOUT = 3600  # 1 hour
MAX_USERNAME_LENGTH = 32
MAX_ROOM_NAME_LENGTH = 64
MAX_MESSAGE_LENGTH = 1000

# ============================================================================
# VALIDATION
# ============================================================================
MIN_PASSWORD_LENGTH = 8
MIN_ROOM_PASSWORD_LENGTH = 4
