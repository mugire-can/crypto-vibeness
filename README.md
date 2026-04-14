# Crypto Vibeness — Système de Chat Sécurisé Progressif

Educational project: build a secure multi-user chat system step by step, introducing cryptographic concepts at each stage.

---

## Project Structure

```
crypto-vibeness/
├── jour1_yolo/              # Day 1 – YOLO + Authentication
│   ├── server.py            # Full server: rooms, colors, logging, auth (MD5→bcrypt)
│   ├── client.py            # Full client: auth flow, room commands, colored output
│   ├── config.py            # Server/client configuration
│   ├── password_rules.json  # Password policy (loaded at runtime)
│   └── README_JOUR1.md
│
├── jour2_crypto/            # Day 2 – Symmetric encryption + per-user keys
│   ├── server.py            # Per-user AES-256 keys; argon2/scrypt password hashing
│   ├── client.py            # Stores own key in ./users/<username>/key.txt
│   ├── crypto_utils.py      # AES-256-CBC+HMAC & AES-256-GCM, PBKDF2
│   └── config.py
│
├── jour3_asymmetric/        # Day 3 – Hybrid E2EE (RSA-OAEP + AES-256-GCM + RSA-PSS)
│   ├── server.py            # Blind relay: distributes public keys, routes ciphertext
│   ├── client.py            # RSA-OAEP key encapsulation + AES-GCM + RSA-PSS signatures
│   ├── crypto_rsa.py        # RSA-2048 key generation, OAEP, PSS
│   ├── crypto_utils.py      # AES-256-GCM utilities
│   └── config.py
│
├── jour4_ecdh/              # Bonus – Modern EC: ECDH + ECDSA + AES-256-GCM (PFS)
│   ├── server.py
│   ├── client.py
│   ├── crypto_ecdh.py       # X25519 ECDH, ECDSA/P-256, AES-256-GCM, HKDF
│   └── config.py
│
├── tests/
│   └── test_crypto.py       # 61 unit tests for all crypto modules
│
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## Learning Path

### Jour 1 — Part 1: YOLO (Basic chat + rooms + colors)

Multi-user IRC-like chat with rooms and visual identity.

**Features:**
- Multiple simultaneous clients
- Unique username enforcement
- **Room system**: create and join rooms, optional room passwords
- Password-protected rooms shown with 🔒 in room list
- **Deterministic colors** per user (consistent across all clients)
- **Timestamps** on all messages
- **File logging**: `log_YYYY-MM-DD_HH-MM-SS.txt`

**Commands:** `/join <room> [password]`, `/create <room> [password]`, `/rooms`, `/users`, `/quit`

```bash
cd jour1_yolo
python3 server.py 5000      # Terminal 1
python3 client.py 5000      # Terminal 2+ 
```

---

### Jour 1 — Part 2: Authentication

Password authentication before chat access.

**Features:**
- First connection → user registration (password chosen + confirmed)
- Password rules (configurable in `password_rules.json`): min 8 chars, 1 digit, 1 uppercase
- **Password strength indicator** (entropy-based: Weak / Fair / Strong / Very Strong)
- Passwords stored **MD5-hashed** (intentionally weak — see Jour 2) in `this_is_safe.txt`
- Format: `username:md5_base64_hash`
- Constant-time comparison (`hmac.compare_digest`)

Built into the same `jour1_yolo/` server as Part 1.

---

### Jour 2 — Part 1: Le hacker marseillais (MD5 cracking → bcrypt)

The "marseillais hacker" stole `this_is_safe.txt` and can crack MD5 hashes.

**What was done:**
- Cracked the hash left by the hacker: `35b95f7c0f63631c453220fb2a86f218` → **`CMrsBB!`**
  - Command: `hashcat -m 0 -a 3 md5_yolo.txt '?u?u?l?l?u?u?s'`
  - See `jour2_crypto/md5_decrypted.txt`

**Upgraded password storage:**
- Replaced MD5 with **argon2** (falls back to **scrypt**) — secure, slow-by-design
- Per-password salt (≥ 96 bits)
- Format: `username:algo:cost_factor:salt_b64:digest_b64`
  - Example: `alice:argon2:3:<salt_b64>:<hash_b64>`

```bash
cd jour2_crypto
python3 server.py 5000
python3 client.py localhost 5000
```

---

### Jour 2 — Part 2: Le hacker russe (Symmetric encryption per user)

A Russian hacker recorded all network traffic. Encrypt everything!

**Features:**
- At account creation: derive a personal **AES-256** key from user's secret via **PBKDF2-SHA256**
- Server stores per-user key+salt in `user_keys_do_not_steal_plz.txt`
- Client stores key locally in `./users/<username>/key.txt`
- All messages encrypted with the user's own AES-256-CBC key
- Server decrypts to relay to recipients (symmetric encryption, not E2EE)

Built into the same `jour2_crypto/` server/client.

---

### Jour 3 — Asymmetric + E2EE

**Part 1 — Key exchange with RSA:**
- Client generates RSA-2048 keypair (or reuses from `.priv`/`.pub` files)
- Asymmetric encryption (RSA-OAEP) used to exchange a symmetric session key
- No `user_keys_do_not_steal_plz.txt` on server

**Part 2 — End-to-End Encryption (E2EE):**
- Server is "honest-but-curious" — routes messages but cannot read them

| Step | What happens |
|------|-------------|
| 1 | Client uploads its RSA public key; server maintains `{username: public_key}` directory |
| 2 | Alice encrypts a session key with Bob's RSA public key (OAEP); sends via server; Bob decrypts with his private key |
| 3 | All messages encrypted with AES-256-GCM using the session key |
| 4 | Each message signed with sender's RSA private key (PSS); recipient verifies |

```bash
cd jour3_asymmetric
python3 server.py 5001      # Terminal 1
python3 client.py 5001      # Terminal 2+
# /key <username> to fetch public key, then @username <message>
```

---

### Jour 4 — ECDH + ECDSA + AES-256-GCM (Bonus: Perfect Forward Secrecy)

Modern elliptic-curve cryptography — smaller keys, faster, PFS.

| Primitive | Purpose |
|-----------|---------|
| X25519 ECDH (ephemeral) | Per-message session key with PFS |
| HKDF-SHA256 | Shared-secret → AES key derivation |
| AES-256-GCM | AEAD encryption |
| ECDSA / P-256 | Digital signatures |

```bash
cd jour4_ecdh
python3 server.py 5002
python3 client.py 5002
```

---

## Tests

```bash
pip install pytest
pytest tests/ -v     # 61 tests, all pass
```

---

## Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# Optional: pip install argon2-cffi   # for argon2 password hashing in jour2
```

---

## Security disclaimer

⚠️ **Educational project only.** Some implementations are intentionally simplified or weak (e.g., MD5 in Jour 1 is used to demonstrate its weaknesses). Do **not** use this code in production.

> "Don't roll your own crypto" — except for learning purposes!
