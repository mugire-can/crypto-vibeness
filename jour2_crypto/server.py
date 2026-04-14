#!/usr/bin/env python3
"""
Crypto Vibeness - Jour 2: Encrypted Chat Server with Per-User Keys and Argon2

Features:
- Argon2 password hashing (falls back to scrypt)
- Per-user AES-256 key generation from PBKDF2-SHA256
- Server decrypts incoming messages and re-encrypts for each recipient
- Password file: this_is_safe.txt (username:algo:cost:salt_b64:hash_b64)
- Keys file: user_keys_do_not_steal_plz.txt (username:aes_key_b64:salt_b64)
"""

import socket
import threading
import sys
import json
import logging
import hmac as hmac_module
import os
import base64
import hashlib

try:
    from argon2.low_level import hash_secret_raw, Type
    ARGON2_AVAILABLE = True
except ImportError:
    ARGON2_AVAILABLE = False

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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

HOST = '0.0.0.0'
DEFAULT_PORT = 5000
BUFFER_SIZE = 4096
ENCODING = 'utf-8'
PASSWORD_FILE = 'this_is_safe.txt'
KEYS_FILE = 'user_keys_do_not_steal_plz.txt'

# Argon2 parameters
ARGON2_TIME_COST = 3
ARGON2_MEMORY_COST = 65536
ARGON2_PARALLELISM = 2
ARGON2_HASH_LEN = 32
ARGON2_SALT_LEN = 16  # 128 bits > 96 bits minimum

# scrypt fallback parameters
SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_SALT_LEN = 16


def hash_password(password: str) -> str:
    """Hash password with argon2 (or scrypt fallback). Returns 'algo:cost:salt_b64:hash_b64'."""
    salt = os.urandom(ARGON2_SALT_LEN)
    if ARGON2_AVAILABLE:
        h = hash_secret_raw(
            secret=password.encode(),
            salt=salt,
            time_cost=ARGON2_TIME_COST,
            memory_cost=ARGON2_MEMORY_COST,
            parallelism=ARGON2_PARALLELISM,
            hash_len=ARGON2_HASH_LEN,
            type=Type.ID
        )
        salt_b64 = base64.b64encode(salt).decode("ascii")
        hash_b64 = base64.b64encode(h).decode("ascii")
        return f"argon2:{ARGON2_TIME_COST}:{salt_b64}:{hash_b64}"
    else:
        dk = hashlib.scrypt(
            password.encode(), salt=salt,
            n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32
        )
        salt_b64 = base64.b64encode(salt).decode("ascii")
        hash_b64 = base64.b64encode(dk).decode("ascii")
        return f"scrypt:{SCRYPT_N}:{salt_b64}:{hash_b64}"


def verify_password(password: str, stored: str) -> bool:
    """Verify password against stored hash string. Constant-time comparison."""
    try:
        parts = stored.split(":")
        algo = parts[0]
        cost = int(parts[1])
        salt = base64.b64decode(parts[2])
        expected_hash = base64.b64decode(parts[3])

        if algo == "argon2" and ARGON2_AVAILABLE:
            h = hash_secret_raw(
                secret=password.encode(),
                salt=salt,
                time_cost=cost,
                memory_cost=ARGON2_MEMORY_COST,
                parallelism=ARGON2_PARALLELISM,
                hash_len=ARGON2_HASH_LEN,
                type=Type.ID
            )
        elif algo == "scrypt":
            h = hashlib.scrypt(
                password.encode(), salt=salt,
                n=cost, r=SCRYPT_R, p=SCRYPT_P, dklen=32
            )
        else:
            return False

        return hmac_module.compare_digest(h, expected_hash)
    except Exception:
        return False


class UserDatabase:
    """Thread-safe user password and key storage."""

    def __init__(self, script_dir: str):
        self.pw_file = os.path.join(script_dir, PASSWORD_FILE)
        self.keys_file = os.path.join(script_dir, KEYS_FILE)
        self._lock = threading.Lock()

    def user_exists(self, username: str) -> bool:
        return username in self._load_passwords()

    def register(self, username: str, password: str) -> bytes:
        """Register new user. Returns the AES key."""
        pw_hash = hash_password(password)
        # Generate per-user AES-256 key
        key_salt = os.urandom(16)
        aes_key, _ = derive_key_from_password(password, key_salt)
        with self._lock:
            with open(self.pw_file, "a") as f:
                f.write(f"{username}:{pw_hash}\n")
            with open(self.keys_file, "a") as f:
                key_b64 = base64.b64encode(aes_key).decode("ascii")
                salt_b64 = base64.b64encode(key_salt).decode("ascii")
                f.write(f"{username}:{key_b64}:{salt_b64}\n")
        return aes_key

    def authenticate(self, username: str, password: str) -> bool:
        db = self._load_passwords()
        if username not in db:
            return False
        return verify_password(password, db[username])

    def get_user_key(self, username: str) -> bytes:
        """Return the AES-256 key for a user."""
        with open(self.keys_file, "r") as f:
            for line in f:
                parts = line.strip().split(":")
                if len(parts) == 3 and parts[0] == username:
                    return base64.b64decode(parts[1])
        raise KeyError(f"No key for user {username}")

    def _load_passwords(self) -> dict:
        db = {}
        try:
            with open(self.pw_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    # format: username:algo:cost:salt:hash
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        db[parts[0]] = parts[1]
        except FileNotFoundError:
            pass
        return db


class EncryptedChatServer:
    """Encrypted chat server with per-user keys and argon2 authentication."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = True
        self.users: dict = {}  # username -> socket
        self.users_lock = threading.Lock()
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.db = UserDatabase(script_dir)

    def _send_line(self, sock: socket.socket, text: str) -> bool:
        try:
            sock.sendall((text + "\n").encode(ENCODING))
            return True
        except Exception:
            return False

    def _recv_line(self, sock: socket.socket) -> str:
        """Receive one line from socket."""
        data = b""
        try:
            while not data.endswith(b"\n"):
                chunk = sock.recv(1)
                if not chunk:
                    return ""
                data += chunk
            return data.decode(ENCODING).strip()
        except Exception:
            return ""

    def start(self) -> None:
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            algo = "argon2" if ARGON2_AVAILABLE else "scrypt"
            logger.info(f"🔒 Encrypted server started on {self.host}:{self.port} (auth: {algo})")

            while self.running:
                try:
                    client_socket, addr = self.server_socket.accept()
                    t = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, addr),
                        daemon=True
                    )
                    t.start()
                except OSError:
                    if self.running:
                        continue
                    break
        except KeyboardInterrupt:
            self.shutdown()
        except Exception as e:
            logger.error(f"Server error: {e}")
            self.shutdown()

    def _handle_client(self, sock: socket.socket, addr: tuple) -> None:
        username = None
        aes_key = None
        try:
            username, aes_key = self._auth_phase(sock, addr)
            if not username:
                return

            with self.users_lock:
                if username in self.users:
                    self._send_line(sock, "ERROR: Username already connected")
                    return
                self.users[username] = sock

            self._broadcast_system(f"[{username}] has joined", exclude=username)
            self._send_line(sock, f"WELCOME: Encrypted chat ready. AES-256-CBC with your personal key. /quit to exit.")

            self._chat_loop(sock, username, aes_key)

        except ConnectionResetError:
            logger.warning(f"Connection reset by {addr}")
        except Exception as e:
            logger.error(f"Error handling {addr}: {e}")
        finally:
            if username:
                with self.users_lock:
                    self.users.pop(username, None)
                self._broadcast_system(f"[{username}] has left", exclude=None)
            try:
                sock.close()
            except Exception:
                pass

    def _auth_phase(self, sock: socket.socket, addr: tuple):
        """Returns (username, aes_key) or (None, None)."""
        self._send_line(sock, "AUTH: Enter username:")
        username = self._recv_line(sock)
        if not username:
            return None, None

        is_new = not self.db.user_exists(username)
        if is_new:
            self._send_line(sock, "AUTH: New user. Create password (min 8 chars, 1 digit, 1 uppercase):")
        else:
            self._send_line(sock, "AUTH: Password:")

        password = self._recv_line(sock)
        if not password:
            return None, None

        if is_new:
            if len(password) < 8 or not any(c.isdigit() for c in password) or not any(c.isupper() for c in password):
                self._send_line(sock, "ERROR: Password does not meet requirements")
                return None, None

            self._send_line(sock, "AUTH: Confirm password:")
            confirm = self._recv_line(sock)
            if confirm != password:
                self._send_line(sock, "ERROR: Passwords do not match")
                return None, None

            aes_key = self.db.register(username, password)
            key_b64 = base64.b64encode(aes_key).decode("ascii")
            self._send_line(sock, f"AUTH_OK: Registered. Your key (store it): {key_b64}")
            logger.info(f"User '{username}' registered")
        else:
            if not self.db.authenticate(username, password):
                self._send_line(sock, "ERROR: Incorrect password")
                return None, None
            aes_key = self.db.get_user_key(username)
            self._send_line(sock, "AUTH_OK: Authenticated")
            logger.info(f"User '{username}' authenticated")

        return username, aes_key

    def _chat_loop(self, sock: socket.socket, username: str, aes_key: bytes) -> None:
        while self.running:
            line = self._recv_line(sock)
            if not line:
                break
            if line.lower() == "/quit":
                break
            # Decrypt incoming message
            try:
                ciphertext, iv = decode_from_transmission(line)
                plaintext = decrypt_message(ciphertext, iv, aes_key)
            except Exception as e:
                logger.warning(f"Decrypt failed from {username}: {e}")
                continue

            logger.info(f"Message from '{username}': {plaintext}")
            # Re-encrypt for each recipient with their own key
            self._broadcast_encrypted(username, plaintext)

    def _broadcast_encrypted(self, sender: str, plaintext: str) -> None:
        """Re-encrypt message for each recipient using their key."""
        formatted = f"{sender}: {plaintext}"
        with self.users_lock:
            recipients = list(self.users.items())
        for uname, sock in recipients:
            try:
                user_key = self.db.get_user_key(uname)
                ciphertext, iv = encrypt_message(formatted, user_key)
                transmission = encode_for_transmission(ciphertext, iv)
                self._send_line(sock, transmission)
            except Exception as e:
                logger.warning(f"Failed to send to {uname}: {e}")

    def _broadcast_system(self, message: str, exclude: str) -> None:
        """Broadcast system message (plaintext, prefixed with SYSTEM:)."""
        with self.users_lock:
            sockets = {u: s for u, s in self.users.items() if u != exclude}
        for u, s in sockets.items():
            self._send_line(s, f"SYSTEM: {message}")

    def shutdown(self) -> None:
        self.running = False
        with self.users_lock:
            for s in self.users.values():
                try:
                    s.close()
                except Exception:
                    pass
            self.users.clear()
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
        sys.exit(0)


def main() -> None:
    port = DEFAULT_PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("Usage: server.py [port]")
            sys.exit(1)
    server = EncryptedChatServer(HOST, port)
    server.start()


if __name__ == "__main__":
    main()
