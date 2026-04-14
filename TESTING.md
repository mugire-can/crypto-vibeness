# 🧪 Crypto Vibeness - Testing & Validation Guide

## Code Compilation Verification

All Python files compile successfully with no syntax errors:

```bash
python -m py_compile jour1_yolo/server.py
python -m py_compile jour1_yolo/client.py  
python -m py_compile jour2_crypto/server.py
python -m py_compile jour2_crypto/client.py
python -m py_compile jour3_asymmetric/server.py
python -m py_compile jour3_asymmetric/client.py
```

## Jour 1 - YOLO (Basic Chat)

### Manual Testing

**Terminal 1 - Start server:**
```bash
cd jour1_yolo
python3 server.py 5000
```

**Terminal 2+ - Connect clients:**
```bash
cd jour1_yolo
python3 client.py localhost 5000
```

### Test Scenarios

1. ✅ **Server starts and listens on port 5000**
   - Verify: Logs show "Server started on 0.0.0.0:5000"

2. ✅ **Multiple clients can connect**
   - Connect 3+ clients in separate terminals
   - Each should receive username prompt

3. ✅ **User registry works**
   - Try connecting with duplicate username
   - Should get error "Username already taken - choose another"

4. ✅ **Messages broadcast correctly**
   - Send message from client1
   - All other clients should see: `[client1_username]: message_text`

5. ✅ **Join/leave notifications**
   - New client connects: `[username] has joined`
   - Client disconnects: `[username] has left`

6. ✅ **Commands work**
   - `/list` - Lists online users (in jour1_yolo/server.py)
   - `/quit` - Disconnects gracefully

### Automated Tests

Run validation suite:
```bash
cd jour1_yolo
python3 validate_requirements.py
```

Expected output: ✓ All 11+ requirements passing

---

## Jour 2 - Symmetric Cryptography

### Features to Verify

1. ✅ **Key derivation works**
   - Same password → same key derived
   - Different salt → different key
   - PBKDF2 with 480K iterations

2. ✅ **Encryption/Decryption roundtrip**
   - Plaintext → encrypt → decrypt → same plaintext
   - Different IV each time (random)
   - Ciphertext different each time (random IV)

3. ✅ **HMAC authentication**
   - Tampering detected: Decrypt fails if HMAC invalid
   - Fail-safe: HMAC verified before decryption

4. ✅ **Transmission encoding**
   - Format: Base64(IV):Base64(ciphertext+HMAC)
   - Safe for text-based protocol

### Manual Testing

```bash
cd jour2_crypto

# Terminal 1: Start server
python3 server.py 5000

# Terminal 2+: Connect clients
python3 client.py localhost 5000
```

Enter password: `password123` (default)

Observation:
- Server log shows encrypted content: `[username]: [encrypted_blob]`
- You can chat normally (transparent encryption)
- Server cannot read plaintext messages ✓

---

## Jour 3 - Asymmetric Cryptography & E2EE

### Features to Verify

1. ✅ **RSA keypair generation**
   - 2048-bit keys generated
   - Private key saved encrypted (PKCS8)
   - Public key saved unencrypted (X.509)

2. ✅ **Hybrid encryption works**
   - RSA encrypts session key
   - AES encrypts message with session key
   - Decryption: decrypt session key, then message

3. ✅ **Digital signatures**
   - Message signed with sender's private key
   - Signature verified with sender's public key
   - Tampering detected (signature verification fails)

4. ✅ **E2EE chat**
   - Server maintains public key registry
   - Messages encrypted with recipient's public key
   - Server cannot read encrypted messages
   - Recipients can decrypt with private key

### Manual Testing

```bash
cd jour3_asymmetric

# Terminal 1: Start server (port 5001)
python3 server.py 5001

# Terminal 2+: Connect clients
python3 client.py localhost 5001
```

First connection generates RSA keypair:
```
[CLIENT] Generating RSA 2048-bit keypair...
[CLIENT] Keys saved to ~/.crypto_vibeness/
[CLIENT] Connected to server!
```

Observation:
- Chat works like before
- Messages are end-to-end encrypted
- Server logs show encrypted data only ✓

---

## Cryptography Validation Checklist

### Key Derivation (PBKDF2)
- [x] Correct algorithm: PBKDF2-HMAC-SHA256
- [x] Correct iterations: 480,000 (NIST recommendation)
- [x] Correct salt length: 16 bytes
- [x] Correct key length: 32 bytes (256-bit AES)

### Encryption (AES-256-CBC)
- [x] Correct mode: CBC (not ECB)
- [x] Correct key size: 256-bit (32 bytes)
- [x] Random IV per message: 16 bytes
- [x] IV prepended to ciphertext

### Authentication (HMAC-SHA256)
- [x] Computed over ciphertext (not plaintext)
- [x] Constant-time comparison (no timing attacks)
- [x] Verified before decryption (fail-safe)
- [x] SHA256 hash algorithm

### Digital Signatures (RSA-PSS)
- [x] Correct algorithm: RSA-PSS with SHA256
- [x] Correct key size: 2048-bit
- [x] Signature verification before processing
- [x] Includes sender public key

---

## Performance Testing

### Message Throughput

Time to send 100 messages (Jour 1):
```bash
# In client, modify main loop to send 100 messages
# Expected: < 2 seconds (depends on system)
```

### Encryption Overhead (Jour 2 vs Jour 1)

Jour 1: 
- Message: plaintext
- Size: ~100 bytes

Jour 2:
- Message: IV + ciphertext + HMAC, Base64 encoded
- Size: ~180 bytes (80% overhead from Base64 encoding + IV)
- Time: < 1ms per message

### Key Generation (Jour 3)

RSA 2048-bit keypair generation:
- Time: 1-5 seconds (one-time)
- PBKDF2 key derivation: 1-2 seconds (one-time) 
- Per-message crypto: < 5ms

---

## Debugging Tips

### Check Server Logs

Jour 1:
```
2026-04-14 10:30:00 - INFO - Server started on 0.0.0.0:5000
2026-04-14 10:30:05 - INFO - Connection received from ('127.0.0.1', 54321)
2026-04-14 10:30:10 - INFO - alice: hello everyone
```

Jour 2 (encrypted):
```
2026-04-14 10:30:00 - INFO - Server started on 0.0.0.0:5000
2026-04-14 10:30:05 - INFO - Connection received from ('127.0.0.1', 54321)
2026-04-14 10:30:10 - INFO - alice: pK2d8x/Q1...==:KjFk3x...==
```

Jour 3 (E2EE):
```
[SERVER] E2EE Chat Server listening on port 5001
[SERVER] New connection from ('127.0.0.1', 54322)
[SERVER] Client registered with username: alice
```

### Common Issues

**Connection refused:**
- Server not running
- Wrong port number
- Firewall blocking

**HMAC verification failed (Jour 2):**
- Password wrong
- Message corrupted in transit
- Clock skew (less likely)

**RSA decryption failed (Jour 3):**
- Wrong recipient attempt to decrypt
- Key files corrupted
- Public key registry out of sync

---

## Test Cases for Custom Extensions

If extending the project, ensure:

1. **Multi-client synchronization**
   - Multiple messages in-flight
   - No race conditions on user registry
   - Proper thread locking on shared data

2. **Error recovery**
   - Client disconnects abruptly
   - Network interruption
   - Invalid messages from malicious clients

3. **Cryptographic edge cases**
   - Very long messages (> 1MB)
   - Unicode special characters
   - Concurrent key generation

4. **Performance under load**
   - 10+ simultaneous clients
   - High message frequency
   - Monitor CPU/memory usage

---

## Continuous Integration (CI/CD)

For GitHub Actions, consider:

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Check syntax
        run: python -m py_compile jour*/*.py
      - name: Run validation (Jour 1)
        run: cd jour1_yolo && python3 validate_requirements.py
```

---

## Coverage Goals

- [x] **Code Compilation:** 100% (all files compile)
- [x] **Manual Testing:** All 3 phases working
- [x] **Cryptography:** Key derivation, encryption, signatures validated
- [x] **Networking:** Multi-client, broadcast, join/leave notifications
- [x] **Documentation:** All 3 phases documented

---

Last Updated: April 14, 2026
