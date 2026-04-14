# Jour 3 - Cryptographie Asymétrique & Chiffrement de Bout en Bout

## Overview

**Jour 3** removes the need for shared passwords by implementing:
1. **RSA asymmetric cryptography** for key exchange
2. **Hybrid encryption** (RSA for key exchange, AES for messages)
3. **End-to-end encryption (E2EE)** where server cannot read messages
4. **Digital signatures** for message authentication

## Architecture Phases

### Phase 1: Key Generation (Partie 1)
- Each client generates RSA 2048-bit key pair
- Public key stored in ~/.crypto_vibeness/username.pub
- Private key stored in ~/.crypto_vibeness/username.priv

### Phase 2: Hybrid Encryption (Partie 2)
- Client still uses shared password for initial encryption (like Jour 2)
- OR: Each client generates random symmetric key
- Uses RSA to exchange symmetric key with server
- Server broadcasts to other clients
- Other clients decrypt session key with their private key

### Phase 3: E2EE Setup (Parties 3-4)
- Server maintains public key registry {username: public_key}
- When Alice sends to Bob:
  1. Alice gets Bob's public key from server
  2. Alice generates random session key
  3. Alice encrypts session key with Bob's RSA public key
  4. Alice sends: RSA_encrypted_session_key to server
  5. Server forwards to Bob
  6. Bob decrypts session key with his RSA private key

### Phase 4: Message Encryption & Signatures (Parties 5-6)
- Alice and Bob now share session key
- All messages encrypted with session key (AES-256)
- Each message signed with sender's private key
- Receiver verifies signature with sender's public key
- Server cannot read or tamper with messages

## Cryptographic Components

### RSA Asymmetric Encryption
- **Key Size:** 2048 bits
- **Format:** PKCS#8 for private keys, X.509 for public keys
- **Padding:** OAEP with SHA256
- **Use:** Key exchange, digital signatures

### AES Session Keys
- **Generation:** Random 32 bytes per conversation
- **Encryption:** AES-256-CBC (same as Jour 2)
- **Transport:** Encrypted with RSA

### Digital Signatures
- **Algorithm:** RSA-PSS with SHA256
- **Size:** 256 bytes per signature
- **Verification:** Constant-time comparison

## Files to Create

### jour3_asymmetric/crypto_rsa.py
RSA asymmetric utilities:
- `generate_rsa_keypair()` - Generate 2048-bit RSA keys
- `load_private_key(filename)` - Load private key from file
- `load_public_key(filename)` - Load public key from file
- `save_private_key(key, filename)` - Save private key encrypted
- `save_public_key(key, filename)` - Save public key
- `encrypt_with_public_key(plaintext, public_key)` - RSA encryption
- `decrypt_with_private_key(ciphertext, private_key)` - RSA decryption
- `sign_message(message, private_key)` - Create digital signature
- `verify_signature(message, signature, public_key)` - Verify signature

### jour3_asymmetric/server.py
Enhanced server with E2EE:
- Maintain public key registry {username: public_key}
- Handle key distribution requests
- Forward encrypted session keys
- Broadcast encrypted messages (cannot read)
- Verify message signatures

### jour3_asymmetric/client.py
Enhanced client with E2EE:
- Generate RSA key pair on first run
- Request other users' public keys
- Establish 1-1 encrypted conversations
- Sign all outgoing messages
- Verify all incoming message signatures

### jour3_asymmetric/crypto_utils.py
Copied from Jour 2 (for AES encryption of session keys in-transit)

## Implementation Steps

### Step 1: RSA Module
- Implement key generation (2048-bit)
- File persistence (encrypted private keys)
- Encryption/decryption with RSA
- Digital signatures

### Step 2: Server with E2EE
- Add public key registry
- Distribute public keys to clients
- Route encrypted session keys
- Handle 1-1 conversations

### Step 3: Client with E2EE
- Generate RSA keys
- Request public keys
- Establish session keys
- Sign/verify messages

### Step 4: Testing
- Key generation and persistence
- Signature verification
- E2EE message encryption
- Server cannot read messages

## Security Properties

✅ **Forward Secrecy**
- Each conversation has unique session key
- Lost session key doesn't compromise others
- Past conversations remain secret

✅ **Authenticity**
- Digital signatures prove message origin
- Receiver verifies sender identity
- Tampering detected immediately

✅ **Confidentiality**
- Server cannot read E2EE messages
- Only sender and recipient can decrypt
- RSA protects session key distribution

✅ **Integrity**
- HMAC on encrypted messages
- Digital signatures on plaintext
- Dual authentication mechanisms

⚠️ **Limitations (Learning Only)**
- No forward secrecy for session key itself
- Key compromise leaks all session conversations
- No key rotation or perfect forward secrecy
- Signature doesn't include timestamp

## Message Flow: E2EE Conversation

**Alice sends to Bob:**

1. Alice requests Bob's public key from server
2. Alice generates random 32-byte session key
3. Alice encrypts session key: `encrypted_sk = RSA_encrypt(session_key, bob_pub_key)`
4. Alice sends to server: `[ESTABLISH_SESSION][bob_username][encrypted_sk]`
5. Server forwards to Bob (cannot decrypt)
6. Bob decrypts: `session_key = RSA_decrypt(encrypted_sk, bob_priv_key)`

**Alice sends message to Bob:**

1. Alice creates message: `"hello bob"`
2. Alice signs: `sig = RSA_sign(message, alice_priv_key)`
3. Alice encrypts: `msg_ct = AES_encrypt(message, session_key)`
4. Alice sends: `[MSG][bob][msg_ct][sig]`
5. Server logs: `alice -> bob: [encrypted]`
6. Bob receives, decrypts message
7. Bob verifies: `RSA_verify(message, sig, alice_pub_key)`
8. Bob displays decrypted message

## Validation Checklist

- [ ] RSA keypair generation works
- [ ] Keys persist to disk
- [ ] Keys load from disk correctly
- [ ] RSA encryption/decryption roundtrip works
- [ ] Digital signatures verify correctly
- [ ] Tampered signatures fail verification
- [ ] Server doesn't have private keys
- [ ] Public keys distribute correctly
- [ ] Session keys established per conversation
- [ ] E2EE messages work 1-1
- [ ] Server logs show only [encrypted]
- [ ] Message signatures prevent tampering

## Testing Strategy

### Unit Tests (crypto_rsa.py)
- Generate keys
- Encrypt/decrypt
- Sign/verify
- Tamper detection

### Integration Tests
1. Start server
2. Client A generates keys
3. Client B generates keys
4. A and B exchange public keys
5. A sends encrypted message to B
6. B verifies signature and decrypts
7. Server logs show [encrypted] only

### Security Tests
1. Tamper with ciphertext - should fail MAC
2. Tamper with signature - should fail verification
3. Use wrong private key - decryption fails
4. Server tries to read message - cannot decrypt

## Next Steps

After Jour 3:
- Project is cryptographically complete
- Support real-world security properties
- Ready for production use (with warnings)
- Ready for security audit

---

**Status:** Ready to implement
**Dependencies:** cryptography library (already installed)
**Components:** RSA 2048, AES-256, HMAC-SHA256, RSA-PSS signatures
