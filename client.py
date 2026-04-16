#!/usr/bin/env python3
"""
CRYPTO VIBENESS - Unified Client
Supports progressive security levels: YOLO → SYMMETRIC → ASYMMETRIC → ECDH

Usage:
    python3 client.py [--host HOST] [--port PORT] [--level LEVEL]

Examples:
    python3 client.py                              # YOLO
    python3 client.py --level symmetric --port 5001
    python3 client.py --level asymmetric --port 5002
    python3 client.py --level ecdh --port 5003
"""

import socket
import threading
import sys
import json
import argparse
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from cryptography.hazmat.primitives import serialization

from config import *
from crypto_utils import (
    derive_key_pbkdf2,
    encrypt_aes_cbc, decrypt_aes_cbc,
    encrypt_aes_gcm, decrypt_aes_gcm,
    generate_rsa_keypair, save_rsa_private_key, load_rsa_private_key,
    save_rsa_public_key, load_rsa_public_key,
    public_key_to_pem, pem_to_public_key,
    rsa_encrypt, rsa_decrypt, rsa_sign, rsa_verify,
    generate_ecdh_keypair, ecdh_shared_secret, derive_session_key_from_secret,
    ecdsa_sign, ecdsa_verify, generate_ecdsa_keypair,
    encode_for_transmission, decode_from_transmission
)
from notifications import (
    get_notifications, set_notification_settings,
    notify_message, notify_user_joined, notify_user_left,
    notify_error, notify_success, notify_encrypted
)


# ============================================================================
# UNIFIED CRYPTO CLIENT
# ============================================================================

class CryptoChatClient:
    """Unified chat client supporting all security levels."""
    
    def __init__(self, host: str, port: int, level: str):
        self.host = host
        self.port = port
        self.level = level.upper()
        self.socket: Optional[socket.socket] = None
        self.username: Optional[str] = None
        self.running = True
        self.current_room = DEFAULT_ROOM
        
        # Notification settings
        self.notifications = get_notifications()
        self.enable_notifications = True
        
        # Encryption state
        self.encryption_key: Optional[bytes] = None
        self.per_user_keys: Dict[str, bytes] = {}  # For asymmetric mode
        self.session_keys: Dict[str, bytes] = {}
        self.peer_public_keys: Dict[str, Any] = {}
        
        # Asymmetric cryptography
        self.rsa_private_key = None
        self.rsa_public_key = None
        
        # ECDH cryptography
        self.ecdh_private_key = None
        self.ecdh_public_key = None
        self.ecdsa_private_key = None
        self.ecdsa_public_key = None
        
        print(f"\n{COLOR_SUCCESS}═══════════════════════════════════════════════════════════{RESET}")
        print(f"{COLOR_SUCCESS}         📱 Crypto Vibeness - Chat Client{RESET}")
        print(f"{COLOR_SUCCESS}═══════════════════════════════════════════════════════════{RESET}")
        print(f"{COLOR_SYSTEM}Security Level: {self.level}{RESET}")
        print(f"{COLOR_SYSTEM}Features: {', '.join(SECURITY_LEVELS[self.level]['features'])}{RESET}")
        print(f"{COLOR_SYSTEM}Server: {self.host}:{self.port}{RESET}\n")
        
        # Setup keys for non-YOLO modes
        if self.level != "YOLO":
            self._setup_cryptography()
    
    def _setup_cryptography(self):
        """Initialize cryptographic keys based on security level."""
        key_dir = STORAGE_KEYS / self.username if self.username else STORAGE_KEYS
        key_dir.mkdir(parents=True, exist_ok=True)
        
        if self.level == "ASYMMETRIC":
            self._setup_rsa_keys(key_dir)
        elif self.level == "ECDH":
            self._setup_ecdh_keys(key_dir)
    
    def _setup_rsa_keys(self, key_dir: Path):
        """Setup or load RSA keypair."""
        private_key_path = key_dir / f"id_rsa{PRIVATE_KEY_EXTENSION}"
        public_key_path = key_dir / f"id_rsa{PUBLIC_KEY_EXTENSION}"
        
        if private_key_path.exists() and public_key_path.exists():
            try:
                self.rsa_private_key = load_rsa_private_key(str(private_key_path))
                self.rsa_public_key = load_rsa_public_key(str(public_key_path))
                print(f"{COLOR_SUCCESS}✓ Loaded existing RSA keypair{RESET}")
                return
            except:
                pass
        
        # Generate new keypair
        print(f"{COLOR_SYSTEM}Generating RSA-2048 keypair...{RESET}")
        self.rsa_private_key, self.rsa_public_key = generate_rsa_keypair()
        save_rsa_private_key(self.rsa_private_key, str(private_key_path))
        save_rsa_public_key(self.rsa_public_key, str(public_key_path))
        print(f"{COLOR_SUCCESS}✓ Generated and saved RSA keypair{RESET}")
    
    def _setup_ecdh_keys(self, key_dir: Path):
        """Setup or load ECDH and ECDSA keypairs."""
        ecdh_private_path = key_dir / f"ecdh{PRIVATE_KEY_EXTENSION}"
        ecdsa_private_path = key_dir / f"ecdsa{PRIVATE_KEY_EXTENSION}"
        
        # ECDH
        if ecdh_private_path.exists():
            try:
                with open(ecdh_private_path, 'rb') as f:
                    self.ecdh_private_key = \
                        X25519PrivateKey.from_private_bytes(f.read())
                self.ecdh_public_key = self.ecdh_private_key.public_key()
                print(f"{COLOR_SUCCESS}✓ Loaded ECDH keypair{RESET}")
            except:
                pass
        
        if not self.ecdh_private_key:
            print(f"{COLOR_SYSTEM}Generating ECDH X25519 keypair...{RESET}")
            from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
            self.ecdh_private_key = X25519PrivateKey.generate()
            self.ecdh_public_key = self.ecdh_private_key.public_key()
            with open(ecdh_private_path, 'wb') as f:
                f.write(self.ecdh_private_key.private_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PrivateFormat.Raw,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            print(f"{COLOR_SUCCESS}✓ Generated ECDH keypair{RESET}")
        
        # ECDSA
        if ecdsa_private_path.exists():
            try:
                with open(ecdsa_private_path, 'rb') as f:
                    self.ecdsa_private_key = \
                        serialization.load_pem_private_key(f.read(), password=None)
                self.ecdsa_public_key = self.ecdsa_private_key.public_key()
                print(f"{COLOR_SUCCESS}✓ Loaded ECDSA keypair{RESET}")
            except:
                pass
        
        if not self.ecdsa_private_key:
            print(f"{COLOR_SYSTEM}Generating ECDSA P-256 keypair...{RESET}")
            self.ecdsa_private_key, self.ecdsa_public_key = generate_ecdsa_keypair()
            with open(ecdsa_private_path, 'wb') as f:
                f.write(self.ecdsa_private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            print(f"{COLOR_SUCCESS}✓ Generated ECDSA keypair{RESET}")
    
    def connect(self):
        """Connect to server."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            print(f"{COLOR_SUCCESS}✓ Connected to {self.host}:{self.port}{RESET}\n")
            return True
        except Exception as e:
            print(f"{COLOR_ERROR}✗ Connection failed: {e}{RESET}", file=sys.stderr)
            return False
    
    def authenticate(self) -> bool:
        """Authenticate with server."""
        print(f"{COLOR_SYSTEM}🔐 Authentication Phase{RESET}\n")
        
        # Get username
        while not self.username:
            username = input(f"{COLOR_SYSTEM}Enter username: {RESET}").strip()
            if not username or len(username) > MAX_USERNAME_LENGTH:
                print(f"{COLOR_ERROR}Invalid username{RESET}")
                continue
            self.username = username
            self._send("AUTH_RESPONSE", username)
        
        # Update crypto setup with username
        if self.level != "YOLO":
            self._setup_cryptography()
        
        # Authentication loop  
        password = None
        while True:
            msg_type, content = self._receive()
            
            if msg_type == "AUTH_RESPONSE":
                if content.startswith("error:"):
                    print(f"{COLOR_ERROR}{content[6:]}{RESET}")
                    if self.enable_notifications:
                        self.notifications.notify_error(content[6:])
                    return False
                elif content.startswith("success:"):
                    print(f"{COLOR_SUCCESS}{content[8:]}{RESET}\n")
                    # Derive encryption key for SYMMETRIC mode
                    if self.level == "SYMMETRIC" and password:
                        self.encryption_key, _ = derive_key_pbkdf2(password)
                        print(f"{COLOR_SUCCESS}✓ Encryption key derived{RESET}\n")
                        if self.enable_notifications:
                            self.notifications.notify_encrypted("password-based key")
                    if self.enable_notifications:
                        self.notifications.notify_success("Authentication successful!")
                    return True
                    
            elif msg_type == "AUTH_REQUEST":
                if "password" in content.lower():
                    password = input(f"{COLOR_SYSTEM}{content} {RESET}").strip()
                    self._send("AUTH_RESPONSE", password)
                else:
                    # Server response to username
                    pass
    
    def run(self):
        """Main client loop."""
        # Start receiver thread
        receiver_thread = threading.Thread(target=self._receive_loop, daemon=True)
        receiver_thread.start()
        
        # Main input loop
        print(f"{COLOR_SYSTEM}Type messages or commands:${RESET}")
        print(f"{COLOR_SYSTEM}/help - show commands, /quit - exit{RESET}\n")
        
        try:
            while self.running:
                try:
                    message = input(f"{self.username}> ").strip()
                    if not message:
                        continue
                    
                    if message.startswith('/'):
                        self._handle_command(message)
                    else:
                        self._send_message(message)
                        
                except KeyboardInterrupt:
                    print()
                    self._send("MESSAGE", "/quit")
                    break
                except EOFError:
                    break
                    
        except Exception as e:
            print(f"{COLOR_ERROR}Error: {e}{RESET}", file=sys.stderr)
        finally:
            self.running = False
            if self.socket:
                self.socket.close()
    
    def _handle_command(self, command: str):
        """Handle client-side commands."""
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        if cmd == "/quit":
            self._send("MESSAGE", "/quit")
            self.running = False
            print(f"{COLOR_SYSTEM}Goodbye!{RESET}")
            
        elif cmd == "/rooms":
            self._send("MESSAGE", "/rooms")
            
        elif cmd == "/users":
            self._send("MESSAGE", "/users")
            
        elif cmd == "/join":
            room_name = args.split()[0] if args else None
            password = args.split()[1] if len(args.split()) > 1 else None
            if room_name:
                cmd_str = f"/join {room_name}"
                if password:
                    cmd_str += f" {password}"
                self._send("MESSAGE", cmd_str)
            else:
                print(f"{COLOR_ERROR}Usage: /join <room> [password]{RESET}")
                
        elif cmd == "/create":
            room_parts = args.split(maxsplit=1)
            room_name = room_parts[0] if room_parts else None
            password = room_parts[1] if len(room_parts) > 1 else None
            if room_name:
                cmd_str = f"/create {room_name}"
                if password:
                    cmd_str += f" {password}"
                self._send("MESSAGE", cmd_str)
            else:
                print(f"{COLOR_ERROR}Usage: /create <room> [password]{RESET}")
                
        elif cmd == "/help":
            help_text = """
Commands:
  /join <room> [password]  - Join a room
  /create <room> [password] - Create a room
  /rooms                   - List all rooms
  /users                   - List online users
  /notifications [on/off]  - Toggle notifications (default: on)
  /quit                    - Disconnect
  /help                    - Show this help
            """
            print(f"{COLOR_SYSTEM}{help_text}{RESET}")
        
        elif cmd == "/notifications":
            if args.lower() == "off":
                self.enable_notifications = False
                print(f"{COLOR_SYSTEM}Notifications disabled{RESET}")
            elif args.lower() == "on":
                self.enable_notifications = True
                print(f"{COLOR_SYSTEM}Notifications enabled{RESET}")
            else:
                status = "enabled" if self.enable_notifications else "disabled"
                print(f"{COLOR_SYSTEM}Notifications are {status}. Use /notifications [on/off]{RESET}")
        else:
            print(f"{COLOR_ERROR}Unknown command: {cmd}{RESET}")
    
    def _send_message(self, message: str):
        """Send encrypted/formatted message with AES-256-GCM for SYMMETRIC mode."""
        if len(message) > MAX_MESSAGE_LENGTH:
            print(f"{COLOR_ERROR}Message too long (max {MAX_MESSAGE_LENGTH} chars){RESET}")
            return
        
        # Display message locally immediately (don't wait for echo from server)
        timestamp = datetime.now().strftime("%H:%M:%S")
        local_color = get_user_color(self.username)
        formatted = f"[{timestamp}] {local_color}{self.username}{RESET}: {message}"
        print(f"\n{formatted}")
        print(f"{self.username}> ", end="", flush=True)
        
        # Apply encryption based on level
        if self.level == "SYMMETRIC":
            # Per-user encryption with AES-256-GCM (more secure)
            if self.encryption_key:
                try:
                    encrypted = encrypt_aes_gcm(message, self.encryption_key)
                    encoded = encode_for_transmission(encrypted)
                    self._send("MESSAGE", encoded)
                except Exception as e:
                    print(f"{COLOR_ERROR}Encryption error: {e}{RESET}")
            else:
                print(f"{COLOR_ERROR}Encryption key not initialized{RESET}")
        else:
            # Other levels: plain transmission for now (would implement asymmetric)
            self._send("MESSAGE", message)
    
    def _receive_loop(self):
        """Background thread for receiving messages."""
        while self.running:
            try:
                msg_type, content = self._receive()
                if not msg_type:
                    continue
                
                if msg_type == "MESSAGE":
                    # Extract username from message if format is "username: message"
                    if ':' in content and ': ' in content:
                        username_part, msg_part = content.split(': ', 1)
                        # Check for mentions
                        is_mention = f"@{self.username}" in msg_part or self.username.lower() in msg_part.lower()
                    else:
                        username_part = "User"
                        msg_part = content
                        is_mention = False
                    
                    # Send notification if enabled
                    if self.enable_notifications:
                        self.notifications.notify_new_message(username_part, msg_part, is_mention)
                    
                    print(f"\n{content}")
                    print(f"{self.username}> ", end="", flush=True)
                    
                elif msg_type == "SYSTEM":
                    # Parse system messages for user join/leave events
                    if "joined the chat" in content.lower() or "joined" in content.lower():
                        if self.enable_notifications:
                            self.notifications.notify_user_joined("User")
                    elif "left" in content.lower():
                        if self.enable_notifications:
                            self.notifications.notify_user_left("User")
                    
                    print(f"\n{COLOR_SYSTEM}{content}{RESET}")
                    print(f"{self.username}> ", end="", flush=True)
                    
                elif msg_type == "ROOMS":
                    try:
                        rooms = json.loads(content)
                        print(f"\n{COLOR_SYSTEM}Available Rooms:{RESET}")
                        for room in rooms:
                            print(f"  • {room}")
                        print(f"{self.username}> ", end="", flush=True)
                    except:
                        pass
                        
                elif msg_type == "USERS":
                    try:
                        users = json.loads(content)
                        print(f"\n{COLOR_SYSTEM}Online Users:{RESET}")
                        for user in users:
                            print(f"  • {user}")
                        print(f"{self.username}> ", end="", flush=True)
                    except:
                        pass
                        
                elif msg_type == "ERROR":
                    print(f"\n{COLOR_ERROR}✗ {content}{RESET}")
                    print(f"{self.username}> ", end="", flush=True)
                    
            except Exception as e:
                if self.running:
                    print(f"{COLOR_ERROR}Receive error: {e}{RESET}", file=sys.stderr)
                break
    
    def _send(self, msg_type: str, content: str):
        """Send message to server with encryption based on security level."""
        try:
            # For SYMMETRIC mode, encrypt the content
            if self.level == "SYMMETRIC" and msg_type == "MESSAGE":
                if self.encryption_key:
                    try:
                        encrypted = encrypt_aes_gcm(content, self.encryption_key)
                        content = encode_for_transmission(encrypted)
                    except Exception as e:
                        print(f"{COLOR_ERROR}Encryption error: {e}{RESET}", file=sys.stderr)
                        return
            
            message = f"{msg_type}:{content}\n"
            self.socket.sendall(message.encode(ENCODING))
        except Exception as e:
            print(f"{COLOR_ERROR}Send error: {e}{RESET}", file=sys.stderr)
    
    def _receive(self) -> tuple:
        """Receive message from server with decryption based on security level."""
        try:
            data = self.socket.recv(MESSAGE_BUFFER_SIZE).decode(ENCODING).strip()
            if not data:
                return None, None
            
            parts = data.split(':', 1)
            msg_type = parts[0]
            content = parts[1] if len(parts) > 1 else ""
            
            # For SYMMETRIC mode, decrypt MESSAGE content
            if self.level == "SYMMETRIC" and msg_type == "MESSAGE":
                if self.encryption_key and content:
                    try:
                        encrypted = decode_from_transmission(content)
                        content = decrypt_aes_gcm(encrypted, self.encryption_key)
                    except Exception as e:
                        print(f"{COLOR_ERROR}Decryption error: {e}{RESET}", file=sys.stderr)
                        return None, None
            
            return msg_type, content
        except:
            return None, None


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Crypto Vibeness - Unified Client',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 client.py                              # YOLO on localhost:5000
  python3 client.py --level symmetric --port 5001
  python3 client.py --level asymmetric --port 5002
  python3 client.py --host 192.168.1.100 --port 5000
        """
    )
    
    parser.add_argument('--host', default=DEFAULT_HOST,
                       help=f'Server host (default: {DEFAULT_HOST})')
    parser.add_argument('--port', type=int, default=None,
                       help='Server port')
    parser.add_argument('--level', choices=['yolo', 'symmetric', 'asymmetric', 'ecdh'],
                       default='yolo', help='Security level (default: yolo)')
    
    args = parser.parse_args()
    
    # Determine port
    if args.port is None:
        args.port = SECURITY_LEVELS[args.level.upper()]['port']
    
    # Create and run client
    client = CryptoChatClient(args.host, args.port, args.level)
    
    if client.connect():
        if client.authenticate():
            client.run()
    
    print(f"{COLOR_SYSTEM}Disconnected.{RESET}")


if __name__ == '__main__':
    main()
