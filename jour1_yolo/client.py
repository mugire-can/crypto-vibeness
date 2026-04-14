#!/usr/bin/env python3
"""
Crypto Vibeness - Jour 1: IRC-like Chat Client with Authentication and Rooms

Features:
- Connect to server, authenticate (register or login)
- Color-coded messages (server assigns colors)
- Timestamped messages
- Commands: /join, /create, /rooms, /users, /quit, /help
- Non-blocking receive/send with threading
"""

import socket
import threading
import sys
import json
import getpass
import logging
from typing import Optional

try:
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from config import DEFAULT_HOST, DEFAULT_PORT, MESSAGE_BUFFER_SIZE, ENCODING, RESET, COLOR_SYSTEM, COLOR_ERROR
except ImportError:
    DEFAULT_HOST = "localhost"
    DEFAULT_PORT = 5000
    MESSAGE_BUFFER_SIZE = 4096
    ENCODING = "utf-8"
    RESET = '\033[0m'
    COLOR_SYSTEM = '\033[90m'
    COLOR_ERROR = '\033[31m'

logging.basicConfig(level=logging.WARNING)


class ChatClient:
    """Chat client that communicates with server using JSON protocol."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.connected = False
        self.username: Optional[str] = None
        self.my_color: str = RESET
        self._recv_buffer = b""
        self._recv_lock = threading.Lock()
        self._print_lock = threading.Lock()

    def _send_line(self, text: str) -> bool:
        try:
            self.socket.sendall((text + "\n").encode(ENCODING))
            return True
        except Exception:
            self.connected = False
            return False

    def _recv_json_line(self) -> Optional[dict]:
        """Read one JSON line from socket."""
        try:
            while b"\n" not in self._recv_buffer:
                chunk = self.socket.recv(MESSAGE_BUFFER_SIZE)
                if not chunk:
                    return None
                self._recv_buffer += chunk
            idx = self._recv_buffer.index(b"\n")
            line = self._recv_buffer[:idx]
            self._recv_buffer = self._recv_buffer[idx + 1:]
            return json.loads(line.decode(ENCODING))
        except Exception:
            return None

    def _print(self, text: str) -> None:
        with self._print_lock:
            print(text)

    def connect(self) -> bool:
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            return True
        except ConnectionRefusedError:
            print(f"❌ Cannot connect to {self.host}:{self.port}. Is the server running?")
            return False
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False

    def authenticate(self) -> bool:
        """Handle authentication flow with server."""
        while True:
            msg = self._recv_json_line()
            if not msg:
                print("❌ Connection lost during authentication")
                return False

            mtype = msg.get("type")

            if mtype == "prompt":
                key = msg.get("key", "")
                prompt_text = msg.get("message", "")
                is_new = msg.get("is_new_user", False)

                if key == "username":
                    print(prompt_text, end="", flush=True)
                    value = input().strip()
                    self.username = value
                    self._send_line(value)

                elif key == "password":
                    if is_new:
                        print("\n📋 Password requirements:")
                        print("  - At least 8 characters")
                        print("  - At least 1 digit")
                        print("  - At least 1 uppercase letter")
                    value = getpass.getpass(prompt_text)
                    self._send_line(value)

                elif key == "confirm_password":
                    value = getpass.getpass(prompt_text)
                    self._send_line(value)

                else:
                    print(prompt_text, end="", flush=True)
                    value = input()
                    self._send_line(value)

            elif mtype == "error":
                print(f"{COLOR_ERROR}❌ {msg.get('message', 'Error')}{RESET}")
                return False

            elif mtype == "auth_result":
                if msg.get("success"):
                    print(f"✅ {msg.get('message', 'OK')}")
                    return True
                else:
                    print(f"{COLOR_ERROR}❌ {msg.get('message', 'Auth failed')}{RESET}")
                    return False

    def _receive_loop(self) -> None:
        """Receive messages from server and display them."""
        while self.connected:
            msg = self._recv_json_line()
            if msg is None:
                self._print(f"\n{COLOR_SYSTEM}[Disconnected from server]{RESET}")
                self.connected = False
                break

            mtype = msg.get("type")

            if mtype == "welcome":
                self.my_color = msg.get("color", RESET)
                self._print(f"\n{COLOR_SYSTEM}{'=' * 50}{RESET}")
                self._print(f"{COLOR_SYSTEM}{msg.get('message', '')}{RESET}")
                self._print(f"{COLOR_SYSTEM}{'=' * 50}{RESET}")

            elif mtype == "chat":
                color = msg.get("color", RESET)
                username = msg.get("username", "?")
                ts = msg.get("timestamp", "")
                message = msg.get("message", "")
                self._print(f"{COLOR_SYSTEM}[{ts}]{RESET} {color}{username}{RESET}: {message}")

            elif mtype == "system":
                self._print(f"{COLOR_SYSTEM}* {msg.get('message', '')}{RESET}")

            elif mtype == "error":
                self._print(f"{COLOR_ERROR}❌ {msg.get('message', '')}{RESET}")

            elif mtype == "rooms_list":
                rooms = msg.get("rooms", [])
                self._print(f"\n{COLOR_SYSTEM}--- Available Rooms ---{RESET}")
                for r in rooms:
                    lock = " 🔒" if r.get("protected") else ""
                    count = r.get("members", 0)
                    self._print(f"  #{r['name']}{lock} ({count} users)")
                self._print(f"{COLOR_SYSTEM}----------------------{RESET}")

            elif mtype == "users_list":
                room = msg.get("room", "")
                users = msg.get("users", [])
                self._print(f"\n{COLOR_SYSTEM}--- Users in #{room} ---{RESET}")
                for u in users:
                    self._print(f"  {u}")
                self._print(f"{COLOR_SYSTEM}--------------------{RESET}")

    def run(self) -> None:
        if not self.connect():
            return

        print("=" * 50)
        print("📱 Crypto Vibeness - Chat Client (Jour 1)")
        print("=" * 50)

        if not self.authenticate():
            self.socket.close()
            return

        self.connected = True

        recv_thread = threading.Thread(target=self._receive_loop, daemon=True)
        recv_thread.start()

        print(f"\nCommands: /join <room> [pass], /create <room> [pass], /rooms, /users, /quit, /help")
        print("Type messages and press Enter to send.\n")

        try:
            while self.connected:
                try:
                    line = input()
                    if not self.connected:
                        break
                    if line.lower() == "/quit":
                        self._send_line("/quit")
                        break
                    self._send_line(line)
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
    client = ChatClient(host, port)
    client.run()


if __name__ == "__main__":
    main()
