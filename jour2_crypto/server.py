#!/usr/bin/env python3
"""
Crypto Vibeness - Jour 2: Encrypted Chat Server
Multi-threaded chat server with AES-256 symmetric encryption.

Features:
- Multi-threaded socket server
- AES-256-CBC encryption of all messages
- Password-based key derivation (PBKDF2)
- HMAC authentication for integrity
- Transparent encryption (server broadcasts encrypted messages)
- Comprehensive logging (encrypted data only)
"""

import socket
import threading
import sys
import logging
from typing import Dict, Optional

try:
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Configuration constants
DEFAULT_PORT = 5000
BUFFER_SIZE = 4096
ENCODING = 'utf-8'
HOST = '0.0.0.0'
DEFAULT_PASSWORD = 'password123'


class EncryptedChatServer:
    """Multi-threaded chat server with AES-256 encryption."""

    def __init__(self, host: str, port: int, password: str = DEFAULT_PASSWORD):
        """
        Initialize encrypted chat server.

        Args:
            host: Host address to bind to
            port: Port number to listen on
            password: Password for deriving encryption key
        """
        self.host = host
        self.port = port
        self.password = password
        self.encryption_key, _ = derive_key_from_password(password)
        self.server_socket: Optional[socket.socket] = None
        self.users: Dict[str, socket.socket] = {}
        self.users_lock = threading.Lock()
        self.running = True

    def start(self) -> None:
        """Start the server and accept connections."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            logger.info(f"🔒 Encrypted server started on {self.host}:{self.port}")
            logger.info(f"Encryption: AES-256-CBC with password-derived key")

            while self.running:
                try:
                    client_socket, client_address = self.server_socket.accept()
                    logger.info(f"Connection from {client_address}")
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, client_address),
                        daemon=False
                    )
                    client_thread.start()
                except OSError:
                    if self.running:
                        logger.error("Error accepting connection")
                        continue
                    break

        except KeyboardInterrupt:
            logger.info("\n⏹️  Server interrupt received (Ctrl+C)")
            self.shutdown()
        except Exception as e:
            logger.error(f"Server error: {e}")
            self.shutdown()

    def _handle_client(self, client_socket: socket.socket, client_address: tuple) -> None:
        """Handle a single client connection with encryption."""
        username: Optional[str] = None
        try:
            # Request username
            client_socket.send(b"Enter your username: ")
            username = client_socket.recv(BUFFER_SIZE).decode(ENCODING).strip()

            if not username:
                logger.warning(f"Client {client_address} provided empty username")
                client_socket.close()
                return

            # Check if username taken
            with self.users_lock:
                if username in self.users:
                    logger.warning(f"Username '{username}' already taken by {client_address}")
                    client_socket.send(b"Username already taken.\n")
                    client_socket.close()
                    return

                self.users[username] = client_socket
                logger.info(f"User '{username}' connected from {client_address}")

            # Notify join
            self._broadcast_system_message(f"[{username}] has joined")

            # Send welcome
            welcome_msg = f"✅ Welcome {username}! Encryption enabled (AES-256). Type /quit to exit.\n"
            client_socket.send(welcome_msg.encode(ENCODING))

            # Receive and broadcast messages
            while self.running:
                try:
                    encrypted_message = client_socket.recv(BUFFER_SIZE).decode(ENCODING).strip()

                    if not encrypted_message:
                        break

                    # Try to decrypt for command processing
                    try:
                        ciphertext, iv = decode_from_transmission(encrypted_message)
                        plaintext = decrypt_message(ciphertext, iv, self.encryption_key)
                    except Exception:
                        logger.warning(f"Failed to decrypt message from {username}")
                        continue

                    # Check for /quit command
                    if plaintext.startswith('/quit'):
                        logger.info(f"User '{username}' requested to quit")
                        break

                    # Broadcast encrypted message
                    self._broadcast_encrypted_message(username, encrypted_message)

                except Exception as e:
                    logger.error(f"Error receiving from {username}: {e}")
                    break

        except ConnectionResetError:
            logger.warning(f"Connection reset by {client_address}")
        except UnicodeDecodeError:
            logger.error(f"Invalid UTF-8 from {client_address}")
        except Exception as e:
            logger.error(f"Error handling client {client_address}: {e}")
        finally:
            # Cleanup
            if username:
                with self.users_lock:
                    if username in self.users:
                        del self.users[username]
                        logger.info(f"User '{username}' disconnected")

                self._broadcast_system_message(f"[{username}] has left")

            try:
                client_socket.close()
            except Exception:
                pass

    def _broadcast_encrypted_message(self, username: str, encrypted_message: str) -> None:
        """Broadcast an encrypted message to all clients."""
        # Format message for broadcast
        formatted_message = f"{username}: {encrypted_message}\n"
        logger.info(f"Message from '{username}': [encrypted: {encrypted_message[:50]}...]")
        self._send_to_all(formatted_message)

    def _broadcast_system_message(self, message: str) -> None:
        """Broadcast a system message (encrypted)."""
        try:
            # Encrypt the system message
            ciphertext, iv = encrypt_message(message, self.encryption_key)
            transmission = encode_for_transmission(ciphertext, iv)
            formatted = f"{transmission}\n"
            logger.info(f"System: {message}")
            self._send_to_all(formatted)
        except Exception as e:
            logger.error(f"Error broadcasting system message: {e}")

    def _send_to_all(self, message: str) -> None:
        """Send message to all connected users."""
        message_bytes = message.encode(ENCODING)
        with self.users_lock:
            disconnected_users = []
            for username, user_socket in self.users.items():
                try:
                    user_socket.send(message_bytes)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    logger.warning(f"Failed to send to '{username}'")
                    disconnected_users.append(username)

            # Cleanup disconnected sockets
            for username in disconnected_users:
                if username in self.users:
                    del self.users[username]

    def shutdown(self) -> None:
        """Gracefully shut down the server."""
        logger.info("Initiating graceful shutdown...")
        self.running = False

        # Close all client connections
        with self.users_lock:
            for username, user_socket in list(self.users.items()):
                try:
                    user_socket.close()
                    logger.info(f"Closed connection for '{username}'")
                except Exception as e:
                    logger.error(f"Error closing '{username}': {e}")
            self.users.clear()

        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
                logger.info("Server socket closed")
            except Exception as e:
                logger.error(f"Error closing server socket: {e}")

        logger.info("Server shutdown complete")
        sys.exit(0)


def parse_arguments() -> tuple[int, str]:
    """Parse command-line arguments."""
    port = DEFAULT_PORT
    password = DEFAULT_PASSWORD

    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
            if not (1 <= port <= 65535):
                print("❌ Error: Port must be between 1 and 65535")
                sys.exit(1)
        except ValueError:
            print("❌ Error: Port must be an integer")
            sys.exit(1)

    if len(sys.argv) > 2:
        password = sys.argv[2]

    return port, password


def main() -> None:
    """Main entry point for the encrypted chat server."""
    port, password = parse_arguments()
    server = EncryptedChatServer(HOST, port, password)
    server.start()


if __name__ == "__main__":
    main()
