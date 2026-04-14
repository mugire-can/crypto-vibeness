# 🛠️ Crypto Vibeness - Development Guide

## Prerequisites

- **Python:** 3.8 or higher
- **pip:** Python package manager (comes with Python)
- **git:** For version control

Check your versions:
```bash
python3 --version
pip3 --version
git --version
```

## Installation

### 1️⃣ Clone Repository
```bash
git clone https://github.com/mugire-can/crypto-vibeness.git
cd crypto-vibeness
```

### 2️⃣ Create Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3️⃣ Install Dependencies
```bash
pip install -r requirements.txt
```

Or with modern Python:
```bash
pip install -e .
```

### 4️⃣ Verify Installation
```bash
python -m py_compile jour1_yolo/server.py jour1_yolo/client.py
echo "✓ Installation successful!"
```

---

## Quick Start

### **Run Jour 1 (Basic Chat)**

**Terminal 1 - Start server:**
```bash
cd jour1_yolo
python3 server.py 5000
```

**Terminal 2 - Connect client (or more):**
```bash
cd jour1_yolo
python3 client.py localhost 5000
```

Type your username and start chatting. Type `/quit` to exit.

---

### **Run Jour 2 (Symmetric Encryption)**

Same steps as Jour 1, but use `jour2_crypto/`:
```bash
# Terminal 1
cd jour2_crypto
python3 server.py 5000

# Terminal 2+
cd jour2_crypto
python3 client.py localhost 5000
```

Password: `password123` (default in config.py)

---

### **Run Jour 3 (End-to-End Encryption)**

```bash
# Terminal 1
cd jour3_asymmetric
python3 server.py 5001

# Terminal 2+
cd jour3_asymmetric
python3 client.py localhost 5001
```

---

## Development Workflow

### Code Quality

**Format code with Black:**
```bash
black jour1_yolo/ jour2_crypto/ jour3_asymmetric/
```

**Lint with Pylint:**
```bash
pylint jour1_yolo/server.py jour2_crypto/server.py
```

### Testing

**Check syntax:**
```bash
python -m py_compile jour1_yolo/*.py jour2_crypto/*.py jour3_asymmetric/*.py
```

**Run validation tests (Jour 1):**
```bash
cd jour1_yolo
python3 validate_requirements.py
```

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'cryptography'"
```bash
pip install cryptography>=42.0.0
```

### "Address already in use" on port
Change the port in code or kill existing process:
```bash
# Find process on port 5000
netstat -ano | findstr :5000

# Kill it (Windows)
taskkill /PID <PID> /F

# Or macOS/Linux
lsof -i :5000 | awk 'NR!=1 {print $2}' | xargs kill -9
```

### Connection refused
- Ensure server is running in separate terminal
- Check firewall settings
- Verify port is correct (default: 5000)

---

## Project Structure

```
crypto-vibeness/
├── README.md                    # Main overview
├── DEVELOPMENT.md              # This file
├── START_HERE.md               # Quick start
├── requirements.txt            # Python dependencies
├── pyproject.toml              # Modern Python config
│
├── jour1_yolo/                 # Phase 1: Basic Chat
│   ├── server.py              # Multi-threaded server
│   ├── client.py              # Interactive client
│   ├── config.py              # Configuration
│   └── README_JOUR1.md        # Phase 1 guide
│
├── jour2_crypto/               # Phase 2: Symmetric Encryption
│   ├── server.py              # AES-256 encrypted server
│   ├── client.py              # Encrypted client
│   ├── crypto_utils.py        # AES/HMAC utils
│   ├── config.py              # Encryption config
│   └── JOUR2_PLAN.md          # Architecture docs
│
└── jour3_asymmetric/           # Phase 3: E2EE + Signatures
    ├── server.py              # RSA key registry + routing
    ├── client.py              # E2EE client
    ├── crypto_rsa.py          # RSA utilities
    ├── crypto_utils.py        # AES utils
    ├── config.py              # E2EE config
    └── JOUR3_PLAN.md          # Architecture docs
```

---

## Contributing

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make changes and test
3. Format code: `black .`
4. Commit with clear messages: `git commit -m "Add feature description"`
5. Push to GitHub: `git push origin feature/my-feature`
6. Open a Pull Request

---

## Documentation Files

| File | Purpose |
|------|---------|
| **README.md** | Main project overview |
| **START_HERE.md** | 5-minute quick start |
| **DEVELOPMENT.md** | This file - setup & development |
| **PROJECT_COMPLETE.md** | Final status report |
| **JOUR1_README.md** | Phase 1 detailed guide |
| **JOUR2_PLAN.md** | Phase 2 architecture |
| **JOUR3_PLAN.md** | Phase 3 architecture |

---

## ⚠️ Security Warning

**This is an educational project.** The implementations are simplified for learning. 

**Never use for production:**
- ❌ Don't use these implementations in production systems
- ❌ Don't rely on custom crypto implementations
- ✅ Use vetted libraries like TLS/SSL for real applications
- ✅ Follow NIST/ANSSI guidelines

---

## License

MIT License - See LICENSE file for details

---

## Questions?

- 📖 Read the phase documentation (JOUR*_PLAN.md)
- 🔍 Check inline code comments
- 📝 Review architecture diagrams in markdown files
