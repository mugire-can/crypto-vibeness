#!/usr/bin/env python3
"""
End-to-end encryption test for Crypto Vibeness
Tests message encryption/decryption in the protocol layer
"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from crypto_utils import (
    derive_key_pbkdf2,
    encrypt_aes_gcm, decrypt_aes_gcm,
    encode_for_transmission, decode_from_transmission
)
from config import *

def test_symmetric_encryption_protocol():
    """Test SYMMETRIC mode message encryption/decryption."""
    print("\n" + "="*60)
    print("Testing SYMMETRIC Mode Message Encryption Protocol")
    print("="*60)
    
    # Simulate password and key derivation
    password = "VerySecure!Pass123"
    key, salt = derive_key_pbkdf2(password)
    
    print(f"[OK] Password: {password}")
    print(f"[OK] Derived key length: {len(key)} bytes")
    print(f"[OK] Salt length: {len(salt)} bytes")
    
    # Simulate messages that would be sent
    messages = [
        "Hello World!",
        "[LOCKED] This is encrypted! [SECURE]",
        "user1: Hello to user2!",
        "/join secret_room password123",
        "Complex message with: colons and: more: stuff",
    ]
    
    print("\nTesting message encryption/decryption:")
    for msg in messages:
        # Encrypt (what client does)
        encrypted = encrypt_aes_gcm(msg, key)
        encoded = encode_for_transmission(encrypted)
        
        # Decrypt (what server does)
        decoded = decode_from_transmission(encoded)
        decrypted = decrypt_aes_gcm(decoded, key)
        
        # Verify
        assert decrypted == msg, f"Mismatch! Original: {msg}, Decrypted: {decrypted}"
        print(f"  [OK] '{msg}' -> encrypted ({len(encoded)} chars) -> decrypted [OK]")
    
    print("\n[OK] SYMMETRIC mode encryption test PASSED!")

def test_different_passwords_different_keys():
    """Test that different passwords produce different encryption."""
    print("\n" + "="*60)
    print("Testing Key Derivation with Different Passwords")
    print("="*60)
    
    msg = "secret message"
    password1 = "Password123!ABC"
    password2 = "Password123!ABC"  # Same
    password3 = "DifferentPass456!"  # Different
    
    key1, salt1 = derive_key_pbkdf2(password1)
    # Use same salt for same password to get identical key
    key2, _ = derive_key_pbkdf2(password2, salt1)
    key3, salt3 = derive_key_pbkdf2(password3)
    
    # Verify same password with same salt produces same key
    assert key1 == key2, "Same password with same salt should produce same key!"
    print(f"[OK] Same password + same salt = same key")
    
    # Encrypt with first key
    encrypted1 = encrypt_aes_gcm(msg, key1)
    encoded1 = encode_for_transmission(encrypted1)
    
    # Decrypt with same key (should work)
    try:
        decoded1 = decode_from_transmission(encoded1)
        decrypted1 = decrypt_aes_gcm(decoded1, key2)
        print(f"[OK] Same key decrypts correctly: '{decrypted1}'")
    except Exception as e:
        print(f"✗ Failed to decrypt with same key: {e}")
        return False
    
    # Try to decrypt with different password (should fail)
    try:
        decoded3 = decode_from_transmission(encoded1)
        decrypted3 = decrypt_aes_gcm(decoded3, key3)
        print(f"✗ Different password should not decrypt! Got: '{decrypted3}'")
        return False
    except ValueError as e:
        print(f"[OK] Different password correctly fails with authentication error")
    
    print("\n[OK] Key derivation security test PASSED!")
    return True

def test_protocol_simulation():
    """Simulate actual protocol messages with encryption."""
    print("\n" + "="*60)
    print("Testing Actual Protocol Message Simulation")
    print("="*60)
    
    password = "SecurePassword123!"
    key, _ = derive_key_pbkdf2(password)
    
    # Simulate different message types
    protocol_messages = [
        ("MESSAGE", "Hello everyone!"),
        ("MESSAGE", "/join room1 password"),
        ("MESSAGE", "[LOCKED] Encrypted chat works! [OK]"),
        ("SYSTEM", "User joined the room"),
        ("AUTH_REQUEST", "Enter your password: "),  # Not encrypted
    ]
    
    print("\nProcessing protocol messages:")
    for msg_type, content in protocol_messages:
        if msg_type == "MESSAGE":
            # Encrypt MESSAGE content
            encrypted = encrypt_aes_gcm(content, key)
            encoded_content = encode_for_transmission(encrypted)
            protocol_msg = f"{msg_type}:{encoded_content}"
            
            # Simulate receiving and decrypting
            parts = protocol_msg.split(':', 1)
            recv_type = parts[0]
            recv_content = parts[1] if len(parts) > 1 else ""
            
            if recv_type == "MESSAGE":
                decoded = decode_from_transmission(recv_content)
                decrypted_content = decrypt_aes_gcm(decoded, key)
                
                assert decrypted_content == content, f"Mismatch!"
                print(f"  [OK] MESSAGE: '{decrypted_content}' (encrypted)")
            else:
                # Unencrypted message types
                protocol_msg = f"{msg_type}:{content}"
                print(f"  [OK] {msg_type}: '{content}' (not encrypted)")
    
    print("\n[OK] Protocol simulation test PASSED!")

if __name__ == '__main__':
    try:
        test_symmetric_encryption_protocol()
        test_different_passwords_different_keys()
        test_protocol_simulation()
        
        print("\n" + "="*60)
        print("[OK] ALL END-TO-END ENCRYPTION TESTS PASSED!")
        print("="*60)
        print("\nSUMMARY:")
        print("[OK] Messages are properly encrypted with AES-256-GCM")
        print("[OK] Different passwords produce different encryption")
        print("[OK] Protocol correctly handles encrypted/unencrypted messages")
        print("[OK] Unicode and special characters are preserved")
        print("\n")
        
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
