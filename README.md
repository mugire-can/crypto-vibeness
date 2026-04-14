# Crypto Vibeness — A Progressive Cryptography Chat Project

**Crypto Vibeness** is an educational project that builds a secure multi-user chat system step by step, introducing cryptographic concepts at each stage.

---

## Project Structure

```
crypto-vibeness/
├── jour1_yolo/              # Day 1 – Basic IRC-like chat (no encryption)
│   ├── server.py
│   ├── client.py
│   ├── config.py
│   ├── test_server.py
│   ├── test_comprehensive.py
│   └── README_JOUR1.md
│
├── jour2_crypto/            # Day 2 – Symmetric encryption (AES-256-CBC + HMAC, AES-256-GCM)
│   ├── server.py
│   ├── client.py
│   ├── crypto_utils.py      # AES-256-CBC+HMAC & AES-256-GCM, PBKDF2
│   └── config.py
│
├── jour3_asymmetric/        # Day 3 – Hybrid E2EE (RSA-OAEP + AES-256-GCM + RSA-PSS)
│   ├── server.py
│   ├── client.py
│   ├── crypto_rsa.py        # RSA-2048 key generation, OAEP encryption, PSS signing
│   ├── crypto_utils.py      # AES-256-GCM utilities (shared with Jour 2)
│   └── config.py
│
├── jour4_ecdh/              # Day 4 – Modern EC: ECDH + ECDSA + AES-256-GCM (PFS)
│   ├── server.py
│   ├── client.py
│   ├── crypto_ecdh.py       # X25519 ECDH, ECDSA/P-256, AES-256-GCM, HKDF
│   └── config.py
│
├── tests/
│   └── test_crypto.py       # Unit tests for all crypto modules (61 tests)
│
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## Learning Path

### Jour 1 — YOLO (No Security)

A plain TCP multi-user chat server and client.  No authentication, no encryption.

**Concepts:** sockets, threading, message broadcasting

```bash
cd jour1_yolo
# Terminal 1
python3 server.py 5000
# Terminal 2+
python3 client.py localhost 5000
```

---

### Jour 2 — Symmetric Cryptography

All messages are encrypted with **AES-256** before being sent.  The server still relays
ciphertext; it cannot read messages because it only knows the shared password-derived key.

**Cryptographic primitives:**
| Primitive | Purpose |
|-----------|---------|
| PBKDF2-SHA256 (480 000 iterations) | Password → AES key derivation |
| AES-256-CBC + HMAC-SHA256 | Encrypt-then-MAC (legacy compatible) |
| AES-256-GCM | Authenticated encryption (recommended) |

```bash
cd jour2_crypto
# Terminal 1
python3 server.py 5000 mypassword
# Terminal 2+
python3 client.py localhost 5000
# Enter the same password when prompted
```

---

### Jour 3 — Hybrid E2EE with RSA

True **end-to-end encryption**: the server is a blind relay that cannot read any message.

**Protocol (per message):**
1. Sender generates a fresh 32-byte AES session key.
2. Session key is encrypted with recipient's **RSA-2048 public key** (OAEP/SHA-256).
3. Message is encrypted with **AES-256-GCM**.
4. Message is signed with sender's **RSA-PSS** private key.
5. Server forwards the opaque bundle; recipient decrypts using their RSA private key.

**Cryptographic primitives:**
| Primitive | Purpose |
|-----------|---------|
| RSA-2048 / OAEP-SHA256 | Session key encapsulation |
| AES-256-GCM | Message encryption (AEAD) |
| RSA-PSS / SHA-256 | Digital signatures |

```bash
cd jour3_asymmetric
# Terminal 1
python3 server.py 5001
# Terminal 2+
python3 client.py localhost 5001
# Send: @username <message>
# Fetch a peer's public key first: /key <username>
```

---

### Jour 4 — ECDH + ECDSA + AES-256-GCM (Perfect Forward Secrecy)

Modern cryptography using **elliptic curves** — smaller keys, faster operations, and
**Perfect Forward Secrecy** (PFS) via ephemeral X25519 key pairs.

**Why better than Jour 3?**
- X25519 keys are 256 bits vs 2048 bits for equivalent RSA security
- Each message uses a fresh ephemeral keypair → compromising one session key never
  reveals previous sessions (PFS)
- ECDSA/P-256 signatures are faster than RSA-PSS
- HKDF-SHA256 provides clean key derivation from the shared secret

**Protocol (per message):**
1. Sender generates a **fresh ephemeral X25519 keypair** (PFS).
2. ECDH exchange: `session_key = HKDF(X25519(sender_eph_priv, recipient_pub))`.
3. Message encrypted with **AES-256-GCM**.
4. Message signed with sender's long-term **ECDSA/P-256** private key.
5. Sender's ephemeral public key is transmitted so the recipient can reconstruct the
   session key.

**Cryptographic primitives:**
| Primitive | Purpose |
|-----------|---------|
| X25519 ECDH (ephemeral) | Session key agreement with PFS |
| HKDF-SHA256 | Shared-secret → AES key derivation |
| AES-256-GCM | Message encryption (AEAD) |
| ECDSA / P-256 / SHA-256 | Digital signatures |

```bash
cd jour4_ecdh
# Terminal 1
python3 server.py 5002
# Terminal 2+
python3 client.py localhost 5002
# Fetch peer keys: /keys <username>
# Send: @username <message>
```

---

## Tests

```bash
pip install pytest
pytest tests/ -v
```

61 tests covering:
- PBKDF2 key derivation
- AES-256-CBC with HMAC-SHA256
- AES-256-GCM (authenticated encryption)
- Transmission encoding/decoding helpers
- RSA-2048 encrypt/decrypt/sign/verify/save/load
- X25519 ECDH key exchange
- ECDSA/P-256 sign/verify
- Full end-to-end integration flow

---

## Installation

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Requires Python 3.8+ and the `cryptography` library (≥ 42.0).

---

## Cryptography Reference

| Concept | What it solves | Where used |
|---------|---------------|------------|
| Symmetric encryption | Efficient bulk data encryption | Jour 2, 3, 4 |
| AEAD (AES-GCM) | Encryption + integrity in one primitive | Jour 2–4 |
| Key derivation (PBKDF2) | Password → strong key | Jour 2–3 |
| Asymmetric encryption (RSA) | Key encapsulation; no shared secret needed | Jour 3 |
| Digital signatures | Authenticity + non-repudiation | Jour 3–4 |
| Hybrid encryption | Combine asymmetric (key exchange) + symmetric (speed) | Jour 3–4 |
| ECDH | Efficient key agreement | Jour 4 |
| Perfect Forward Secrecy | Old sessions safe even if long-term key leaks | Jour 4 |
| HKDF | Derive strong keys from shared secrets | Jour 4 |

---

## ⚠️  Educational Project

This code is for learning purposes only.  Do **not** use in production systems without
a thorough security review.  Always follow current NIST / ANSSI guidelines and prefer
well-audited libraries such as TLS 1.3 for real-world communication security.
