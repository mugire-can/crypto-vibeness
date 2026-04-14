# Jour 2 - Cryptographie Symétrique

## Overview

**Jour 2** adds symmetric encryption (AES-256) to the chat system. Messages are now encrypted before being sent, and the server cannot read their content.

## Architecture Changes

### Phase Comparison

**Jour 1 (YOLO):**
```
Client → [plaintext message] → Server → Logs: "alice: hello"
```

**Jour 2 (Symmetric Crypto):**
```
Client → [AES-256 ciphertext] → Server → Logs: "alice: [encrypted_blob]"
```

## Cryptographic Components

### 1. Key Derivation (PBKDF2)
- **Input:** User password
- **Output:** 256-bit key for AES-256
- **Algorithm:** PBKDF2-HMAC-SHA256
- **Iterations:** 480,000 (NIST recommendation)
- **Salt:** 16 random bytes

### 2. Symmetric Encryption (AES-256)
- **Algorithm:** AES-256 in CBC mode
- **Key Size:** 256 bits (32 bytes)
- **IV:** 16 random bytes per message
- **Block Size:** 128 bits

### 3. Message Authentication (HMAC-SHA256)
- **Algorithm:** HMAC-SHA256
- **Purpose:** Detect tampering
- **Verification:** Before decryption (fail-safe)
- **Constant-time comparison:** Prevent timing attacks

### 4. Transmission Encoding
- **Format:** Base64(IV):Base64(ciphertext+HMAC)
- **Why:** Safe transmission over text-based protocol

## Files to Create

### jour2_crypto/crypto_utils.py
Central cryptography utilities module with:
- `derive_key_from_password()` - PBKDF2
- `encrypt_message()` - AES-256-CBC with HMAC
- `decrypt_message()` - Verify & decrypt
- `encode_for_transmission()` - Base64 encoding
- `decode_from_transmission()` - Base64 decoding

### jour2_crypto/server.py
Modified server with encryption:
- Import crypto_utils
- Add password configuration
- Encrypt all outgoing messages
- Decrypt all incoming messages
- Log encrypted content only

### jour2_crypto/client.py
Modified client with encryption:
- Import crypto_utils
- Password negotiation with server
- Encrypt all outgoing messages
- Decrypt all incoming messages
- Display plaintext to user

### jour2_crypto/config.py
Configuration for symmetric crypto:
- PBKDF2 iterations
- Key derivation salt length
- Encryption algorithm names
- Buffer sizes

## Implementation Steps

### Step 1: Crypto Module (crypto_utils.py)
- Create encryption/decryption functions
- Implement PBKDF2 key derivation
- Add HMAC verification
- Test with sample data

### Step 2: Update Server (server.py)
- Add password setup
- Encrypt messages before broadcasting
- Decrypt incoming messages
- Verify HMAC on all messages

### Step 3: Update Client (client.py)
- Add password input
- Encrypt before sending
- Decrypt after receiving
- Same user interface (transparently encrypted)

### Step 4: Testing
- Test encryption/decryption roundtrip
- Multi-client with same password
- Verify server logs show ciphertext
- Verify clients see plaintext

## Message Flow

### Encryption on Send (Client)
1. User types: "hello everyone"
2. Client derives key from password
3. Client generates random IV
4. Client encrypts with AES-256: ciphertext = AES_encrypt(message, key, iv)
5. Client creates HMAC: hmac = HMAC_SHA256(ciphertext, key)
6. Client encodes: transmission = Base64(iv):Base64(ciphertext+hmac)
7. Client sends to server

### Server Receives
1. Server receives encrypted blob
2. Server cannot decrypt (doesn't have password)
3. Server logs encrypted blob
4. Server broadcasts encrypted blob to all other clients

### Decryption on Receive (Client)
1. Receiving client gets: Base64(iv):Base64(ciphertext+hmac)
2. Client decodes: extracts iv, ciphertext, hmac
3. Client verifies: hmac_verify(ciphertext, key) - if fails, reject message
4. Client decrypts: plaintext = AES_decrypt(ciphertext, key, iv)
5. Client displays plaintext to user

## Security Properties

✅ **Confidentiality**
- Messages encrypted with AES-256
- Server cannot read message content
- Only clients with password can decrypt

✅ **Integrity**
- HMAC-SHA256 detects tampering
- Verified before decryption
- Fails safely if MAC invalid

✅ **Key Derivation**
- PBKDF2 with 480,000 iterations
- Resists brute-force attacks
- 16-byte salt prevents rainbow tables

⚠️ **Limitations (Intentional for Learning)**
- No forward secrecy (key never changes)
- No key rotation
- No perfect forward secrecy
- Same key for all messages
- Server can see who talks to whom (metadata)

## Validation Checklist

- [ ] Crypto module encrypts/decrypts correctly
- [ ] HMAC verification works
- [ ] Key derivation from password works
- [ ] Server logs show only ciphertext
- [ ] Clients can decrypt with correct password
- [ ] Wrong password fails decryption
- [ ] Multi-client communication works
- [ ] Message integrity verified
- [ ] No plaintext in server logs
- [ ] Performance acceptable

## Testing Strategy

### Unit Tests
```python
# Test key derivation
key1, salt = derive_key_from_password("password123")
key2 = derive_key_from_password("password123", salt)
assert key1 == key2  # Same password + salt = same key

# Test encryption/decryption
plaintext = "Hello world!"
ciphertext, iv = encrypt_message(plaintext, key)
decrypted = decrypt_message(ciphertext, iv, key)
assert decrypted == plaintext  # Roundtrip works

# Test HMAC failure
tampered = tamper_with_ciphertext(ciphertext)
try:
    decrypt_message(tampered, iv, key)
    assert False  # Should fail
except ValueError:
    pass  # Expected
```

### Integration Tests
1. Start server with password "test123"
2. Connect 2 clients with same password
3. Send messages between clients
4. Check server logs show only [encrypted_blob]
5. Verify both clients see plaintext

## Performance Considerations

- PBKDF2: ~200-300ms per password (acceptable on startup)
- AES-256 encryption: ~0.1-1ms per message
- HMAC verification: <1ms per message
- Overall latency: Similar to Jour 1

## Next Phase (Jour 3)

Jour 3 will add:
- RSA asymmetric encryption for key exchange
- Per-user key pairs (public/private)
- Eliminate need for shared password
- 1-1 conversations with end-to-end encryption
- Digital signatures for authentication

---

**Status:** Ready to implement
**Dependencies:** cryptography library (installed)
**Timeline:** Start with crypto_utils.py, then update server/client
