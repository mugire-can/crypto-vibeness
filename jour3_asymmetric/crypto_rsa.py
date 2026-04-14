"""
Jour 3: Asymmetric cryptography utilities for E2EE.

Provides RSA key generation, encryption, decryption, and digital signatures.
"""

from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
import os

# Constants
RSA_KEY_SIZE = 2048
RSA_PUBLIC_EXPONENT = 65537


def generate_rsa_keypair() -> tuple:
    """
    Generate RSA 2048-bit keypair for asymmetric encryption and signatures.

    Returns:
        tuple: (private_key, public_key)
    """
    private_key = rsa.generate_private_key(
        public_exponent=RSA_PUBLIC_EXPONENT,
        key_size=RSA_KEY_SIZE,
        backend=default_backend()
    )
    public_key = private_key.public_key()
    return private_key, public_key


def save_private_key(private_key, filepath: str, password: bytes = None) -> None:
    """Save private key to file (encrypted)."""
    encryption_algorithm = (
        serialization.BestAvailableEncryption(password) if password
        else serialization.NoEncryption()
    )
    
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=encryption_algorithm
    )
    
    os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
    with open(filepath, 'wb') as f:
        f.write(pem)
    os.chmod(filepath, 0o600)  # Read/write for owner only


def load_private_key(filepath: str, password: bytes = None):
    """Load private key from file."""
    with open(filepath, 'rb') as f:
        pem = f.read()
    
    return serialization.load_pem_private_key(
        pem,
        password=password,
        backend=default_backend()
    )


def save_public_key(public_key, filepath: str) -> None:
    """Save public key to file (unencrypted)."""
    pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
    with open(filepath, 'wb') as f:
        f.write(pem)


def load_public_key(filepath: str):
    """Load public key from file."""
    with open(filepath, 'rb') as f:
        pem = f.read()
    
    return serialization.load_pem_public_key(
        pem,
        backend=default_backend()
    )


def encrypt_with_public_key(plaintext: bytes, public_key) -> bytes:
    """
    Encrypt plaintext using RSA-OAEP with SHA256.

    Args:
        plaintext: Data to encrypt (max 190 bytes for RSA-2048)
        public_key: RSA public key

    Returns:
        Encrypted bytes
    """
    return public_key.encrypt(
        plaintext,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )


def decrypt_with_private_key(ciphertext: bytes, private_key) -> bytes:
    """
    Decrypt ciphertext using RSA-OAEP with SHA256.

    Args:
        ciphertext: Data to decrypt
        private_key: RSA private key

    Returns:
        Decrypted plaintext bytes
    """
    return private_key.decrypt(
        ciphertext,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )


def sign_message(message: bytes, private_key) -> bytes:
    """
    Sign message with RSA-PSS using SHA256.

    Args:
        message: Message to sign
        private_key: RSA private key

    Returns:
        Digital signature bytes
    """
    return private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )


def verify_signature(message: bytes, signature: bytes, public_key) -> bool:
    """
    Verify digital signature with RSA-PSS using SHA256.

    Args:
        message: Original message
        signature: Digital signature
        public_key: RSA public key

    Returns:
        True if signature valid, False otherwise
    """
    try:
        public_key.verify(
            signature,
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return True
    except Exception:
        return False


def public_key_to_pem(public_key) -> bytes:
    """Convert public key to PEM bytes for transmission."""
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )


def pem_to_public_key(pem_bytes: bytes):
    """Convert PEM bytes to public key object."""
    return serialization.load_pem_public_key(
        pem_bytes,
        backend=default_backend()
    )
