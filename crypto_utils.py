"""
Unified Cryptography Utilities for Crypto Vibeness
Supports: MD5 (YOLO), AES-256-CBC/GCM (Symmetric), RSA (Asymmetric), ECDH/ECDSA (Modern)
"""

import hashlib
import hmac
import base64
import os
import json
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding, utils
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidTag
import struct

try:
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
    from cryptography.hazmat.primitives.asymmetric.ec import (
        EllipticCurvePrivateKey, EllipticCurvePublicKey,
        SECP256R1, ECDSA
    )
except ImportError:
    pass

from config import *

# ============================================================================
# JOUR 1: MD5 HASHING (YOLO - Intentionally Weak)
# ============================================================================

def hash_password_md5(password: str) -> str:
    """
    Hash password with MD5 and return base64-encoded digest.
    ⚠️  WARNING: MD5 is cryptographically broken. Only for educational purposes.
    """
    digest = hashlib.md5(password.encode(ENCODING)).digest()
    return base64.b64encode(digest).decode("ascii")


def verify_password_md5(password: str, stored_hash: str) -> bool:
    """Verify MD5 password using constant-time comparison."""
    computed_hash = hash_password_md5(password)
    return hmac.compare_digest(computed_hash, stored_hash)


# ============================================================================
# JOUR 2+: MODERN PASSWORD HASHING (Argon2 or Scrypt)
# ============================================================================

def derive_key_pbkdf2(password: str, salt: bytes = None, iterations: int = PBKDF2_ITERATIONS) -> tuple:
    """
    Derive AES key from password using PBKDF2-SHA256.
    Returns: (key_bytes, salt_bytes)
    """
    if salt is None:
        salt = os.urandom(PBKDF2_SALT_LENGTH)
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=AES_KEY_SIZE,
        salt=salt,
        iterations=iterations,
    )
    key = kdf.derive(password.encode(ENCODING))
    return key, salt


def hash_password_modern(password: str, salt: bytes = None) -> tuple:
    """
    Hash password with Argon2/ScryptKey derivation.
    Returns: (hash_b64, salt_b64, algorithm_name, cost_factor)
    """
    try:
        from argon2 import PasswordHasher
        ph = PasswordHasher()
        hash_result = ph.hash(password)
        # Argon2 includes salt in the hash
        return hash_result, None, 'argon2', 3
    except ImportError:
        # Fallback to PBKDF2
        key, salt = derive_key_pbkdf2(password, salt)
        key_b64 = base64.b64encode(key).decode('ascii')
        salt_b64 = base64.b64encode(salt).decode('ascii')
        return key_b64, salt_b64, 'pbkdf2', PBKDF2_ITERATIONS


def verify_password_modern(password: str, stored_hash: str, salt_b64: str = None, 
                          algorithm: str = 'pbkdf2') -> bool:
    """Verify modern password hash."""
    if algorithm == 'argon2':
        try:
            from argon2 import PasswordHasher
            from argon2.exceptions import VerifyMismatchError
            ph = PasswordHasher()
            try:
                ph.verify(stored_hash, password)
                return True
            except VerifyMismatchError:
                return False
        except ImportError:
            return False
    else:
        # PBKDF2 verification
        salt = base64.b64decode(salt_b64) if salt_b64 else os.urandom(PBKDF2_SALT_LENGTH)
        key, _ = derive_key_pbkdf2(password, salt)
        stored_key = base64.b64decode(stored_hash)
        return hmac.compare_digest(key, stored_key)


# ============================================================================
# JOUR 2: AES-256 ENCRYPTION (Symmetric)
# ============================================================================

def encrypt_aes_cbc(plaintext: str, key: bytes) -> bytes:
    """
    Encrypt with AES-256-CBC + HMAC authentication.
    Returns: nonce || ciphertext || tag (suitable for transmission)
    """
    if not isinstance(plaintext, str):
        raise TypeError("Plaintext must be a string")
    
    if len(key) != AES_KEY_SIZE:
        raise ValueError(f"Key must be {AES_KEY_SIZE} bytes")
    
    # Generate random IV
    iv = os.urandom(AES_BLOCK_SIZE)
    
    # Encrypt
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    
    # PKCS7 padding
    plaintext_bytes = plaintext.encode(ENCODING)
    padding_length = AES_BLOCK_SIZE - (len(plaintext_bytes) % AES_BLOCK_SIZE)
    plaintext_bytes += bytes([padding_length] * padding_length)
    
    ciphertext = encryptor.update(plaintext_bytes) + encryptor.finalize()
    
    # HMAC for authentication
    h = hmac.new(key, iv + ciphertext, hashlib.sha256)
    tag = h.digest()
    
    return iv + ciphertext + tag


def decrypt_aes_cbc(ciphertext_blob: bytes, key: bytes) -> str:
    """
    Decrypt AES-256-CBC message (with HMAC verification).
    Expects format: nonce || ciphertext || tag
    """
    if len(key) != AES_KEY_SIZE:
        raise ValueError(f"Key must be {AES_KEY_SIZE} bytes")
    
    # Extract components
    iv = ciphertext_blob[:AES_BLOCK_SIZE]
    tag = ciphertext_blob[-32:]  # SHA256 = 32 bytes
    ciphertext = ciphertext_blob[AES_BLOCK_SIZE:-32]
    
    # Verify HMAC
    h = hmac.new(key, iv + ciphertext, hashlib.sha256)
    expected_tag = h.digest()
    
    if not hmac.compare_digest(tag, expected_tag):
        raise ValueError("Authentication tag verification failed")
    
    # Decrypt
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    plaintext_bytes = decryptor.update(ciphertext) + decryptor.finalize()
    
    # Remove PKCS7 padding
    padding_length = plaintext_bytes[-1]
    plaintext_bytes = plaintext_bytes[:-padding_length]
    
    return plaintext_bytes.decode(ENCODING)


def encrypt_aes_gcm(plaintext: str, key: bytes, aad: bytes = None) -> bytes:
    """
    Encrypt with AES-256-GCM (AEAD - includes authentication).
    Returns: nonce || ciphertext || tag
    """
    if not isinstance(plaintext, str):
        raise TypeError("Plaintext must be a string")
    
    if len(key) != AES_KEY_SIZE:
        raise ValueError(f"Key must be {AES_KEY_SIZE} bytes")
    
    nonce = os.urandom(12)  # 96 bits for GCM
    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce))
    encryptor = cipher.encryptor()
    
    if aad:
        encryptor.authenticate_additional_data(aad)
    
    plaintext_bytes = plaintext.encode(ENCODING)
    ciphertext = encryptor.update(plaintext_bytes) + encryptor.finalize()
    
    return nonce + ciphertext + encryptor.tag


def decrypt_aes_gcm(ciphertext_blob: bytes, key: bytes, aad: bytes = None) -> str:
    """
    Decrypt AES-256-GCM message.
    Expects format: nonce || ciphertext || tag
    """
    if len(key) != AES_KEY_SIZE:
        raise ValueError(f"Key must be {AES_KEY_SIZE} bytes")
    
    nonce = ciphertext_blob[:12]
    tag = ciphertext_blob[-16:]  # GCM tag is 16 bytes
    ciphertext = ciphertext_blob[12:-16]
    
    cipher = Cipher(algorithms.AES(key), modes.GCM(nonce, tag))
    decryptor = cipher.decryptor()
    
    if aad:
        decryptor.authenticate_additional_data(aad)
    
    try:
        plaintext_bytes = decryptor.update(ciphertext) + decryptor.finalize()
    except InvalidTag:
        raise ValueError("Authentication tag verification failed - ciphertext or AAD corrupted")
    return plaintext_bytes.decode(ENCODING)


# ============================================================================
# JOUR 3: RSA ENCRYPTION (Asymmetric)
# ============================================================================

def generate_rsa_keypair() -> tuple:
    """Generate RSA-2048 keypair. Returns: (private_key, public_key)"""
    private_key = rsa.generate_private_key(
        public_exponent=RSA_PUBLIC_EXPONENT,
        key_size=RSA_KEY_SIZE,
    )
    return private_key, private_key.public_key()


def rsa_encrypt(public_key, plaintext: str) -> bytes:
    """Encrypt with RSA-OAEP."""
    plaintext_bytes = plaintext.encode(ENCODING)
    return public_key.encrypt(
        plaintext_bytes,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )


def rsa_decrypt(private_key, ciphertext: bytes) -> str:
    """Decrypt with RSA-OAEP."""
    plaintext_bytes = private_key.decrypt(
        ciphertext,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return plaintext_bytes.decode(ENCODING)


def rsa_sign(private_key, message: str) -> bytes:
    """Sign with RSA-PSS."""
    message_bytes = message.encode(ENCODING)
    return private_key.sign(
        message_bytes,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )


def rsa_verify(public_key, message: str, signature: bytes) -> bool:
    """Verify RSA-PSS signature."""
    try:
        message_bytes = message.encode(ENCODING)
        public_key.verify(
            signature,
            message_bytes,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return True
    except:
        return False


def save_rsa_private_key(private_key, filepath: str):
    """Save RSA private key to PEM file."""
    with open(filepath, 'wb') as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))


def load_rsa_private_key(filepath: str):
    """Load RSA private key from PEM file."""
    with open(filepath, 'rb') as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def save_rsa_public_key(public_key, filepath: str):
    """Save RSA public key to PEM file."""
    with open(filepath, 'wb') as f:
        f.write(public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ))


def load_rsa_public_key(filepath: str):
    """Load RSA public key from PEM file."""
    with open(filepath, 'rb') as f:
        return serialization.load_pem_public_key(f.read())


def public_key_to_pem(public_key) -> str:
    """Convert public key to PEM string."""
    pem_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return pem_bytes.decode('ascii')


def pem_to_public_key(pem_string: str):
    """Convert PEM string to public key object."""
    return serialization.load_pem_public_key(pem_string.encode('ascii'))


# ============================================================================
# JOUR 4: ECDH + ECDSA (Modern Cryptography)
# ============================================================================

def generate_ecdh_keypair():
    """Generate X25519 keypair for ECDH."""
    private_key = X25519PrivateKey.generate()
    return private_key, private_key.public_key()


def ecdh_shared_secret(private_key, peer_public_key) -> bytes:
    """Derive shared secret using ECDH."""
    return private_key.exchange(peer_public_key)


def derive_session_key_from_secret(shared_secret: bytes, salt: bytes = None) -> bytes:
    """Convert ECDH shared secret to AES key using HKDF."""
    if salt is None:
        salt = HKDF_SALT
    
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=AES_KEY_SIZE,
        salt=salt,
        info=b'session-key'
    )
    return hkdf.derive(shared_secret)


def generate_ecdsa_keypair():
    """Generate ECDSA P-256 keypair for signing."""
    from cryptography.hazmat.primitives.asymmetric import ec
    private_key = ec.generate_private_key(SECP256R1())
    return private_key, private_key.public_key()


def ecdsa_sign(private_key, message: str) -> bytes:
    """Sign with ECDSA P-256."""
    message_bytes = message.encode(ENCODING)
    return private_key.sign(message_bytes, ECDSA(hashes.SHA256()))


def ecdsa_verify(public_key, message: str, signature: bytes) -> bool:
    """Verify ECDSA signature."""
    try:
        message_bytes = message.encode(ENCODING)
        public_key.verify(signature, message_bytes, ECDSA(hashes.SHA256()))
        return True
    except:
        return False


# ============================================================================
# MESSAGE PROTOCOL HELPERS
# ============================================================================

def encode_for_transmission(ciphertext: bytes) -> str:
    """Encode ciphertext for safe transmission (base64)."""
    return base64.b64encode(ciphertext).decode('ascii')


def decode_from_transmission(encoded: str) -> bytes:
    """Decode base64-encoded message."""
    return base64.b64decode(encoded)


def pack_message_tuple(msg_type: str, data: bytes) -> bytes:
    """Pack message with type prefix and length."""
    msg_type_bytes = msg_type.encode('ascii')
    type_len = len(msg_type_bytes)
    data_len = len(data)
    
    # Format: [type_len (1 byte)][type][data_len (4 bytes)][data]
    return struct.pack('B', type_len) + msg_type_bytes + struct.pack('I', data_len) + data


def unpack_message_tuple(blob: bytes) -> tuple:
    """Unpack message type and data."""
    type_len = struct.unpack('B', blob[:1])[0]
    type_bytes = blob[1:1+type_len]
    msg_type = type_bytes.decode('ascii')
    data_len_offset = 1 + type_len
    data_len = struct.unpack('I', blob[data_len_offset:data_len_offset+4])[0]
    data = blob[data_len_offset+4:data_len_offset+4+data_len]
    return msg_type, data
