"""
Symmetric encryption utilities for Crypto Vibeness.

This module provides AES-256 encryption, PBKDF2 key derivation, and HMAC authentication
for secure message encryption and decryption with authentication.
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


def encode_for_transmission(ciphertext: bytes, iv: bytes) -> str:
    """
    Base64 encode IV and ciphertext for safe transmission.

    This function encodes the IV and ciphertext (which may have HMAC appended) using
    Base64 to create a safe string format for transmission over text-based channels.

    Args:
        ciphertext: Ciphertext bytes (may include HMAC appended from encrypt_message).
        iv: 16-byte initialization vector.

    Returns:
        str: Encoded string in format "base64(iv):base64(ciphertext)".

    Raises:
        TypeError: If parameters are not bytes.
    """
    if not isinstance(ciphertext, bytes):
        raise TypeError("Ciphertext must be bytes")

    if not isinstance(iv, bytes):
        raise TypeError("IV must be bytes")

    iv_b64 = base64.b64encode(iv).decode('ascii')
    ciphertext_b64 = base64.b64encode(ciphertext).decode('ascii')

    return f"{iv_b64}:{ciphertext_b64}"


def decode_from_transmission(encoded: str) -> tuple[bytes, bytes]:
    """
    Base64 decode IV and ciphertext from transmission format.

    This function decodes a transmission-formatted string back to binary IV and
    ciphertext components.

    Args:
        encoded: Encoded string in format "base64(iv):base64(ciphertext)".

    Returns:
        tuple: (ciphertext, iv) where:
            - ciphertext: Decoded ciphertext bytes (may have HMAC appended)
            - iv: Decoded 16-byte initialization vector

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

        if len(iv) != 16:
            raise ValueError("Decoded IV must be 16 bytes")

        return ciphertext, iv

    except ValueError as e:
        raise ValueError(f"Failed to decode transmission format: {e}") from e
    except Exception as e:
        raise ValueError(f"Unexpected error during transmission decoding: {e}") from e
