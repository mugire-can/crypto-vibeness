#!/usr/bin/env python3
"""
Crypto Vibeness - Jour 2: Encrypted Chat Client
Chat client with AES-256 symmetric encryption.

Features:
- Connect to server with encryption
- Password-based key derivation (PBKDF2)
- AES-256-CBC encryption of all messages
- HMAC authentication for integrity
- Non-blocking I/O with threading
- Transparent encryption (user sees plaintext)
"""

import socket
import threading
import sys
import queue
import logging
from typing import Optional

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
DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 5000
BUFFER_SIZE = 4096
ENCODING = 'utf-8'
DEFAULT_PASSWORD = 'password123'


class EncryptedChatClient:
    """Encrypted chat client with AES-256 symmetric encryption."""

    def __init__(self, host: str, port: int):
        """
        Initialize encrypted chat client.

        Args:
            host: Server host address
            port: Server port number
        """
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.connected = False
        self.username: Optional[str] = None
        self.encryption_key: Optional[bytes] = None
        self.message_queue: queue.Queue = queue.Queue()
        self.input_lock = threading.Lock()

    def connect(self) -> bool:
        """Connect to the server."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.connected = True
            logger.info(f"Connected to {self.host}:{self.port}")
            return True
        except ConnectionRefusedError:
            print(f"\n❌ Error: Could not connect to {self.host}:{self.port}")
            print("   Make sure the server is running.")
            logger.error(f"Connection refused to {self.host}:{self.port}")
            return False
        except Exception as e:
            print(f"\n❌ Connection error: {e}")
            logger.error(f"Failed to connect: {e}")
            return False

    def get_username(self) -> bool:
        """Request username from server and get user input."""
        try:
            prompt = self.socket.recv(BUFFER_SIZE).decode(ENCODING)
            if prompt:
                print(prompt, end='', flush=True)

            self.username = input().strip()

            if not self.username:
                print("❌ Username cannot be empty.")
                logger.warning("User provided empty username")
                return False

            self.socket.send(self.username.encode(ENCODING))

            response = self.socket.recv(BUFFER_SIZE).decode(ENCODING)
            if response:
                print(response, end='', flush=True)

            if "already taken" in response.lower() or "closed" in response.lower():
                logger.warning(f"Username '{self.username}' rejected by server")
                return False

            logger.info(f"Username set to '{self.username}'")
            return True

        except Exception as e:
            print(f"\n❌ Error during username setup: {e}")
            logger.error(f"Error during username negotiation: {e}")
            return False

    def setup_encryption(self) -> bool:
        """Setup encryption with password."""
        try:
            with self.input_lock:
                password = input("\n🔐 Enter encryption password (default: password123): ").strip()
                if not password:
                    password = DEFAULT_PASSWORD

            # Derive key from password
            self.encryption_key, _ = derive_key_from_password(password)
            logger.info("Encryption key derived from password")
            print("✅ Encryption key configured")
            return True

        except Exception as e:
            print(f"\n❌ Error setting up encryption: {e}")
            logger.error(f"Error deriving key: {e}")
            return False

    def receive_messages(self) -> None:
        """Receive and decrypt messages from server."""
        try:
            while self.connected:
                try:
                    encrypted_message = self.socket.recv(BUFFER_SIZE).decode(ENCODING)
                    if not encrypted_message:
                        self.message_queue.put(None)
                        break

                    try:
                        # Decode transmission format
                        ciphertext, iv = decode_from_transmission(encrypted_message)
                        # Decrypt message
                        plaintext = decrypt_message(ciphertext, iv, self.encryption_key)
                        self.message_queue.put(plaintext)
                    except ValueError as e:
                        logger.warning(f"Decryption failed: {e}")
                        self.message_queue.put(f"⚠️  Failed to decrypt message: {str(e)}")
                    except Exception as e:
                        logger.error(f"Error decrypting: {e}")
                        self.message_queue.put(None)

                except socket.timeout:
                    continue
        except Exception as e:
            logger.error(f"Error receiving messages: {e}")
            self.message_queue.put(None)
        finally:
            self.connected = False

    def display_messages(self) -> None:
        """Display decrypted messages to the user."""
        while self.connected:
            try:
                message = self.message_queue.get(timeout=0.1)
                if message is None:
                    break
                with self.input_lock:
                    print(message, end='', flush=True)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error displaying message: {e}")
                break

    def send_message(self, plaintext: str) -> None:
        """Encrypt and send a message."""
        try:
            # Encrypt the message
            ciphertext, iv = encrypt_message(plaintext, self.encryption_key)
            # Encode for transmission
            transmission = encode_for_transmission(ciphertext, iv)
            # Send encrypted message
            self.socket.send(transmission.encode(ENCODING))
            logger.debug(f"Sent encrypted message")
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self.connected = False

    def handle_user_input(self) -> None:
        """Handle user input in main thread."""
        try:
            while self.connected:
                try:
                    with self.input_lock:
                        user_input = input()

                    if not user_input:
                        continue

                    # Handle commands
                    if user_input.lower() == '/quit':
                        logger.info("User requested quit")
                        self.send_message(user_input)
                        break

                    # Send regular message (encrypted)
                    self.send_message(user_input)

                except EOFError:
                    logger.info("EOF received from stdin")
                    break
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error(f"Error in user input handler: {e}")
        finally:
            self.connected = False

    def disconnect(self) -> None:
        """Disconnect from the server gracefully."""
        self.connected = False
        try:
            if self.socket:
                self.socket.close()
                logger.info("Socket closed")
        except Exception as e:
            logger.error(f"Error closing socket: {e}")

    def run(self) -> None:
        """Run the client main loop."""
        # Connect to server
        if not self.connect():
            return

        # Get username
        if not self.get_username():
            self.disconnect()
            return

        # Setup encryption
        if not self.setup_encryption():
            self.disconnect()
            return

        self.connected = True

        # Start receive thread
        receive_thread = threading.Thread(
            target=self.receive_messages,
            daemon=True
        )
        receive_thread.start()

        # Start display thread
        display_thread = threading.Thread(
            target=self.display_messages,
            daemon=True
        )
        display_thread.start()

        # Handle user input in main thread
        self.handle_user_input()

        # Disconnect
        self.disconnect()
        print("\n👋 Disconnected from server")


def parse_arguments() -> tuple[str, int]:
    """Parse command-line arguments for host and port."""
    host = DEFAULT_HOST
    port = DEFAULT_PORT

    if len(sys.argv) > 1:
        host = sys.argv[1]

    if len(sys.argv) > 2:
        try:
            port = int(sys.argv[2])
            if not (1 <= port <= 65535):
                print("❌ Error: Port must be between 1 and 65535")
                sys.exit(1)
        except ValueError:
            print("❌ Error: Port must be an integer")
            sys.exit(1)

    return host, port


def main() -> None:
    """Main entry point for the encrypted chat client."""
    host, port = parse_arguments()

    if len(sys.argv) == 1:
        print("=" * 60)
        print("🔐 Crypto Vibeness - Encrypted Chat Client (Jour 2)")
        print("=" * 60)
        print(f"Connecting to {host}:{port}...")
        print("Encryption: AES-256-CBC with PBKDF2 key derivation")
        print("Commands: /quit (exit)")
        print("=" * 60)

    client = EncryptedChatClient(host, port)
    client.run()


if __name__ == "__main__":
    main()
