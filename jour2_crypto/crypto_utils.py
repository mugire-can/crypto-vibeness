"""
Symmetric encryption utilities for Crypto Vibeness.

This module provides:
- AES-256-CBC encryption with HMAC-SHA256 authentication (legacy/compatible)
- AES-256-GCM authenticated encryption (recommended, simpler, faster)
- PBKDF2-SHA256 key derivation
- Base64 encode/decode helpers for transmission

AES-GCM is an AEAD (Authenticated Encryption with Associated Data) mode that
provides both confidentiality and integrity in a single primitive, making a
separate HMAC unnecessary.
"""

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import os
import base64
import hmac as hmac_module

# Constants
ITERATIONS = 480000
ALGORITHM_NAME = 'AES-256-CBC'
GCM_ALGORITHM_NAME = 'AES-256-GCM'
GCM_NONCE_SIZE = 12   # 96-bit nonce recommended for GCM
GCM_TAG_SIZE = 16     # 128-bit authentication tag


def derive_key_from_password(password: str, salt: bytes = None) -> tuple[bytes, bytes]:
    """
    Derive a 32-byte AES-256 key from a password using PBKDF2-SHA256.

    This function uses PBKDF2 with SHA256 hash algorithm to derive a cryptographically
    secure key from a password. It can generate a random salt if not provided.

    Args:
        password: Password string to derive the key from.
        salt: Optional salt bytes. If not provided, generates a random 16-byte salt.

    Returns:
        tuple: (derived_key, salt) where:
            - derived_key: 32-byte key suitable for AES-256
            - salt: 16-byte salt used in derivation (for later decryption)

    Raises:
        TypeError: If password is not a string.
    """
    if salt is None:
        salt = os.urandom(16)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=ITERATIONS,
        backend=default_backend()
    )
    key = kdf.derive(password.encode())
    return key, salt


# ---------------------------------------------------------------------------
# AES-256-CBC + HMAC-SHA256  (Encrypt-then-MAC)
# ---------------------------------------------------------------------------

def encrypt_message(plaintext: str, key: bytes) -> tuple[bytes, bytes]:
    """
    Encrypt plaintext using AES-256 in CBC mode with HMAC-SHA256 authentication.

    This function encrypts the plaintext using AES-256 in CBC mode with a random IV,
    then appends an HMAC-SHA256 digest for authentication. The IV is returned separately
    for use in decryption.

    Args:
        plaintext: String to encrypt.
        key: 32-byte AES-256 key (typically from derive_key_from_password).

    Returns:
        tuple: (ciphertext_with_hmac, iv) where:
            - ciphertext_with_hmac: Concatenated ciphertext + HMAC (32-byte digest appended)
            - iv: 16-byte random initialization vector

    Raises:
        TypeError: If plaintext is not a string or key is not bytes.
        ValueError: If key length is not 32 bytes.
    """
    if not isinstance(key, bytes) or len(key) != 32:
        raise ValueError("Key must be 32 bytes for AES-256")

    # Generate random IV
    iv = os.urandom(16)

    # Create cipher and encrypt
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()

    # Apply PKCS7 padding
    plaintext_bytes = plaintext.encode('utf-8')
    padding_length = 16 - (len(plaintext_bytes) % 16)
    padded_plaintext = plaintext_bytes + bytes([padding_length] * padding_length)

    # Encrypt padded plaintext
    ciphertext = encryptor.update(padded_plaintext) + encryptor.finalize()

    # Create HMAC-SHA256 for authentication
    h = hmac.HMAC(key, hashes.SHA256(), backend=default_backend())
    h.update(ciphertext)
    hmac_digest = h.finalize()

    # Concatenate ciphertext and HMAC
    ciphertext_with_hmac = ciphertext + hmac_digest

    return ciphertext_with_hmac, iv


def decrypt_message(encrypted_data: bytes, iv: bytes, key: bytes) -> str:
    """
    Decrypt and authenticate AES-256 CBC encrypted message with HMAC verification.

    This function verifies the HMAC-SHA256 digest first (using constant-time comparison)
    to ensure data integrity before attempting decryption. Only decrypts if HMAC
    verification succeeds.

    Args:
        encrypted_data: Concatenated ciphertext + HMAC bytes from encrypt_message.
        iv: 16-byte initialization vector (from encrypt_message return value).
        key: 32-byte AES-256 key (same key used in encryption).

    Returns:
        str: Decrypted plaintext string.

    Raises:
        ValueError: If HMAC verification fails or data is malformed.
        TypeError: If parameters are not of expected types.
    """
    if not isinstance(key, bytes) or len(key) != 32:
        raise ValueError("Key must be 32 bytes for AES-256")

    if not isinstance(iv, bytes) or len(iv) != 16:
        raise ValueError("IV must be 16 bytes")

    # HMAC-SHA256 produces 32-byte digest
    hmac_size = 32

    if len(encrypted_data) < hmac_size:
        raise ValueError("Encrypted data too short to contain valid HMAC")

    # Split ciphertext and HMAC
    ciphertext = encrypted_data[:-hmac_size]
    received_hmac = encrypted_data[-hmac_size:]

    # Verify HMAC with constant-time comparison
    h = hmac.HMAC(key, hashes.SHA256(), backend=default_backend())
    h.update(ciphertext)
    computed_hmac = h.finalize()

    if not hmac_module.compare_digest(computed_hmac, received_hmac):
        raise ValueError("HMAC verification failed - data may have been tampered with")

    # Decrypt if HMAC is valid
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()

    # Remove PKCS7 padding
    padding_length = padded_plaintext[-1]
    if padding_length > 16 or padding_length == 0:
        raise ValueError("Invalid padding - data may be corrupted")

    plaintext = padded_plaintext[:-padding_length]

    return plaintext.decode('utf-8')


# ---------------------------------------------------------------------------
# AES-256-GCM  (Authenticated Encryption — recommended)
# ---------------------------------------------------------------------------

def encrypt_message_gcm(plaintext: str, key: bytes) -> tuple[bytes, bytes]:
    """
    Encrypt plaintext using AES-256-GCM (Authenticated Encryption).

    GCM (Galois/Counter Mode) provides both confidentiality and integrity in a
    single pass, with no need for a separate HMAC.  The 16-byte authentication
    tag is appended to the ciphertext in the returned value.

    Args:
        plaintext: String to encrypt.
        key: 32-byte AES-256 key.

    Returns:
        tuple: (ciphertext_with_tag, nonce) where:
            - ciphertext_with_tag: ciphertext concatenated with the 16-byte GCM tag
            - nonce: 12-byte random nonce

    Raises:
        ValueError: If key length is not 32 bytes.
    """
    if not isinstance(key, bytes) or len(key) != 32:
        raise ValueError("Key must be 32 bytes for AES-256-GCM")

    nonce = os.urandom(GCM_NONCE_SIZE)
    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(plaintext.encode('utf-8')) + encryptor.finalize()
    tag = encryptor.tag  # 16-byte authentication tag

    return ciphertext + tag, nonce


def decrypt_message_gcm(encrypted_data: bytes, nonce: bytes, key: bytes) -> str:
    """
    Decrypt and authenticate AES-256-GCM encrypted message.

    Args:
        encrypted_data: ciphertext concatenated with 16-byte GCM tag.
        nonce: 12-byte nonce used during encryption.
        key: 32-byte AES-256 key.

    Returns:
        str: Decrypted plaintext string.

    Raises:
        ValueError: If authentication fails (data tampered) or inputs are invalid.
    """
    if not isinstance(key, bytes) or len(key) != 32:
        raise ValueError("Key must be 32 bytes for AES-256-GCM")

    if not isinstance(nonce, bytes) or len(nonce) != GCM_NONCE_SIZE:
        raise ValueError(f"Nonce must be {GCM_NONCE_SIZE} bytes for AES-256-GCM")

    if len(encrypted_data) < GCM_TAG_SIZE:
        raise ValueError("Encrypted data too short to contain GCM tag")

    ciphertext = encrypted_data[:-GCM_TAG_SIZE]
    tag = encrypted_data[-GCM_TAG_SIZE:]

    try:
        cipher = Cipher(
            algorithms.AES(key), modes.GCM(nonce, tag), backend=default_backend()
        )
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()
    except Exception as exc:
        raise ValueError("GCM authentication failed - data may have been tampered with") from exc

    return plaintext.decode('utf-8')


# ---------------------------------------------------------------------------
# Transmission helpers (work for both CBC and GCM)
# ---------------------------------------------------------------------------

def encode_for_transmission(ciphertext: bytes, iv: bytes) -> str:
    """
    Base64 encode IV/nonce and ciphertext for safe transmission.

    Works for both AES-CBC (16-byte IV) and AES-GCM (12-byte nonce).

    Args:
        ciphertext: Ciphertext bytes (may include HMAC or GCM tag).
        iv: Initialization vector or nonce.

    Returns:
        str: Encoded string in format "base64(iv):base64(ciphertext)".
    """
    if not isinstance(ciphertext, bytes):
        raise TypeError("Ciphertext must be bytes")
    if not isinstance(iv, bytes):
        raise TypeError("IV/nonce must be bytes")

    iv_b64 = base64.b64encode(iv).decode('ascii')
    ciphertext_b64 = base64.b64encode(ciphertext).decode('ascii')

    return f"{iv_b64}:{ciphertext_b64}"


def decode_from_transmission(encoded: str) -> tuple[bytes, bytes]:
    """
    Base64 decode IV/nonce and ciphertext from transmission format.

    Works for both AES-CBC (16-byte IV) and AES-GCM (12-byte nonce).

    Args:
        encoded: Encoded string in format "base64(iv):base64(ciphertext)".

    Returns:
        tuple: (ciphertext, iv) where both are decoded bytes.

    Raises:
        ValueError: If format is invalid or Base64 decoding fails.
    """
    try:
        parts = encoded.split(":")
        if len(parts) != 2:
            raise ValueError(
                "Invalid transmission format - expected 'base64(iv):base64(ciphertext)'"
            )

        iv_b64, ciphertext_b64 = parts
        iv = base64.b64decode(iv_b64)
        ciphertext = base64.b64decode(ciphertext_b64)

        if len(iv) not in (12, 16):
            raise ValueError("Decoded IV/nonce must be 12 bytes (GCM) or 16 bytes (CBC)")

        return ciphertext, iv

    except ValueError as e:
        raise ValueError(f"Failed to decode transmission format: {e}") from e
    except Exception as e:
        raise ValueError(f"Unexpected error during transmission decoding: {e}") from e


