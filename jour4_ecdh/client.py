"""
Jour 4: ECDH/ECDSA Chat Client

Features:
- X25519 ephemeral ECDH for Perfect Forward Secrecy
- ECDSA (P-256) digital signatures
- AES-256-GCM authenticated encryption
- Key persistence on disk

Usage:
    python3 client.py [host] [port]
    Commands: @user <message>  |  /list  |  /keys <user>  |  /quit
"""

import socket
import threading
import json
import sys
import os
import getpass
import logging
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from crypto_ecdh import (
    generate_x25519_keypair,
    x25519_public_key_to_bytes,
    x25519_public_key_from_bytes,
    ecdh_derive_session_key,
    generate_ecdsa_keypair,
    ecdsa_public_key_to_pem,
    ecdsa_public_key_from_pem,
    ecdsa_sign, ecdsa_verify,
    aes_gcm_encrypt, aes_gcm_decrypt,
    encode_for_transmission, decode_from_transmission,
)
from config import CLIENT_HOST, CLIENT_PORT

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)


class ECDHClient:
    """
    Chat client using X25519 ECDH + ECDSA + AES-256-GCM.

    Session key protocol (per message):
    1. Client generates a fresh X25519 *ephemeral* keypair.
    2. Client fetches (or has cached) the recipient's X25519 public key.
    3. ECDH shared secret = X25519(ephemeral_priv, recipient_pub).
    4. Session key = HKDF-SHA256(shared_secret).
    5. Message encrypted with AES-256-GCM; sender's ephemeral public key
       sent alongside so the recipient can reconstruct the session key.
    6. Message signed with sender's long-term ECDSA private key.
    """

    def __init__(self, host: str = CLIENT_HOST, port: int = CLIENT_PORT):
        self.host = host
        self.port = port
        self.socket = None
        self.username = None
        self.shutdown_event = threading.Event()

        # Long-term ECDSA keys (persist to disk)
        self.ecdsa_priv = None
        self.ecdsa_pub = None

        # Ephemeral X25519 keypair (refreshed per-session)
        self.ecdh_priv = None
        self.ecdh_pub = None

        # Cached peer keys: {username: {'ecdsa': pub, 'ecdh': pub}}
        self.peer_keys: dict = {}

        self.key_dir = Path.home() / '.crypto_vibeness_j4'
        self.key_dir.mkdir(exist_ok=True)

    # ------------------------------------------------------------------
    # Connection / handshake
    # ------------------------------------------------------------------

    def connect(self):
        """Connect and complete the ECDH handshake."""
        logger.info(f"Connecting to {self.host}:{self.port}...")
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            self.socket.connect((self.host, self.port))
        except ConnectionRefusedError:
            logger.error(f"Connection refused: {self.host}:{self.port}")
            sys.exit(1)

        self.username = input("Username: ").strip()
        if not self.username:
            logger.error("Username cannot be empty")
            sys.exit(1)

        # Load or generate long-term ECDSA keys
        self._setup_ecdsa_keys()

        # Generate fresh ephemeral X25519 keypair
        self.ecdh_priv, self.ecdh_pub = generate_x25519_keypair()
        ecdh_pub_hex = x25519_public_key_to_bytes(self.ecdh_pub).hex()

        # Phase 1: Authenticate
        self.socket.send(json.dumps({'type': 'AUTH', 'username': self.username}).encode('utf-8'))
        resp = json.loads(self.socket.recv(1024).decode('utf-8'))

        if resp.get('type') != 'AUTH_OK':
            logger.error("Authentication failed")
            sys.exit(1)

        logger.info(f"Authenticated as '{self.username}'")

        # Phase 2: Upload our ECDSA + ECDH public keys
        ecdsa_pem = ecdsa_public_key_to_pem(self.ecdsa_pub).decode('utf-8')
        keys_msg = {
            'type': 'KEYS',
            'ecdsa_pub': ecdsa_pem,
            'ecdh_pub_hex': ecdh_pub_hex,
        }
        self.socket.send(json.dumps(keys_msg).encode('utf-8'))
        logger.info("ECDSA + ECDH public keys uploaded")

        # Start receive thread
        threading.Thread(target=self._receive_loop, daemon=True).start()

        # Input loop
        self._input_loop()

    # ------------------------------------------------------------------
    # Key management
    # ------------------------------------------------------------------

    def _setup_ecdsa_keys(self):
        """Load or generate long-term ECDSA (P-256) keypair."""
        priv_path = self.key_dir / f"{self.username}.ecdsa.priv"
        pub_path = self.key_dir / f"{self.username}.ecdsa.pub"

        if priv_path.exists() and pub_path.exists():
            logger.info("Loading existing ECDSA keys...")
            with open(priv_path, 'rb') as f:
                self.ecdsa_priv = serialization.load_pem_private_key(
                    f.read(), password=None, backend=default_backend()
                )
            self.ecdsa_pub = self.ecdsa_priv.public_key()
        else:
            logger.info("Generating new ECDSA/P-256 keypair...")
            self.ecdsa_priv, self.ecdsa_pub = generate_ecdsa_keypair()

            priv_pem = self.ecdsa_priv.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            with open(priv_path, 'wb') as f:
                f.write(priv_pem)
            os.chmod(priv_path, 0o600)

            pub_pem = ecdsa_public_key_to_pem(self.ecdsa_pub)
            with open(pub_path, 'wb') as f:
                f.write(pub_pem)

            logger.info(f"ECDSA keys saved to {self.key_dir}")

    # ------------------------------------------------------------------
    # Receive loop
    # ------------------------------------------------------------------

    def _receive_loop(self):
        """Receive and dispatch server messages."""
        try:
            buffer = ""  # Buffer for incomplete JSON messages
            while not self.shutdown_event.is_set():
                data = self.socket.recv(8192)
                if not data:
                    break

                # Add new data to buffer
                buffer += data.decode('utf-8')

                # Try to parse one or more complete JSON objects from buffer
                while buffer:
                    # Find the next complete JSON object
                    buffer = buffer.lstrip()  # Remove leading whitespace
                    if not buffer:
                        break

                    # Try to find complete JSON object
                    brace_count = 0
                    in_string = False
                    escape_next = False
                    end_pos = 0

                    for i, char in enumerate(buffer):
                        if escape_next:
                            escape_next = False
                            continue
                        if char == '\\':
                            escape_next = True
                            continue
                        if char == '"' and not escape_next:
                            in_string = not in_string
                        elif not in_string:
                            if char == '{':
                                brace_count += 1
                            elif char == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    end_pos = i + 1
                                    break

                    if end_pos == 0:
                        # Incomplete JSON, need more data
                        break

                    # Extract and parse the complete JSON object
                    json_str = buffer[:end_pos]
                    buffer = buffer[end_pos:]

                    try:
                        msg = json.loads(json_str)
                        t = msg.get('type')

                        if t == 'MSG':
                            self._handle_message(msg)
                        elif t == 'USER_LIST':
                            self._handle_user_list(msg)
                        elif t == 'PEER_KEYS':
                            self._handle_peer_keys(msg)
                        elif t == 'ERROR':
                            logger.warning(f"Server: {msg.get('message')}")

                    except Exception as e:
                        logger.error(f"Receive error: {e}")

        except Exception as e:
            if not self.shutdown_event.is_set():
                logger.error(f"Receive loop: {e}")
        finally:
            self.shutdown()

    def _handle_message(self, msg: dict):
        """Decrypt and verify an incoming message using ECDH session key."""
        sender = msg.get('from', '?')

        try:
            # 1. Reconstruct the ECDH session key from sender's ephemeral public key
            sender_ecdh_pub = x25519_public_key_from_bytes(
                bytes.fromhex(msg['sender_ecdh_pub_hex'])
            )
            session_key = ecdh_derive_session_key(self.ecdh_priv, sender_ecdh_pub)

            # 2. Decrypt with AES-256-GCM
            ciphertext_with_tag, nonce = decode_from_transmission(msg['encrypted_msg'])
            plaintext = aes_gcm_decrypt(ciphertext_with_tag, nonce, session_key)

            # 3. Verify ECDSA signature
            sig_status = "⚠️ (key unknown)"
            if sender in self.peer_keys and 'ecdsa' in self.peer_keys[sender]:
                sig = bytes.fromhex(msg['signature'])
                if ecdsa_verify(plaintext.encode('utf-8'), sig, self.peer_keys[sender]['ecdsa']):
                    sig_status = "✅ verified"
                else:
                    sig_status = "❌ INVALID SIGNATURE"

            print(f"\n[{sender}] {plaintext}  [{sig_status}]")
            print(">>> ", end="", flush=True)

        except Exception as e:
            logger.error(f"Decryption error from '{sender}': {e}")
            print(f"\n[{sender}] <decryption error>")
            print(">>> ", end="", flush=True)

    def _handle_user_list(self, msg: dict):
        others = [u for u in msg.get('users', []) if u != self.username]
        if others:
            print(f"\n[Server] Online: {', '.join(others)}")
            print(">>> ", end="", flush=True)

    def _handle_peer_keys(self, msg: dict):
        uname = msg.get('username')
        if not uname:
            return

        ecdsa_pub = ecdsa_public_key_from_pem(msg['ecdsa_pub'].encode('utf-8'))
        ecdh_pub = x25519_public_key_from_bytes(bytes.fromhex(msg['ecdh_pub_hex']))

        self.peer_keys[uname] = {'ecdsa': ecdsa_pub, 'ecdh': ecdh_pub}
        logger.info(f"Cached ECDSA + ECDH keys for '{uname}'")
        print(f"\n[Client] Keys for '{uname}' received. You can now message them.")
        print(">>> ", end="", flush=True)

    # ------------------------------------------------------------------
    # Input loop / sending
    # ------------------------------------------------------------------

    def _input_loop(self):
        """Handle user input."""
        print("Commands: @user <message>  |  /list  |  /keys <user>  |  /quit")
        print(">>> ", end="", flush=True)

        try:
            while not self.shutdown_event.is_set():
                try:
                    line = input()
                except EOFError:
                    break

                if line.startswith('/quit'):
                    break
                elif line.startswith('/list'):
                    self.socket.send(json.dumps({'type': 'GET_KEYS', 'username': None}).encode('utf-8'))
                    # server broadcasts USER_LIST on connect; just print what we know
                    with_keys = list(self.peer_keys.keys())
                    print(f"[Client] Cached peers: {with_keys or '(none)'}")
                elif line.startswith('/keys '):
                    uname = line.split(' ', 1)[1].strip()
                    self._request_peer_keys(uname)
                elif line.startswith('@'):
                    parts = line.split(' ', 1)
                    if len(parts) == 2:
                        self._send_message(parts[0][1:], parts[1])
                    else:
                        print("Usage: @username <message>")
                else:
                    print("Usage: @username <message>, /list, /keys <username>, /quit")

                print(">>> ", end="", flush=True)

        except Exception as e:
            logger.error(f"Input error: {e}")
        finally:
            self.shutdown()

    def _request_peer_keys(self, username: str):
        """Ask server for a peer's public keys."""
        self.socket.send(json.dumps({'type': 'GET_KEYS', 'username': username}).encode('utf-8'))

    def _send_message(self, recipient: str, message: str):
        """
        Send an E2EE message using ephemeral ECDH + AES-256-GCM + ECDSA.
        """
        if recipient not in self.peer_keys:
            logger.info(f"Requesting keys for '{recipient}'...")
            self._request_peer_keys(recipient)
            print(f"[Client] Fetching keys for '{recipient}'. Retry once received.")
            return

        try:
            peer_ecdh_pub = self.peer_keys[recipient]['ecdh']

            # 1. Generate a *fresh* ephemeral X25519 keypair for this message
            #    → Perfect Forward Secrecy: each message uses a new ephemeral key
            sender_ecdh_priv, sender_ecdh_pub = generate_x25519_keypair()
            session_key = ecdh_derive_session_key(sender_ecdh_priv, peer_ecdh_pub)

            # 2. Encrypt with AES-256-GCM
            ct_with_tag, nonce = aes_gcm_encrypt(message, session_key)
            enc_msg = encode_for_transmission(ct_with_tag, nonce)

            # 3. Sign plaintext with ECDSA
            signature_hex = ecdsa_sign(message.encode('utf-8'), self.ecdsa_priv).hex()

            # 4. Send to server
            payload = {
                'type': 'MSG',
                'to': recipient,
                'sender_ecdh_pub_hex': x25519_public_key_to_bytes(sender_ecdh_pub).hex(),
                'encrypted_msg': enc_msg,
                'signature': signature_hex,
            }
            self.socket.send(json.dumps(payload).encode('utf-8'))
            logger.info(f"Message → '{recipient}' (ECDH/X25519 + AES-256-GCM + ECDSA)")

        except Exception as e:
            logger.error(f"Send error to '{recipient}': {e}")

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def shutdown(self):
        """Gracefully disconnect."""
        if not self.shutdown_event.is_set():
            logger.info("Disconnecting...")
        self.shutdown_event.set()
        try:
            self.socket.close()
        except Exception:
            pass


def main():
    host = CLIENT_HOST
    port = CLIENT_PORT

    if len(sys.argv) > 1:
        host = sys.argv[1]
    if len(sys.argv) > 2:
        try:
            port = int(sys.argv[2])
        except ValueError:
            print(f"Usage: {sys.argv[0]} [host] [port]")
            sys.exit(1)

    client = ECDHClient(host=host, port=port)
    client.connect()


if __name__ == '__main__':
    main()
