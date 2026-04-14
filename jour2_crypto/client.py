#!/usr/bin/env python3
"""
Crypto Vibeness - Jour 2: Encrypted Chat Client with Per-User Keys

Features:
- Authenticate with server (register or login)
- Receive and store AES-256 key in ./users/<username>/key.txt
- All messages encrypted with user's personal key
- AES-256-CBC with HMAC-SHA256
"""

import socket
import threading
import sys
import os
import base64
import logging
import getpass
from typing import Optional

try:
    sys.path.insert(0, os.path.dirname(__file__))
    from crypto_utils import (
        derive_key_from_password,
        encrypt_message,
        decrypt_message,
        encode_for_transmission,
        decode_from_transmission
    )
except ImportError:
    print("❌ Error: crypto_utils module not found")
    sys.exit(1)

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 5000
BUFFER_SIZE = 4096
ENCODING = 'utf-8'


def load_or_get_key(username: str, script_dir: str) -> Optional[bytes]:
    """Load AES key from ./users/<username>/key.txt if it exists."""
    key_path = os.path.join(script_dir, "users", username, "key.txt")
    if os.path.exists(key_path):
        try:
            with open(key_path, "r") as f:
                return base64.b64decode(f.read().strip())
        except Exception:
            return None
    return None


def save_key(username: str, key_b64: str, script_dir: str) -> None:
    """Save AES key to ./users/<username>/key.txt."""
    key_dir = os.path.join(script_dir, "users", username)
    os.makedirs(key_dir, exist_ok=True)
    key_path = os.path.join(key_dir, "key.txt")
    with open(key_path, "w") as f:
        f.write(key_b64 + "\n")
    logger.info(f"Key saved to {key_path}")


class EncryptedChatClient:
    """Encrypted chat client with per-user AES key."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.connected = False
        self.username: Optional[str] = None
        self.aes_key: Optional[bytes] = None
        self._recv_buffer = b""
        self.script_dir = os.path.dirname(os.path.abspath(__file__))

    def _send_line(self, text: str) -> bool:
        try:
            self.socket.sendall((text + "\n").encode(ENCODING))
            return True
        except Exception:
            self.connected = False
            return False

    def _recv_line(self) -> Optional[str]:
        try:
            while b"\n" not in self._recv_buffer:
                chunk = self.socket.recv(BUFFER_SIZE)
                if not chunk:
                    return None
                self._recv_buffer += chunk
            idx = self._recv_buffer.index(b"\n")
            line = self._recv_buffer[:idx]
            self._recv_buffer = self._recv_buffer[idx + 1:]
            return line.decode(ENCODING).strip()
        except Exception:
            return None

    def connect(self) -> bool:
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            return True
        except ConnectionRefusedError:
            print(f"❌ Cannot connect to {self.host}:{self.port}")
            return False
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False

    def authenticate(self) -> bool:
        """Handle auth flow with server."""
        while True:
            line = self._recv_line()
            if not line:
                print("❌ Connection lost")
                return False

            if line.startswith("AUTH: Enter username:"):
                print(line[6:], end=" ", flush=True)
                self.username = input().strip()
                self._send_line(self.username)

            elif line.startswith("AUTH: New user."):
                print(f"\n📋 {line[6:]}")
                password = getpass.getpass("Password: ")
                self._send_line(password)

            elif line.startswith("AUTH: Password:"):
                password = getpass.getpass("Password: ")
                self._send_line(password)

            elif line.startswith("AUTH: Confirm password:"):
                confirm = getpass.getpass("Confirm password: ")
                self._send_line(confirm)

            elif line.startswith("AUTH_OK:"):
                # Check for key in the response
                msg = line[8:].strip()
                if "Your key" in msg and ":" in msg:
                    # Extract key from "Registered. Your key (store it): <key_b64>"
                    key_b64 = msg.split(":")[-1].strip()
                    try:
                        self.aes_key = base64.b64decode(key_b64)
                        save_key(self.username, key_b64, self.script_dir)
                        print(f"✅ {msg}")
                        print(f"🔑 Key saved to users/{self.username}/key.txt")
                    except Exception as e:
                        print(f"⚠️  Could not save key: {e}")
                else:
                    # Login: load key from file
                    self.aes_key = load_or_get_key(self.username, self.script_dir)
                    if not self.aes_key:
                        print("⚠️  No key file found. Messages will fail to decrypt.")
                    print(f"✅ {msg}")
                return True

            elif line.startswith("ERROR:"):
                print(f"❌ {line[7:]}")
                return False

            elif line.startswith("WELCOME:"):
                print(f"ℹ️  {line[8:].strip()}")
                return True

    def _receive_loop(self) -> None:
        while self.connected:
            line = self._recv_line()
            if line is None:
                print("\n[Disconnected from server]")
                self.connected = False
                break

            if line.startswith("WELCOME:"):
                print(f"\n✅ {line[8:].strip()}")
            elif line.startswith("SYSTEM:"):
                print(f"\n* {line[7:].strip()}")
            elif line.startswith("ERROR:"):
                print(f"\n❌ {line[6:].strip()}")
            else:
                # Assume encrypted message
                if self.aes_key:
                    try:
                        ciphertext, iv = decode_from_transmission(line)
                        plaintext = decrypt_message(ciphertext, iv, self.aes_key)
                        print(f"\n{plaintext}")
                    except Exception as e:
                        print(f"\n[Cannot decrypt message: {e}]")
                else:
                    print(f"\n[encrypted - no key available]")

    def run(self) -> None:
        if not self.connect():
            return

        print("=" * 60)
        print("🔐 Crypto Vibeness - Encrypted Chat Client (Jour 2)")
        print("=" * 60)

        if not self.authenticate():
            self.socket.close()
            return

        self.connected = True

        recv_thread = threading.Thread(target=self._receive_loop, daemon=True)
        recv_thread.start()

        print("\nType messages (encrypted with your key). /quit to exit.\n")

        try:
            while self.connected:
                try:
                    line = input()
                    if not self.connected:
                        break
                    if line.lower() == "/quit":
                        self._send_line("/quit")
                        break
                    if self.aes_key:
                        ciphertext, iv = encrypt_message(line, self.aes_key)
                        transmission = encode_for_transmission(ciphertext, iv)
                        self._send_line(transmission)
                    else:
                        print("❌ No encryption key available")
                except EOFError:
                    break
        except KeyboardInterrupt:
            pass
        finally:
            self.connected = False
            try:
                self.socket.close()
            except Exception:
                pass
            print("\n👋 Disconnected")


def main() -> None:
    host = DEFAULT_HOST
    port = DEFAULT_PORT
    if len(sys.argv) > 1:
        host = sys.argv[1]
    if len(sys.argv) > 2:
        try:
            port = int(sys.argv[2])
        except ValueError:
            print("Usage: client.py [host] [port]")
            sys.exit(1)
    client = EncryptedChatClient(host, port)
    client.run()


if __name__ == "__main__":
    main()
