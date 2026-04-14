"""
Jour 4: Elliptic-Curve Cryptography utilities.

Provides:
- ECDH key exchange (X25519) for forward-secure session key establishment
- ECDSA (P-256 / secp256r1) digital signatures
- AES-256-GCM authenticated encryption
- HKDF-SHA256 key derivation from shared secrets
- Helpers for PEM serialisation / deserialisation

Why elliptic curves vs RSA?
- Smaller keys for equivalent security: 256-bit EC ≈ 3072-bit RSA
- Faster key generation and signature operations
- X25519 enables *ephemeral* key exchange → Perfect Forward Secrecy (PFS)
"""

import os
import base64

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.asymmetric.ec import (
    SECP256R1, generate_private_key as ec_generate_private_key,
    ECDSA, EllipticCurvePrivateKey, EllipticCurvePublicKey,
)
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature

# AES-GCM constants
GCM_NONCE_SIZE = 12   # 96-bit nonce
GCM_TAG_SIZE = 16     # 128-bit authentication tag
AES_KEY_SIZE = 32     # AES-256


# ---------------------------------------------------------------------------
# X25519 ECDH – ephemeral key exchange (Perfect Forward Secrecy)
# ---------------------------------------------------------------------------

def generate_x25519_keypair() -> tuple[X25519PrivateKey, X25519PublicKey]:
    """Generate an X25519 ephemeral keypair for ECDH key exchange.

    Returns:
        (private_key, public_key)
    """
    private_key = X25519PrivateKey.generate()
    return private_key, private_key.public_key()


def x25519_public_key_to_bytes(public_key: X25519PublicKey) -> bytes:
    """Serialise an X25519 public key to raw bytes (32 bytes)."""
    return public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def x25519_public_key_from_bytes(raw: bytes) -> X25519PublicKey:
    """Deserialise an X25519 public key from raw bytes."""
    return X25519PublicKey.from_public_bytes(raw)


def ecdh_derive_session_key(
    private_key: X25519PrivateKey,
    peer_public_key: X25519PublicKey,
    info: bytes = b'crypto-vibeness-jour4',
) -> bytes:
    """
    Derive a 32-byte AES session key from an X25519 ECDH exchange.

    Uses HKDF-SHA256 to stretch the raw Diffie-Hellman shared secret into a
    cryptographically strong key.  The *info* parameter binds the key to this
    application (domain separation).

    Args:
        private_key: Our X25519 private key.
        peer_public_key: The other party's X25519 public key.
        info: Application-specific context string (optional).

    Returns:
        32-byte AES-256 session key.
    """
    raw_shared_secret = private_key.exchange(peer_public_key)

    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=AES_KEY_SIZE,
        salt=None,
        info=info,
        backend=default_backend(),
    )
    return hkdf.derive(raw_shared_secret)


# ---------------------------------------------------------------------------
# ECDSA (P-256) – digital signatures
# ---------------------------------------------------------------------------

def generate_ecdsa_keypair() -> tuple[EllipticCurvePrivateKey, EllipticCurvePublicKey]:
    """Generate a P-256 (secp256r1) ECDSA keypair for signing.

    Returns:
        (private_key, public_key)
    """
    private_key = ec_generate_private_key(SECP256R1(), default_backend())
    return private_key, private_key.public_key()


def ecdsa_public_key_to_pem(public_key: EllipticCurvePublicKey) -> bytes:
    """Serialise an ECDSA public key to PEM bytes."""
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def ecdsa_public_key_from_pem(pem: bytes) -> EllipticCurvePublicKey:
    """Deserialise an ECDSA public key from PEM bytes."""
    return serialization.load_pem_public_key(pem, backend=default_backend())


def ecdsa_sign(message: bytes, private_key: EllipticCurvePrivateKey) -> bytes:
    """Sign *message* with ECDSA/P-256/SHA-256.

    Args:
        message: Raw bytes to sign.
        private_key: ECDSA private key.

    Returns:
        DER-encoded signature bytes.
    """
    return private_key.sign(message, ECDSA(hashes.SHA256()))


def ecdsa_verify(message: bytes, signature: bytes, public_key: EllipticCurvePublicKey) -> bool:
    """Verify an ECDSA/P-256/SHA-256 signature.

    Args:
        message: Original message bytes.
        signature: DER-encoded signature bytes.
        public_key: Signer's ECDSA public key.

    Returns:
        True if valid, False if invalid.
    """
    try:
        public_key.verify(signature, message, ECDSA(hashes.SHA256()))
        return True
    except InvalidSignature:
        return False


# ---------------------------------------------------------------------------
# AES-256-GCM – authenticated encryption
# ---------------------------------------------------------------------------

def aes_gcm_encrypt(plaintext: str, key: bytes) -> tuple[bytes, bytes]:
    """Encrypt *plaintext* with AES-256-GCM (AEAD).

    Args:
        plaintext: UTF-8 string to encrypt.
        key: 32-byte AES-256 key.

    Returns:
        (ciphertext_with_tag, nonce):
            - ciphertext_with_tag: ciphertext || 16-byte GCM tag
            - nonce: 12-byte random nonce
    """
    if not isinstance(key, bytes) or len(key) != AES_KEY_SIZE:
        raise ValueError(f"Key must be {AES_KEY_SIZE} bytes for AES-256-GCM")

    nonce = os.urandom(GCM_NONCE_SIZE)
    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(plaintext.encode('utf-8')) + encryptor.finalize()

    return ciphertext + encryptor.tag, nonce


def aes_gcm_decrypt(encrypted_data: bytes, nonce: bytes, key: bytes) -> str:
    """Decrypt an AES-256-GCM ciphertext.

    Args:
        encrypted_data: ciphertext || 16-byte GCM tag.
        nonce: 12-byte nonce used during encryption.
        key: 32-byte AES-256 key.

    Returns:
        Decrypted UTF-8 string.

    Raises:
        ValueError: If authentication fails (data tampered) or inputs are invalid.
    """
    if not isinstance(key, bytes) or len(key) != AES_KEY_SIZE:
        raise ValueError(f"Key must be {AES_KEY_SIZE} bytes for AES-256-GCM")
    if not isinstance(nonce, bytes) or len(nonce) != GCM_NONCE_SIZE:
        raise ValueError(f"Nonce must be {GCM_NONCE_SIZE} bytes")
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
        raise ValueError("GCM authentication failed — data may have been tampered with") from exc

    return plaintext.decode('utf-8')


# ---------------------------------------------------------------------------
# Transmission helpers
# ---------------------------------------------------------------------------

def encode_for_transmission(ciphertext: bytes, nonce: bytes) -> str:
    """Base64-encode nonce and ciphertext for JSON transmission.

    Returns:
        "base64(nonce):base64(ciphertext)"
    """
    return (
        base64.b64encode(nonce).decode('ascii')
        + ':'
        + base64.b64encode(ciphertext).decode('ascii')
    )


def decode_from_transmission(encoded: str) -> tuple[bytes, bytes]:
    """Decode a transmission string produced by encode_for_transmission.

    Returns:
        (ciphertext_bytes, nonce_bytes)
    """
    parts = encoded.split(':')
    if len(parts) != 2:
        raise ValueError("Invalid transmission format")
    nonce = base64.b64decode(parts[0])
    ciphertext = base64.b64decode(parts[1])
    return ciphertext, nonce
