# Crypto Vibeness - A Secure Chat System Project

## Project Overview

**Crypto Vibeness** is an educational project designed to teach cryptography concepts through progressive implementation of a secure chat system. The project builds a multi-user chat application using Python, gradually introducing three core cryptographic branches:

1. **Hash Functions** (MD5, SHA256, etc.) - Data indexing, integrity verification
2. **Symmetric Cryptography** - Secure communication channels (HTTPS, VPNs, Signal-like protocols)
3. **Asymmetric Cryptography** - Public/private key systems, digital signatures, end-to-end encryption

## Project Structure

```
crypto-vibeness/
├── README.md                    # Project documentation (this file)
├── .gitignore                   # Git ignore rules
├── jour1_yolo/                  # Day 1: Basic chat (no auth, no encryption)
│   ├── server.py               # IRC-like chat server
│   └── client.py               # Chat client
├── jour2_crypto/                # Day 2: Symmetric cryptography
│   ├── jour2_partie1/          # Basic symmetric encryption
│   ├── jour2_partie2/          # Enhanced with key management
│   └── jour2_partie3/          # Symmetric key encapsulation
├── jour3_asymmetric/            # Day 3: Asymmetric cryptography
│   ├── jour3_partie1/          # Key generation and exchange
│   └── jour3_partie2/          # Hybrid encryption (asymmetric + symmetric)
├── jour3_e2ee/                  # Day 3: End-to-End Encryption (E2EE)
│   ├── jour3_partie3/          # Public key distribution
│   ├── jour3_partie4/          # Session key establishment
│   ├── jour3_partie5/          # Message encryption
│   └── jour3_partie6/          # Message signatures
└── docs/                        # Additional documentation and resources
```

## Development Stages

### **Jour 1 - 1ère partie: YOLO** (No Security)
Build a basic IRC-like multi-user chat system without authentication or encryption.

**Key Features:**
- Server listens on a configurable port (default defined in variables)
- Multiple clients can connect simultaneously
- Messages broadcast to all connected clients
- Simple command interface (e.g., `/quit` to disconnect)
- Clear user join/leave notifications

**Validation Criteria:**
- Server starts and listens correctly
- Multiple clients connect and communicate
- Messages broadcast to all users
- Clean disconnection handling

### **Jour 2 - Cryptographie Symétrique** (Symmetric Encryption)
Implement symmetric encryption for secure communication.

### **Jour 3 - Cryptographie Asymétrique** (Asymmetric Encryption)
Implement asymmetric cryptography for key exchange.

### **Jour 3 - Chiffrement de Bout en Bout** (End-to-End Encryption)
Implement E2EE with digital signatures for secure 1-1 communication.

## Technical Requirements

### Prerequisites
- Python 3.8 or higher
- `cryptography` library (for crypto primitives)
- Standard library modules: `socket`, `threading`, `json`, `hashlib`, `hmac`

### Installation & Setup

📖 **For detailed setup instructions**, see [DEVELOPMENT.md](./DEVELOPMENT.md)

Quick start:
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Project

**See [START_HERE.md](./START_HERE.md) for quick-start instructions!**

**Day 1 (YOLO - Basic Chat):**

```bash
cd jour1_yolo

# Terminal 1: Start the server
python3 server.py 5000

# Terminal 2+: Connect clients  
python3 client.py localhost 5000
```

Type a username and start chatting. Type `/quit` to disconnect.

## Important Notes on Cryptography

⚠️ **WARNING**: This project is educational. The implementations are intentionally simplified and **NOT suitable for production use**. The systems may be cryptographically weak. Always remember: **"Don't roll your own crypto"** except for learning purposes.

In real-world applications:
- Use vetted cryptographic libraries and frameworks
- Never implement custom cryptographic primitives
- Follow ANSSI and NIST guidelines
- Have security professionals review your code

## Learning Objectives

By completing this project, you will:
- ✅ Understand hash functions and their applications
- ✅ Implement symmetric key cryptography
- ✅ Implement asymmetric key cryptography
- ✅ Design hybrid encryption systems (symmetric + asymmetric)
- ✅ Implement end-to-end encryption (E2EE)
- ✅ Understand digital signatures and authentication
- ✅ Apply prompt engineering to AI coding agents
- ✅ Validate cryptographic implementations

## Validation Strategy

Each phase must be validated before proceeding to the next:

1. **Code Review**: Ensure code follows best practices
2. **Functional Testing**: Verify all features work as expected
3. **Security Validation**: Check encryption/decryption, signature verification
4. **Server Logs Review**: For E2EE phases, verify encrypted data in logs
5. **Manual Testing**: Test edge cases and attack scenarios

## AI Agent Workflow

This project is designed to be completed with an AI coding agent (Copilot CLI, Claude, etc.) using:
- **Prompt Engineering**: Carefully crafted prompts with full context
- **Context Engineering**: Configuration files and documentation for context
- **Validation**: Manual verification of each deliverable before proceeding
- **Iterative Development**: Prompt → Code → Test → Validate → Next Phase

## Key Concepts to Understand

### Hashing
- One-way function producing fixed-size output
- Use: password storage, integrity checking, blockchain

### Symmetric Encryption
- Same key for encryption and decryption
- Fast, efficient for bulk data
- Challenge: key distribution

### Asymmetric Encryption
- Public/private key pair
- Public key for encryption, private key for decryption
- Challenge: computational cost

### Hybrid Encryption
- Use asymmetric crypto to exchange symmetric key
- Use symmetric crypto for actual communication
- Best of both worlds: security + performance

### End-to-End Encryption (E2EE)
- Only sender and recipient can read messages
- Server cannot access message content
- Requires authentication and key management

### Digital Signatures
- Prove message authenticity and non-repudiation
- Sign with private key, verify with public key
- Detect tampering

## Resources

- **Crypto 101**: Essential resource for cryptographic primitives
- **ANSSI Password Rules**: https://www.anssi.gouv.fr/
- **Latacora Best Practices**: Good reflexes in cryptography
- **xkcd on Password Entropy**: https://xkcd.com/936/
- **Password Strength Meter**: https://howsecureismypassword.net/
- **Hashcat**: Password cracking tool for understanding attack vectors

## Commits and Progress

Each completed phase should be committed with clear messages:
```bash
git add .
git commit -m "Jour 1 - YOLO: Basic IRC-like chat system

- Multi-user chat server and client
- User join/leave notifications
- Message broadcasting
- Command interface (/quit, etc.)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

## Code Standards

- **Language**: English (all code)
- **Communication**: French allowed in prompts, documents
- **Style**: PEP 8 for Python
- **Comments**: Only for non-obvious logic
- **Logging**: Useful for validation, especially in later phases

## Evaluation Criteria

Project will be evaluated on:
1. ✅ Functional correctness (does it work?)
2. ✅ Code quality (clean, readable, well-structured)
3. ✅ Cryptographic understanding (proper usage, not just implementation)
4. ✅ Documentation quality (README, code comments, commit messages)
5. ✅ Prompt engineering skills (effective use of AI agents)
6. ✅ Validation thoroughness (comprehensive testing)

---

**Good luck! Remember: understand the concepts, validate each phase, and ask your AI agent to explain any cryptographic concepts you don't understand!**
