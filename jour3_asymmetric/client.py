"""
Jour 3: E2EE Chat Client

End-to-end encrypted chat using hybrid encryption:
  - RSA-OAEP (2048-bit): encrypts the per-message AES session key
  - AES-256-GCM: encrypts the actual message (AEAD — no separate HMAC needed)
  - RSA-PSS / SHA-256: digitally signs every message for authenticity

Protocol (per message):
  1. Sender generates a fresh 32-byte AES session key.
  2. Sender encrypts that key with recipient's RSA public key  (RSA-OAEP).
  3. Sender encrypts the plaintext with AES-256-GCM.
  4. Sender signs the plaintext with their RSA private key (RSA-PSS).
  5. Sender transmits {encrypted_session_key, encrypted_msg, signature} to server.
  6. Server forwards the bundle opaquely (cannot read content).
  7. Recipient decrypts session key with their RSA private key.
  8. Recipient decrypts message with the session key.
  9. Recipient verifies the signature with sender's public key.
"""

import socket
import threading
import json
import sys
import os
import getpass
import base64
import logging
from pathlib import Path
from crypto_utils import (
    encrypt_message_gcm, decrypt_message_gcm,
    encode_for_transmission, decode_from_transmission,
)
from crypto_rsa import (
    generate_rsa_keypair, load_private_key, save_private_key,
    save_public_key, load_public_key, public_key_to_pem,
    pem_to_public_key, encrypt_with_public_key, decrypt_with_private_key,
    sign_message, verify_signature,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)


class E2EEClient:
    def __init__(self, host='localhost', port=5001):
        self.host = host
        self.port = port
        self.socket = None
        self.username = None
        self.shutdown_event = threading.Event()

        # RSA keys (loaded/generated in _setup_rsa_keys)
        self.private_key = None
        self.public_key = None

        # Other users' public keys: {username: public_key_object}
        self.peer_public_keys = {}

        # Key directory
        self.key_dir = Path.home() / '.crypto_vibeness'
        self.key_dir.mkdir(exist_ok=True)

        logger.info(f"Key store: {self.key_dir}")

    # ------------------------------------------------------------------
    # Connection / authentication
    # ------------------------------------------------------------------

    def connect(self):
        """Connect to server and complete the E2EE handshake."""
        logger.info(f"Connecting to {self.host}:{self.port}...")
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            self.socket.connect((self.host, self.port))
        except ConnectionRefusedError:
            logger.error(f"Could not connect to {self.host}:{self.port}")
            sys.exit(1)

        self.username = input("Username: ").strip()
        if not self.username:
            logger.error("Username cannot be empty")
            sys.exit(1)

        password = getpass.getpass("Password: ")

        # Load or generate RSA keys
        self._setup_rsa_keys()

        # Phase 1: Authenticate
        auth_msg = {'type': 'AUTH', 'username': self.username, 'password': password}
        self.socket.send(json.dumps(auth_msg).encode('utf-8'))

        response = json.loads(self.socket.recv(1024).decode('utf-8'))
        if response.get('type') != 'AUTH_OK':
            logger.error("Authentication failed")
            sys.exit(1)

        logger.info(f"Authenticated as '{self.username}'")

        # Phase 2: Upload our RSA public key
        pub_pem = public_key_to_pem(self.public_key).decode('utf-8')
        self.socket.send(json.dumps({'type': 'PUBLIC_KEY', 'public_key': pub_pem}).encode('utf-8'))
        logger.info("RSA public key uploaded to server")

        # Start receive thread
        threading.Thread(target=self._receive_loop, daemon=True).start()

        # Input loop (blocking)
        self._input_loop()

    # ------------------------------------------------------------------
    # RSA key management
    # ------------------------------------------------------------------

    def _setup_rsa_keys(self):
        """Load existing RSA keypair or generate a new one."""
        priv_file = self.key_dir / f"{self.username}.priv"
        pub_file = self.key_dir / f"{self.username}.pub"

        if priv_file.exists() and pub_file.exists():
            logger.info("Loading existing RSA keys...")
            self.private_key = load_private_key(str(priv_file))
            self.public_key = load_public_key(str(pub_file))
        else:
            logger.info("Generating new RSA-2048 keypair...")
            self.private_key, self.public_key = generate_rsa_keypair()
            save_private_key(self.private_key, str(priv_file))
            save_public_key(self.public_key, str(pub_file))
            logger.info(f"Keys saved to {self.key_dir}")

    # ------------------------------------------------------------------
    # Receive loop
    # ------------------------------------------------------------------

    def _receive_loop(self):
        """Receive and dispatch messages from the server."""
        try:
            while not self.shutdown_event.is_set():
                data = self.socket.recv(4096)
                if not data:
                    break

                try:
                    msg = json.loads(data.decode('utf-8'))
                    t = msg.get('type')

                    if t == 'MSG':
                        self._handle_incoming_message(msg)
                    elif t == 'USER_LIST':
                        self._handle_user_list(msg)
                    elif t == 'PUBLIC_KEY':
                        self._handle_public_key_response(msg)
                    elif t == 'ERROR':
                        logger.warning(f"Server error: {msg.get('message')}")

                except Exception as e:
                    logger.error(f"Receive error: {e}")

        except Exception as e:
            if not self.shutdown_event.is_set():
                logger.error(f"Receive loop error: {e}")
        finally:
            self.shutdown()

    def _handle_incoming_message(self, msg: dict):
        """
        Decrypt and verify an incoming E2EE message.

        Expected fields:
          - from: sender username
          - encrypted_session_key: base64(RSA-OAEP(session_key, our_pub_key))
          - encrypted_msg: encode_for_transmission(AES-GCM ciphertext, nonce)
          - signature: hex(RSA-PSS(plaintext_bytes, sender_priv_key))
        """
        sender = msg.get('from', '?')

        try:
            # 1. Decrypt the per-message AES session key with our RSA private key
            enc_sk_b64 = msg['encrypted_session_key']
            enc_sk = base64.b64decode(enc_sk_b64)
            session_key = decrypt_with_private_key(enc_sk, self.private_key)

            # 2. Decode and decrypt the message with AES-256-GCM
            ciphertext_with_tag, nonce = decode_from_transmission(msg['encrypted_msg'])
            plaintext = decrypt_message_gcm(ciphertext_with_tag, nonce, session_key)

            # 3. Verify digital signature (RSA-PSS)
            sig_status = "⚠️ (signature unknown)"
            if sender in self.peer_public_keys:
                signature = bytes.fromhex(msg['signature'])
                if verify_signature(plaintext.encode('utf-8'), signature, self.peer_public_keys[sender]):
                    sig_status = "✅ verified"
                else:
                    sig_status = "❌ INVALID SIGNATURE"
            else:
                sig_status = "⚠️ (public key not yet fetched)"

            print(f"\n[{sender}] {plaintext}  [{sig_status}]")
            print(">>> ", end="", flush=True)

        except Exception as e:
            logger.error(f"Failed to decrypt message from '{sender}': {e}")
            print(f"\n[{sender}] <decryption error>")
            print(">>> ", end="", flush=True)

    def _handle_user_list(self, msg: dict):
        users = msg.get('users', [])
        others = [u for u in users if u != self.username]
        if others:
            print(f"\n[Server] Online: {', '.join(others)}")
            print(">>> ", end="", flush=True)

    def _handle_public_key_response(self, msg: dict):
        uname = msg.get('username')
        if not uname:
            return
        pub_key = pem_to_public_key(msg['public_key'].encode('utf-8'))
        self.peer_public_keys[uname] = pub_key
        logger.info(f"Stored public key for '{uname}'")
        print(f"\n[Client] Public key for '{uname}' received — you can now message them.")
        print(">>> ", end="", flush=True)

    # ------------------------------------------------------------------
    # Input loop / sending
    # ------------------------------------------------------------------

    def _input_loop(self):
        """Read user commands and messages from stdin."""
        print("Commands: @user <message>  |  /list  |  /key <user>  |  /quit")
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
                    self.socket.send(json.dumps({'type': 'GET_USER_LIST'}).encode('utf-8'))
                elif line.startswith('/key '):
                    uname = line.split(' ', 1)[1].strip()
                    self._request_public_key(uname)
                elif line.startswith('@'):
                    parts = line.split(' ', 1)
                    if len(parts) == 2:
                        recipient = parts[0][1:]
                        self._send_e2ee_message(recipient, parts[1])
                    else:
                        print("Usage: @username <message>")
                else:
                    print("Usage: @username <message>, /list, /key <username>, /quit")

                print(">>> ", end="", flush=True)

        except Exception as e:
            logger.error(f"Input error: {e}")
        finally:
            self.shutdown()

    def _request_public_key(self, username: str):
        """Ask the server for a peer's public key."""
        self.socket.send(json.dumps({'type': 'GET_PUBLIC_KEY', 'username': username}).encode('utf-8'))

    def _send_e2ee_message(self, recipient: str, message: str):
        """
        Send a hybrid-encrypted, signed message to recipient.

        If recipient's public key is not yet known, request it first and
        prompt the user to retry once the key arrives.
        """
        if recipient not in self.peer_public_keys:
            logger.info(f"Requesting public key for '{recipient}'…")
            self._request_public_key(recipient)
            print(f"[Client] Fetching key for '{recipient}'. Retry once key is received.")
            return

        try:
            # 1. Generate a fresh 32-byte AES session key
            session_key = os.urandom(32)

            # 2. Encrypt session key with recipient's RSA public key (OAEP)
            enc_session_key = encrypt_with_public_key(session_key, self.peer_public_keys[recipient])
            enc_sk_b64 = base64.b64encode(enc_session_key).decode('ascii')

            # 3. Encrypt message with AES-256-GCM
            ciphertext_with_tag, nonce = encrypt_message_gcm(message, session_key)
            enc_msg_str = encode_for_transmission(ciphertext_with_tag, nonce)

            # 4. Sign the plaintext with our RSA private key (PSS)
            signature_hex = sign_message(message.encode('utf-8'), self.private_key).hex()

            # 5. Send to server for routing
            payload = {
                'type': 'MSG',
                'to': recipient,
                'encrypted_session_key': enc_sk_b64,
                'encrypted_msg': enc_msg_str,
                'signature': signature_hex,
            }
            self.socket.send(json.dumps(payload).encode('utf-8'))
            logger.info(f"Encrypted message sent to '{recipient}' (AES-256-GCM + RSA-OAEP)")

        except Exception as e:
            logger.error(f"Failed to send message to '{recipient}': {e}")

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
    host = 'localhost'
    port = 5001

    if len(sys.argv) > 1:
        host = sys.argv[1]
    if len(sys.argv) > 2:
        try:
            port = int(sys.argv[2])
        except ValueError:
            print(f"Usage: {sys.argv[0]} [host] [port]")
            sys.exit(1)

    client = E2EEClient(host=host, port=port)
    client.connect()


if __name__ == '__main__':
    main()
