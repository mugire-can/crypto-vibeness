"""
Configuration for Jour 4 – ECDH / ECDSA / AES-GCM chat system.
"""

# Server
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5002
SERVER_LISTEN_BACKLOG = 5
SERVER_SOCKET_TIMEOUT = 1.0

# Client
CLIENT_HOST = 'localhost'
CLIENT_PORT = 5002
BUFFER_SIZE = 8192

# Cryptography
EC_CURVE = 'P-256'           # ECDSA signing curve
ECDH_CURVE = 'X25519'        # ECDH key exchange curve
AES_MODE = 'GCM'             # Authenticated encryption
AES_KEY_BITS = 256
GCM_NONCE_SIZE = 12
GCM_TAG_SIZE = 16
HKDF_INFO = b'crypto-vibeness-jour4'

# Key storage
KEY_STORAGE_DIR = '~/.crypto_vibeness_j4'
ECDH_PRIV_EXT = '.ecdh.priv'
ECDSA_PRIV_EXT = '.ecdsa.priv'
ECDSA_PUB_EXT = '.ecdsa.pub'

# Session
MAX_MESSAGE_SIZE = 10000
