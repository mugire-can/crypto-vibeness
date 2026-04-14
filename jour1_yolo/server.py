#!/usr/bin/env python3
"""
Crypto Vibeness - Jour 1: IRC-like Chat Server with Authentication and Rooms

Features:
- Multi-threaded socket server for multiple concurrent clients
- Room system with optional password protection
- Deterministic user colors via ANSI escape codes
- Message timestamps
- File logging (log_YYYY-MM-DD_HH-MM-SS.txt)
- Authentication: MD5/base64 passwords stored in this_is_safe.txt
- Password rules loaded from password_rules.json
- Constant-time password comparison
"""

import socket
import threading
import sys
import json
import logging
import hashlib
import hmac
import base64
import math
import string
import os
from datetime import datetime
from typing import Dict, Optional, Set

try:
    sys.path.insert(0, os.path.dirname(__file__))
    from config import (
        HOST_BIND, DEFAULT_PORT, MESSAGE_BUFFER_SIZE, ENCODING,
        SERVER_BACKLOG, COLORS, RESET, COLOR_SYSTEM,
        DEFAULT_ROOM, PASSWORD_FILE, PASSWORD_RULES_FILE
    )
except ImportError:
    HOST_BIND = "0.0.0.0"
    DEFAULT_PORT = 5000
    MESSAGE_BUFFER_SIZE = 4096
    ENCODING = "utf-8"
    SERVER_BACKLOG = 10
    COLORS = ['\033[31m', '\033[32m', '\033[33m', '\033[34m', '\033[35m', '\033[36m',
              '\033[91m', '\033[92m', '\033[93m', '\033[94m', '\033[95m', '\033[96m']
    RESET = '\033[0m'
    COLOR_SYSTEM = '\033[90m'
    DEFAULT_ROOM = "general"
    PASSWORD_FILE = "this_is_safe.txt"
    PASSWORD_RULES_FILE = "password_rules.json"

# States for client authentication
STATE_USERNAME = "auth_username"
STATE_PASSWORD = "auth_password"
STATE_CONFIRM = "auth_confirm"
STATE_CHATTING = "chatting"


def get_user_color(username: str) -> str:
    """Return a deterministic ANSI color code for a username."""
    idx = abs(hash(username)) % len(COLORS)
    return COLORS[idx]


def hash_password_md5(password: str) -> str:
    """Hash password with MD5 and return base64-encoded digest."""
    digest = hashlib.md5(password.encode(ENCODING)).digest()
    return base64.b64encode(digest).decode("ascii")


def compute_entropy(password: str) -> float:
    """Estimate password entropy in bits."""
    pool = 0
    if any(c.islower() for c in password):
        pool += 26
    if any(c.isupper() for c in password):
        pool += 26
    if any(c.isdigit() for c in password):
        pool += 10
    if any(c in string.punctuation for c in password):
        pool += 32
    if pool == 0:
        return 0.0
    return len(password) * math.log2(pool)


def password_strength_label(entropy: float) -> str:
    """Return a human-readable strength label based on entropy bits."""
    if entropy < 28:
        return "Very Weak"
    elif entropy < 36:
        return "Weak"
    elif entropy < 60:
        return "Fair"
    elif entropy < 80:
        return "Strong"
    else:
        return "Very Strong"


class PasswordManager:
    """Handles password storage and validation."""

    def __init__(self, password_file: str, rules_file: str):
        self.password_file = password_file
        self.rules = self._load_rules(rules_file)
        self._lock = threading.Lock()

    def _load_rules(self, rules_file: str) -> dict:
        try:
            with open(rules_file, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                "min_length": 8,
                "require_digit": True,
                "require_uppercase": True,
                "require_lowercase": True,
            }

    def check_rules(self, password: str) -> list:
        """Return list of violated rule descriptions. Empty = all rules pass."""
        violations = []
        min_len = self.rules.get("min_length", 8)
        if len(password) < min_len:
            violations.append(f"At least {min_len} characters required")
        if self.rules.get("require_digit", True) and not any(c.isdigit() for c in password):
            violations.append("At least 1 digit required")
        if self.rules.get("require_uppercase", True) and not any(c.isupper() for c in password):
            violations.append("At least 1 uppercase letter required")
        if self.rules.get("require_lowercase", False) and not any(c.islower() for c in password):
            violations.append("At least 1 lowercase letter required")
        if self.rules.get("require_special", False) and not any(c in string.punctuation for c in password):
            violations.append("At least 1 special character required")
        return violations

    def user_exists(self, username: str) -> bool:
        return username in self._load_db()

    def verify_password(self, username: str, password: str) -> bool:
        db = self._load_db()
        if username not in db:
            return False
        stored_hash = db[username]
        provided_hash = hash_password_md5(password)
        return hmac.compare_digest(stored_hash, provided_hash)

    def register_user(self, username: str, password: str) -> None:
        hashed = hash_password_md5(password)
        with self._lock:
            with open(self.password_file, "a") as f:
                f.write(f"{username}:{hashed}\n")

    def _load_db(self) -> Dict[str, str]:
        db = {}
        try:
            with open(self.password_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if ":" in line:
                        username, hashed = line.split(":", 1)
                        db[username] = hashed
        except FileNotFoundError:
            pass
        return db


class Room:
    """Represents a chat room."""

    def __init__(self, name: str, password: Optional[str] = None):
        self.name = name
        self.password_hash: Optional[str] = hash_password_md5(password) if password else None
        self.members: Set[str] = set()
        self._lock = threading.Lock()

    @property
    def is_protected(self) -> bool:
        return self.password_hash is not None

    def check_password(self, password: str) -> bool:
        if not self.is_protected:
            return True
        provided = hash_password_md5(password)
        return hmac.compare_digest(self.password_hash, provided)

    def add_member(self, username: str) -> None:
        with self._lock:
            self.members.add(username)

    def remove_member(self, username: str) -> None:
        with self._lock:
            self.members.discard(username)

    def get_members(self) -> list:
        with self._lock:
            return sorted(self.members)


class ChatServer:
    """Multi-threaded IRC-like chat server with auth and rooms."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.server_socket: Optional[socket.socket] = None
        self.running = True

        # user_socket[username] = socket
        self.user_sockets: Dict[str, socket.socket] = {}
        # user_room[username] = room_name
        self.user_rooms: Dict[str, str] = {}
        self.users_lock = threading.Lock()

        # rooms[name] = Room
        self.rooms: Dict[str, Room] = {}
        self.rooms_lock = threading.Lock()
        self._create_room(DEFAULT_ROOM, None)

        # Password management
        script_dir = os.path.dirname(os.path.abspath(__file__))
        pw_file = os.path.join(script_dir, PASSWORD_FILE)
        rules_file = os.path.join(script_dir, PASSWORD_RULES_FILE)
        self.password_manager = PasswordManager(pw_file, rules_file)

        # Set up file logger
        self._setup_file_logger()

    def _setup_file_logger(self) -> None:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        log_filename = os.path.join(script_dir, f"log_{ts}.txt")
        self.file_logger = logging.getLogger("chat_file")
        self.file_logger.setLevel(logging.INFO)
        fh = logging.FileHandler(log_filename)
        fh.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
        self.file_logger.addHandler(fh)
        self.file_logger.propagate = False
        self.file_logger.info(f"Server started on {self.host}:{self.port}")

    def _create_room(self, name: str, password: Optional[str]) -> Room:
        room = Room(name, password)
        with self.rooms_lock:
            self.rooms[name] = room
        return room

    def _send_json(self, sock: socket.socket, data: dict) -> bool:
        try:
            line = json.dumps(data) + "\n"
            sock.sendall(line.encode(ENCODING))
            return True
        except (BrokenPipeError, ConnectionResetError, OSError):
            return False

    def _recv_line(self, sock: socket.socket) -> Optional[str]:
        """Receive one line from socket."""
        data = b""
        try:
            while not data.endswith(b"\n"):
                chunk = sock.recv(1)
                if not chunk:
                    return None
                data += chunk
            return data.decode(ENCODING).strip()
        except Exception:
            return None

    def start(self) -> None:
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(SERVER_BACKLOG)
            logging.info(f"Server started on {self.host}:{self.port}")

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
            logging.error(f"Server error: {e}")
            self.shutdown()

    def _handle_client(self, sock: socket.socket, addr: tuple) -> None:
        username: Optional[str] = None
        try:
            # --- Authentication phase ---
            username = self._auth_phase(sock, addr)
            if not username:
                return

            # --- Chatting phase ---
            color = get_user_color(username)
            self._send_json(sock, {
                "type": "welcome",
                "color": color,
                "message": f"Welcome {username}! You are in #{DEFAULT_ROOM}. Type /help for commands."
            })

            # Add to default room
            with self.users_lock:
                self.user_sockets[username] = sock
                self.user_rooms[username] = DEFAULT_ROOM
            with self.rooms_lock:
                self.rooms[DEFAULT_ROOM].add_member(username)

            self._broadcast_room_system(DEFAULT_ROOM, f"{username} joined #{DEFAULT_ROOM}", exclude=None)
            self.file_logger.info(f"USER_JOIN username={username} room={DEFAULT_ROOM}")

            self._chat_loop(sock, username)

        except ConnectionResetError:
            logging.warning(f"Connection reset by {addr}")
        except Exception as e:
            logging.error(f"Error handling {addr}: {e}")
        finally:
            if username:
                self._disconnect_user(username)
            try:
                sock.close()
            except Exception:
                pass

    def _auth_phase(self, sock: socket.socket, addr: tuple) -> Optional[str]:
        """Handle authentication. Returns username on success, None on failure."""
        # Get username
        self._send_json(sock, {"type": "prompt", "key": "username", "message": "Enter username: "})
        username = self._recv_line(sock)
        if not username:
            return None
        username = username.strip()
        if not username or len(username) > 32 or not username.replace("_", "").replace("-", "").isalnum():
            self._send_json(sock, {"type": "error", "message": "Invalid username (alphanumeric, max 32 chars)"})
            return None

        with self.users_lock:
            if username in self.user_sockets:
                self._send_json(sock, {"type": "error", "message": f"Username '{username}' is already taken"})
                return None

        is_new_user = not self.password_manager.user_exists(username)

        # Get password
        self._send_json(sock, {
            "type": "prompt",
            "key": "password",
            "message": "Create password: " if is_new_user else "Password: ",
            "is_new_user": is_new_user
        })
        password = self._recv_line(sock)
        if not password:
            return None

        if is_new_user:
            # Check rules
            violations = self.password_manager.check_rules(password)
            if violations:
                self._send_json(sock, {
                    "type": "error",
                    "message": "Password does not meet requirements:\n  - " + "\n  - ".join(violations)
                })
                return None

            # Confirm password
            self._send_json(sock, {"type": "prompt", "key": "confirm_password", "message": "Confirm password: "})
            confirm = self._recv_line(sock)
            if not confirm or confirm != password:
                self._send_json(sock, {"type": "error", "message": "Passwords do not match"})
                return None

            # Register
            self.password_manager.register_user(username, password)
            entropy = compute_entropy(password)
            strength = password_strength_label(entropy)
            self._send_json(sock, {
                "type": "auth_result",
                "success": True,
                "message": f"Account created! Password strength: {strength} ({entropy:.0f} bits)"
            })
            self.file_logger.info(f"USER_REGISTER username={username} strength={strength}")
        else:
            # Verify
            if not self.password_manager.verify_password(username, password):
                self._send_json(sock, {"type": "error", "message": "Incorrect password"})
                return None
            self._send_json(sock, {"type": "auth_result", "success": True, "message": "Authentication successful"})
            self.file_logger.info(f"USER_LOGIN username={username} addr={addr}")

        return username

    def _chat_loop(self, sock: socket.socket, username: str) -> None:
        """Main chat loop for an authenticated user."""
        while self.running:
            line = self._recv_line(sock)
            if line is None:
                break
            line = line.strip()
            if not line:
                continue

            if line.startswith("/"):
                self._handle_command(sock, username, line)
                if line.lower() == "/quit":
                    break
            else:
                self._handle_message(username, line)

    def _handle_command(self, sock: socket.socket, username: str, line: str) -> None:
        parts = line.split()
        cmd = parts[0].lower()

        if cmd == "/quit":
            return

        elif cmd == "/rooms":
            with self.rooms_lock:
                rooms_info = []
                for name, room in self.rooms.items():
                    rooms_info.append({
                        "name": name,
                        "protected": room.is_protected,
                        "members": len(room.members)
                    })
            self._send_json(sock, {"type": "rooms_list", "rooms": rooms_info})

        elif cmd == "/users":
            with self.users_lock:
                room_name = self.user_rooms.get(username, DEFAULT_ROOM)
            with self.rooms_lock:
                room = self.rooms.get(room_name)
                members = room.get_members() if room else []
            self._send_json(sock, {"type": "users_list", "room": room_name, "users": members})

        elif cmd == "/join":
            if len(parts) < 2:
                self._send_json(sock, {"type": "error", "message": "Usage: /join <room> [password]"})
                return
            room_name = parts[1]
            password = parts[2] if len(parts) > 2 else None
            self._cmd_join(sock, username, room_name, password, create_if_missing=True)

        elif cmd == "/create":
            if len(parts) < 2:
                self._send_json(sock, {"type": "error", "message": "Usage: /create <room> [password]"})
                return
            room_name = parts[1]
            password = parts[2] if len(parts) > 2 else None
            with self.rooms_lock:
                if room_name in self.rooms:
                    self._send_json(sock, {"type": "error", "message": f"Room #{room_name} already exists"})
                    return
            self._create_room(room_name, password)
            self._send_json(sock, {"type": "system", "message": f"Room #{room_name} created"})
            self.file_logger.info(f"ROOM_CREATE room={room_name} protected={password is not None} by={username}")
            self._cmd_join(sock, username, room_name, password, create_if_missing=False)

        elif cmd == "/help":
            self._send_json(sock, {
                "type": "system",
                "message": "Commands: /join <room> [pass], /create <room> [pass], /rooms, /users, /quit"
            })
        else:
            self._send_json(sock, {"type": "error", "message": f"Unknown command: {cmd}"})

    def _cmd_join(self, sock: socket.socket, username: str, room_name: str,
                  password: Optional[str], create_if_missing: bool) -> None:
        with self.rooms_lock:
            if room_name not in self.rooms:
                if create_if_missing:
                    self.rooms[room_name] = Room(room_name, None)
                else:
                    self._send_json(sock, {"type": "error", "message": f"Room #{room_name} does not exist"})
                    return
            room = self.rooms[room_name]

        if room.is_protected and not room.check_password(password or ""):
            self._send_json(sock, {"type": "error", "message": "Incorrect room password"})
            return

        # Leave current room
        with self.users_lock:
            old_room = self.user_rooms.get(username, DEFAULT_ROOM)
        if old_room != room_name:
            with self.rooms_lock:
                if old_room in self.rooms:
                    self.rooms[old_room].remove_member(username)
            self._broadcast_room_system(old_room, f"{username} left #{old_room}", exclude=username)

        # Join new room
        room.add_member(username)
        with self.users_lock:
            self.user_rooms[username] = room_name

        self._send_json(sock, {"type": "system", "message": f"You joined #{room_name}"})
        self._broadcast_room_system(room_name, f"{username} joined #{room_name}", exclude=username)
        self.file_logger.info(f"USER_JOIN_ROOM username={username} room={room_name}")

    def _handle_message(self, username: str, message: str) -> None:
        with self.users_lock:
            room_name = self.user_rooms.get(username, DEFAULT_ROOM)
        color = get_user_color(username)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.file_logger.info(f"MSG room={room_name} from={username}: {message}")
        self._broadcast_room_chat(room_name, username, color, message, timestamp)

    def _broadcast_room_chat(self, room_name: str, username: str, color: str,
                              message: str, timestamp: str) -> None:
        data = {
            "type": "chat",
            "username": username,
            "color": color,
            "room": room_name,
            "message": message,
            "timestamp": timestamp
        }
        with self.rooms_lock:
            room = self.rooms.get(room_name)
            members = room.get_members() if room else []
        with self.users_lock:
            sockets = {u: self.user_sockets[u] for u in members if u in self.user_sockets}
        for u, s in sockets.items():
            self._send_json(s, data)

    def _broadcast_room_system(self, room_name: str, message: str, exclude: Optional[str]) -> None:
        data = {"type": "system", "message": message}
        with self.rooms_lock:
            room = self.rooms.get(room_name)
            members = room.get_members() if room else []
        with self.users_lock:
            sockets = {u: self.user_sockets[u] for u in members if u in self.user_sockets and u != exclude}
        for u, s in sockets.items():
            self._send_json(s, data)

    def _disconnect_user(self, username: str) -> None:
        with self.users_lock:
            room_name = self.user_rooms.pop(username, DEFAULT_ROOM)
            self.user_sockets.pop(username, None)
        with self.rooms_lock:
            if room_name in self.rooms:
                self.rooms[room_name].remove_member(username)
        self._broadcast_room_system(room_name, f"{username} left #{room_name}", exclude=None)
        self.file_logger.info(f"USER_LEAVE username={username} room={room_name}")

    def shutdown(self) -> None:
        self.running = False
        with self.users_lock:
            for s in self.user_sockets.values():
                try:
                    s.close()
                except Exception:
                    pass
            self.user_sockets.clear()
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
        self.file_logger.info("Server shutdown")
        sys.exit(0)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
    port = DEFAULT_PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("Usage: server.py [port]")
            sys.exit(1)
    server = ChatServer(HOST_BIND, port)
    server.start()


if __name__ == "__main__":
    main()
