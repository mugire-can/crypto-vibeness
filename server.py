#!/usr/bin/env python3
"""
CRYPTO VIBENESS - Unified Multi-Level Chat Server
Supports progressive security levels: YOLO → SYMMETRIC → ASYMMETRIC → ECDH

Usage:
    python3 server.py [--port PORT] [--level LEVEL] [--help]

Examples:
    python3 server.py                              # Default: YOLO on port 5000
    python3 server.py --level symmetric --port 5001
    python3 server.py --level asymmetric --port 5002
    python3 server.py --level ecdh --port 5003
"""

import socket
import threading
import sys
import json
import logging
import os
import time
import argparse
from datetime import datetime
from typing import Dict, Optional, Set, Tuple, Any
from pathlib import Path
import struct

from config import *
from crypto_utils import (
    hash_password_md5, verify_password_md5,
    hash_password_modern, verify_password_modern,
    derive_key_pbkdf2,
    encrypt_aes_cbc, decrypt_aes_cbc,
    encrypt_aes_gcm, decrypt_aes_gcm,
    rsa_sign, rsa_verify,
    generate_rsa_keypair, save_rsa_public_key, load_rsa_public_key,
    public_key_to_pem, pem_to_public_key,
    ecdh_shared_secret, derive_session_key_from_secret,
    ecdsa_sign, ecdsa_verify,
    encode_for_transmission, decode_from_transmission
)


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging(security_level: str):
    """Setup file and console logging with proper directory creation."""
    # Create logs directory
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    log_file = logs_dir / f"server_{security_level}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__), str(log_file)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def compute_password_entropy(password: str) -> float:
    """Estimate password entropy in bits."""
    pool = 0
    if any(c.islower() for c in password):
        pool += 26
    if any(c.isupper() for c in password):
        pool += 26
    if any(c.isdigit() for c in password):
        pool += 10
    if any(c in "!@#$%^&*()-_=+[]{}|;:,.<>?" for c in password):
        pool += 32
    
    if pool == 0:
        return 0.0
    
    return len(password) * (pool.bit_length() - 1)


def get_password_strength(entropy: float) -> str:
    """Return password strength as string and ANSI color."""
    if entropy < 30:
        return f"{COLOR_ERROR}Weak{RESET}", "Weak"
    elif entropy < 50:
        return f"{COLOR_WARNING}Fair{RESET}", "Fair"
    elif entropy < 70:
        return f"{COLOR_SUCCESS}Strong{RESET}", "Strong"
    else:
        return f"{COLOR_SUCCESS}Very Strong{RESET}", "Very Strong"


# ============================================================================
# PASSWORD MANAGEMENT
# ============================================================================

def load_password_rules() -> Dict[str, Any]:
    """Load password validation rules from JSON file."""
    try:
        if os.path.exists(PASSWORD_RULES_FILE):
            with open(PASSWORD_RULES_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        pass
    
    # Default rules
    return {
        "min_length": 8,
        "require_digit": True,
        "require_uppercase": True,
        "require_lowercase": True,
        "require_special": False
    }


def validate_password(password: str, rules: Dict) -> Tuple[bool, str]:
    """Validate password against rules. Returns: (is_valid, error_message)"""
    if len(password) < rules.get("min_length", 8):
        return False, f"Password must be at least {rules.get('min_length', 8)} characters"
    
    if rules.get("require_digit") and not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"
    
    if rules.get("require_uppercase") and not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    
    if rules.get("require_lowercase") and not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    
    if rules.get("require_special") and not any(c in "!@#$%^&*()-_=+" for c in password):
        return False, "Password must contain at least one special character"
    
    return True, ""


# ============================================================================
# CLIENT HANDLER
# ============================================================================

class ClientHandler:
    """Handles individual client connections."""
    
    def __init__(self, socket_obj: socket.socket, addr: Tuple, server: 'ChatServer'):
        self.socket = socket_obj
        self.address = addr
        self.server = server
        self.username: Optional[str] = None
        self.current_room: str = DEFAULT_ROOM
        self.is_authenticated = False
        self.color = ""
        self.session_key: Optional[bytes] = None  # For encrypted modes
        self.public_key = None  # For asymmetric modes
        
    def run(self):
        """Main client handling loop."""
        try:
            # Authentication phase
            if not self._authenticate():
                self.server.logger.warning(f"Authentication failed for {self.address}")
                self._send_error("Authentication failed")
                return
            
            self.is_authenticated = True
            self.color = get_user_color(self.username)
            self.server.logger.info(f"{self.username} authenticated from {self.address}")
            
            # Register user in server's users dictionary
            with self.server.users_lock:
                self.server.users[self.username] = self
            
            # Add user to default room
            with self.server.rooms_lock:
                if self.current_room not in self.server.rooms:
                    self.server.rooms[self.current_room] = {
                        "password": None,
                        "users": set(),
                        "created_at": datetime.now().isoformat()
                    }
                self.server.rooms[self.current_room]["users"].add(self.username)
            
            # Notify others
            self._broadcast_system(f"{self.color}{self.username}{RESET} has joined the chat")
            
            # Main chat loop
            self._chat_loop()
            
        except Exception as e:
            self.server.logger.error(f"Error handling {self.address}: {e}")
        finally:
            self._cleanup()
    
    def _authenticate(self) -> bool:
        """Handle user authentication."""
        # Request username
        self._send_message("AUTH_REQUEST", "Enter your username: ")
        raw_username = self._receive_message()
        
        # Parse protocol format if present
        if ':' in raw_username:
            parts = raw_username.split(':', 1)
            username = parts[1]
        else:
            username = raw_username
        
        if not username or len(username) > MAX_USERNAME_LENGTH:
            return False
        
        # Check if username taken
        if username in self.server.users:
            self._send_message("AUTH_RESPONSE", "error:Username already taken")
            return False
        
        self.username = username
        self.server.logger.info(f"Username registered: {username}")
        
        # Request/verify password
        password_rules = load_password_rules()
        
        if self._is_user_exists(username):
            # Existing user - verify password
            stored_hash = self.server._get_password_hash(username)
            if not stored_hash:
                return False
            
            for attempt in range(3):
                self._send_message("AUTH_REQUEST", "Enter your password: ")
                raw_password = self._receive_message()
                
                # Parse protocol format if present
                if ':' in raw_password:
                    parts = raw_password.split(':', 1)
                    password = parts[1]
                else:
                    password = raw_password
                
                if self._verify_password(username, password, stored_hash):
                    self._send_message("AUTH_RESPONSE", "success:Welcome back!")
                    # Derive encryption key for SYMMETRIC mode
                    if self.server.security_level == "SYMMETRIC":
                        self.session_key, _ = derive_key_pbkdf2(password)
                        self.server.logger.info(f"Encryption key derived for {username}")
                    return True
                else:
                    remaining = 2 - attempt
                    self._send_message("AUTH_RESPONSE", f"error:Wrong password. {remaining} attempts remaining")
            
            return False
        else:
            # New user - registration
            self._send_message("AUTH_REQUEST", "First time? Create a password: ")
            raw_password = self._receive_message()
            
            # Parse protocol format if present
            if ':' in raw_password:
                parts = raw_password.split(':', 1)
                password = parts[1]
            else:
                password = raw_password
            
            # Validate password
            is_valid, error_msg = validate_password(password, password_rules)
            if not is_valid:
                self._send_message("AUTH_RESPONSE", f"error:{error_msg}")
                return False
            
            # Calculate entropy and strength
            entropy = compute_password_entropy(password)
            strength_colored, strength_text = get_password_strength(entropy)
            
            self._send_message("AUTH_REQUEST", f"Password strength: {strength_colored} ({entropy:.0f} bits). Confirm password: ")
            raw_password_confirm = self._receive_message()
            
            # Parse protocol format if present
            if ':' in raw_password_confirm:
                parts = raw_password_confirm.split(':', 1)
                password_confirm = parts[1]
            else:
                password_confirm = raw_password_confirm
            
            if password != password_confirm:
                self._send_message("AUTH_RESPONSE", "error:Passwords don't match")
                return False
            
            # Store password
            self.server._store_password(username, password)
            self._send_message("AUTH_RESPONSE", f"success:Account created! Strength: {strength_text}")
            # Derive encryption key for SYMMETRIC mode
            if self.server.security_level == "SYMMETRIC":
                self.session_key, _ = derive_key_pbkdf2(password)
                self.server.logger.info(f"Encryption key derived for {username}")
            return True
    
    def _is_user_exists(self, username: str) -> bool:
        """Check if user exists in password file."""
        try:
            with open(PASSWORD_FILE, 'r') as f:
                for line in f:
                    if line.startswith(f"{username}:"):
                        return True
        except FileNotFoundError:
            pass
        return False
    
    def _chat_loop(self):
        """Main chat message loop."""
        while self.is_authenticated:
            try:
                raw_message = self._receive_message()
                if not raw_message:
                    continue
                
                # Parse protocol format: TYPE:content
                parts = raw_message.split(':', 1)
                msg_type = parts[0]
                content = parts[1] if len(parts) > 1 else ""
                
                # Handle commands vs messages
                if content.startswith('/'):
                    self._handle_command(content)
                elif msg_type == "MESSAGE":
                    # Regular message
                    self._process_message(content)
                else:
                    # Other message types (shouldn't happen in chat loop)
                    pass
                    
            except (socket.error, ConnectionResetError):
                break
    
    def _handle_command(self, command: str):
        """Process user commands."""
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        if cmd == COMMANDS['QUIT']:
            self._send_message("SYSTEM", "Goodbye!")
            self.is_authenticated = False
            
        elif cmd == COMMANDS['ROOMS']:
            rooms = list(self.server.rooms.keys())
            self._send_message("ROOMS", json.dumps(rooms))
            
        elif cmd == COMMANDS['USERS']:
            users = list(self.server.users.keys())
            self._send_message("USERS", json.dumps(users))
            
        elif cmd == COMMANDS['JOIN']:
            room_name = args.split()[0] if args else DEFAULT_ROOM
            password = args.split()[1] if len(args.split()) > 1 else None
            self._join_room(room_name, password)
            
        elif cmd == COMMANDS['CREATE']:
            parts_args = args.split(maxsplit=1)
            room_name = parts_args[0] if parts_args else None
            password = parts_args[1] if len(parts_args) > 1 else None
            self._create_room(room_name, password)
            
        elif cmd == COMMANDS['HELP']:
            help_text = "Commands: /quit, /rooms, /users, /join <room> [password], /create <room> [password], /help"
            self._send_message("SYSTEM", help_text)
        else:
            self._send_message("ERROR", "Unknown command")
    
    def _join_room(self, room_name: str, password: Optional[str]):
        """Join a room."""
        with self.server.rooms_lock:
            if room_name not in self.server.rooms:
                self._send_message("ERROR", f"Room {room_name} does not exist")
                return
            
            room_info = self.server.rooms[room_name]
            if room_info.get("password") and room_info["password"] != password:
                self._send_message("ERROR", "Wrong room password")
                return
            
            # Remove from old room
            if self.current_room in self.server.rooms:
                self.server.rooms[self.current_room]["users"].discard(self.username)
            
            # Add to new room
            self.current_room = room_name
            self.server.rooms[room_name]["users"].add(self.username)
        
        self._broadcast_system(f"{self.color}{self.username}{RESET} joined {room_name}")
        self.server.logger.info(f"{self.username} joined {room_name}")
    
    def _create_room(self, room_name: str, password: Optional[str]):
        """Create a new room."""
        if not room_name or len(room_name) > MAX_ROOM_NAME_LENGTH:
            self._send_message("ERROR", "Invalid room name")
            return
        
        with self.server.rooms_lock:
            if room_name in self.server.rooms:
                self._send_message("ERROR", f"Room {room_name} already exists")
                return
            
            self.server.rooms[room_name] = {
                "password": password,
                "users": {self.username},
                "created_at": datetime.now().isoformat()
            }
            
            # Remove from old room
            if self.current_room and self.current_room != room_name and self.current_room in self.server.rooms:
                self.server.rooms[self.current_room]["users"].discard(self.username)
            
            self.current_room = room_name
        
        self._send_message("SYSTEM", f"Created room {room_name}")
        self.server.logger.info(f"{self.username} created room {room_name}")
    
    def _process_message(self, message: str):
        """Process and broadcast chat message."""
        if len(message) > MAX_MESSAGE_LENGTH:
            self._send_message("ERROR", "Message too long")
            return
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {self.color}{self.username}{RESET}: {message}"
        
        # Broadcast to room (exclude sender to prevent duplication)
        self._broadcast_to_room(formatted, exclude_user=self.username)
        self.server.logger.info(f"[{self.current_room}] {self.username}: {message}")
    
    def _broadcast_to_room(self, message: str, exclude_user: Optional[str] = None):
        """Broadcast message to all users in current room (optionally excluding sender)."""
        with self.server.rooms_lock:
            room_users = self.server.rooms.get(self.current_room, {}).get("users", set()).copy()
        
        for username in room_users:
            # Skip broadcast to sender to prevent duplication
            if exclude_user and username == exclude_user:
                continue
            
            with self.server.users_lock:
                if username in self.server.users:
                    try:
                        self.server.users[username]._send_message("MESSAGE", message)
                    except:
                        pass
    
    def _broadcast_system(self, message: str):
        """Broadcast system message to all users in room."""
        with self.server.rooms_lock:
            room_users = self.server.rooms.get(self.current_room, {}).get("users", set()).copy()
        
        for username in room_users:
            with self.server.users_lock:
                if username in self.server.users:
                    try:
                        self.server.users[username]._send_message("SYSTEM", message)
                    except:
                        pass
    
    def _send_message(self, msg_type: str, content: str):
        """Send message to client with encryption based on security level."""
        try:
            # For SYMMETRIC mode, encrypt MESSAGE content
            if self.server.security_level == "SYMMETRIC" and msg_type == "MESSAGE" and self.session_key:
                try:
                    encrypted = encrypt_aes_gcm(content, self.session_key)
                    content = encode_for_transmission(encrypted)
                except Exception as e:
                    self.server.logger.error(f"Encryption error: {e}")
                    return
            
            msg = f"{msg_type}:{content}\n"
            self.socket.sendall(msg.encode(ENCODING))
        except:
            pass
    
    def _receive_message(self) -> str:
        """Receive message from client with decryption based on security level."""
        try:
            data = self.socket.recv(MESSAGE_BUFFER_SIZE).decode(ENCODING).strip()
            
            # For SYMMETRIC mode, decrypt if message matches encrypted pattern
            if self.server.security_level == "SYMMETRIC" and self.session_key and data:
                # Check if it looks like an encrypted message (contains ':')
                parts = data.split(':', 1)
                if len(parts) == 2:
                    msg_type, content = parts
                    if msg_type == "MESSAGE" and content:
                        try:
                            encrypted = decode_from_transmission(content)
                            decrypted = decrypt_aes_gcm(encrypted, self.session_key)
                            data = f"{msg_type}:{decrypted}"
                        except Exception as e:
                            self.server.logger.warning(f"Decryption error: {e}")
                            return ""
            
            return data
        except:
            return ""
    
    def _send_error(self, msg: str):
        """Send error message."""
        self._send_message("ERROR", msg)
    
    def _verify_password(self, username: str, password: str, stored_hash: str) -> bool:
        """Verify password against stored hash."""
        if self.server.security_level == "YOLO":
            return verify_password_md5(password, stored_hash)
        else:
            # Modern password verification
            parts = stored_hash.split(':')
            if len(parts) >= 3:
                algorithm = parts[0]
                salt_b64 = parts[1] if len(parts) > 2 else None
                hash_val = parts[2] if len(parts) > 2 else parts[1]
                return verify_password_modern(password, hash_val, salt_b64, algorithm)
            return False
    
    def _cleanup(self):
        """Clean up when client disconnects."""
        if self.username:
            # Remove from rooms and users with proper locking
            with self.server.rooms_lock:
                for room_name, room_info in self.server.rooms.items():
                    room_info["users"].discard(self.username)
            
            with self.server.users_lock:
                if self.username in self.server.users:
                    del self.server.users[self.username]
            
            # Notify others
            if self.current_room:
                self._broadcast_system(f"{self.color}{self.username}{RESET} has left")
            
            self.server.logger.info(f"{self.username} disconnected from {self.address}")
        
        self.socket.close()


# ============================================================================
# MAIN SERVER
# ============================================================================

class ChatServer:
    """Unified Multi-Level Chat Server."""
    
    def __init__(self, port: int, security_level: str):
        self.port = port
        self.security_level = security_level.upper()
        self.running = True
        
        # Logging
        self.logger, self.log_file = setup_logging(self.security_level)
        
        # State
        self.users: Dict[str, ClientHandler] = {}
        self.rooms: Dict[str, Dict] = {
            DEFAULT_ROOM: {"password": None, "users": set(), "created_at": datetime.now().isoformat()}
        }
        self.users_lock = threading.Lock()
        self.rooms_lock = threading.Lock()
        
        # Server socket
        self.server_socket = None
        
        self.logger.info(f"===== Chat Server Starting =====")
        self.logger.info(f"Security Level: {self.security_level}")
        self.logger.info(f"Features: {', '.join(SECURITY_LEVELS[self.security_level]['features'])}")
        self.logger.info(f"Description: {SECURITY_LEVELS[self.security_level]['description']}")
    
    def start(self):
        """Start the server."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((HOST_BIND, self.port))
            self.server_socket.listen(SERVER_BACKLOG)
            
            print(f"\n{COLOR_SUCCESS}✓ Server started on {HOST_BIND}:{self.port}{RESET}")
            print(f"{COLOR_SUCCESS}✓ Security level: {self.security_level}{RESET}")
            print(f"{COLOR_SYSTEM}💡 Accepting connections...{RESET}\n")
            self.logger.info(f"Server listening on {HOST_BIND}:{self.port}")
            
            while self.running:
                try:
                    client_socket, addr = self.server_socket.accept()
                    self.logger.info(f"New connection from {addr}")
                    
                    handler = ClientHandler(client_socket, addr, self)
                    thread = threading.Thread(target=handler.run, daemon=True)
                    
                    with self.users_lock:
                        # Register user (temporary until authenticated)
                        pass
                    
                    thread.start()
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    self.logger.error(f"Error accepting connection: {e}")
                    
        except Exception as e:
            self.logger.error(f"Server error: {e}")
            print(f"{COLOR_ERROR}✗ Server error: {e}{RESET}", file=sys.stderr)
        finally:
            self.stop()
    
    def stop(self):
        """Stop the server gracefully."""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        self.logger.info("Server stopped")
    
    def _get_password_hash(self, username: str) -> Optional[str]:
        """Get password hash from file."""
        try:
            with open(PASSWORD_FILE, 'r') as f:
                for line in f:
                    if line.startswith(f"{username}:"):
                        parts = line.strip().split(':', 1)
                        if len(parts) > 1:
                            return parts[1]
        except:
            pass
        return None
    
    def _store_password(self, username: str, password: str):
        """Store password hash in file."""
        try:
            # Store with appropriate hashing based on security level
            if self.security_level == "YOLO":
                password_hash = hash_password_md5(password)
                line = f"{username}:{password_hash}\n"
            else:
                hash_result, salt_b64, algorithm, cost = hash_password_modern(password)
                if salt_b64:
                    line = f"{username}:{algorithm}:{salt_b64}:{hash_result}\n"
                else:
                    # Argon2 includes salt in hash
                    line = f"{username}:{algorithm}:::{hash_result}\n"
            
            with open(PASSWORD_FILE, 'a') as f:
                f.write(line)
        except Exception as e:
            self.logger.error(f"Error storing password: {e}")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Crypto Vibeness - Unified Multi-Level Chat Server',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 server.py                              # YOLO on port 5000
  python3 server.py --level symmetric --port 5001
  python3 server.py --level asymmetric --port 5002
  python3 server.py --level ecdh --port 5003
        """
    )
    
    parser.add_argument('--port', type=int, default=None,
                       help=f'Port to listen on (default: auto-assigned for level)')
    parser.add_argument('--level', choices=['yolo', 'symmetric', 'asymmetric', 'ecdh'],
                       default='yolo', help='Security level (default: yolo)')
    parser.add_argument('--host', default=HOST_BIND,
                       help=f'Host to bind to (default: {HOST_BIND})')
    
    args = parser.parse_args()
    
    # Determine port
    if args.port is None:
        args.port = SECURITY_LEVELS[args.level.upper()]['port']
    
    # Start server
    server = ChatServer(args.port, args.level)
    try:
        server.start()
    except KeyboardInterrupt:
        print(f"\n{COLOR_SYSTEM}Shutting down...{RESET}")
        server.stop()


if __name__ == '__main__':
    main()
