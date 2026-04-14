#!/usr/bin/env python3
"""
Crypto Vibeness - Day 1: IRC-like Chat Client
A basic multi-user chat client without security features.

Features:
- Connect to a chat server with customizable host and port
- Non-blocking input/output with threading
- Send and receive messages simultaneously
- Support for /quit command to disconnect gracefully
- Support for /list command to show online users
- Join/leave notifications from server
- Graceful handling of connection loss
- Comprehensive error handling and user-friendly prompts
"""

import socket
import threading
import sys
import queue
import logging
from typing import Optional

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
BUFFER_SIZE = 1024
ENCODING = 'utf-8'


class ChatClient:
    """IRC-like chat client for multi-user messaging."""

    def __init__(self, host: str, port: int):
        """
        Initialize chat client.

        Args:
            host: Server host address
            port: Server port number
        """
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.connected = False
        self.username: Optional[str] = None
        # Queue for thread-safe message handling to avoid garbled output
        self.message_queue: queue.Queue = queue.Queue()
        self.input_lock = threading.Lock()

    def connect(self) -> bool:
        """
        Connect to the server.

        Returns:
            True if connection successful, False otherwise
        """
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
        except socket.timeout:
            print(f"\n❌ Error: Connection to {self.host}:{self.port} timed out")
            logger.error(f"Connection timeout to {self.host}:{self.port}")
            return False
        except Exception as e:
            print(f"\n❌ Connection error: {e}")
            logger.error(f"Failed to connect: {e}")
            return False

    def get_username(self) -> bool:
        """
        Request username from server and get user input.

        Returns:
            True if username was successfully set, False otherwise
        """
        try:
            # Receive username prompt from server
            prompt = self.socket.recv(BUFFER_SIZE).decode(ENCODING)
            if prompt:
                print(prompt, end='', flush=True)

            # Get username from user
            self.username = input().strip()

            if not self.username:
                print("❌ Username cannot be empty. Connection closed.")
                logger.warning("User provided empty username")
                return False

            # Send username to server
            self.socket.send(self.username.encode(ENCODING))

            # Receive server response (welcome or error)
            response = self.socket.recv(BUFFER_SIZE).decode(ENCODING)
            if response:
                print(response, end='', flush=True)

            # Check if username was rejected
            if "already taken" in response.lower() or "closed" in response.lower():
                logger.warning(f"Username '{self.username}' rejected by server")
                return False

            logger.info(f"Username set to '{self.username}'")
            return True

        except ConnectionResetError:
            print("\n❌ Server closed the connection during username negotiation")
            logger.error("Connection reset during username setup")
            return False
        except UnicodeDecodeError:
            print("\n❌ Invalid message encoding from server")
            logger.error("Unicode decode error during username setup")
            return False
        except Exception as e:
            print(f"\n❌ Error during username setup: {e}")
            logger.error(f"Error during username negotiation: {e}")
            return False

    def receive_messages(self) -> None:
        """
        Receive messages from server in a separate thread.

        Continuously listens for incoming messages and queues them for display.
        Handles connection loss gracefully.
        """
        try:
            while self.connected:
                try:
                    message = self.socket.recv(BUFFER_SIZE).decode(ENCODING)
                    if not message:
                        # Empty message indicates server closed connection
                        self.message_queue.put(None)
                        break
                    self.message_queue.put(message)
                except socket.timeout:
                    # Timeout is normal, continue
                    continue
        except ConnectionResetError:
            logger.warning("Connection reset by server")
            self.message_queue.put(None)
        except UnicodeDecodeError:
            logger.error("Invalid UTF-8 encoding from server")
            self.message_queue.put(None)
        except Exception as e:
            logger.error(f"Error receiving messages: {e}")
            self.message_queue.put(None)
        finally:
            self.connected = False

    def display_messages(self) -> None:
        """
        Display queued messages to the user.

        Runs in main thread to safely display messages from receive thread.
        """
        while self.connected:
            try:
                # Check for queued messages with short timeout
                message = self.message_queue.get(timeout=0.1)
                if message is None:
                    # None indicates connection closed
                    break
                with self.input_lock:
                    print(message, end='', flush=True)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error displaying message: {e}")
                break

    def handle_user_input(self) -> None:
        """
        Handle user input in main thread.

        Reads from stdin and sends messages to server. Processes special commands.
        """
        try:
            while self.connected:
                try:
                    with self.input_lock:
                        user_input = input()

                    if not user_input:
                        continue

                    # Handle special commands
                    if user_input.lower() == '/quit':
                        logger.info("User requested quit")
                        self.send_message(user_input)
                        break

                    if user_input.lower() == '/list':
                        logger.info("User requested list command")
                        self.send_message(user_input)
                        continue

                    # Send regular message
                    self.send_message(user_input)

                except EOFError:
                    # Ctrl+D pressed
                    logger.info("EOF received from stdin")
                    break
        except KeyboardInterrupt:
            # Ctrl+C pressed
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error(f"Error in user input handler: {e}")
        finally:
            self.connected = False

    def send_message(self, message: str) -> None:
        """
        Send a message to the server.

        Args:
            message: Message content to send
        """
        try:
            self.socket.send(message.encode(ENCODING))
            logger.debug(f"Sent message: {message}")
        except (BrokenPipeError, ConnectionResetError):
            logger.warning("Connection closed when sending message")
            self.connected = False
        except Exception as e:
            logger.error(f"Error sending message: {e}")
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
        """
        Run the client main loop.

        Handles connection, username setup, and message exchange.
        """
        # Connect to server
        if not self.connect():
            return

        # Get username from user
        if not self.get_username():
            self.disconnect()
            return

        self.connected = True

        # Start receive thread
        receive_thread = threading.Thread(
            target=self.receive_messages,
            daemon=True
        )
        receive_thread.start()

        # Start message display thread
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
    """
    Parse command-line arguments for host and port.

    Returns:
        Tuple of (host, port)
    """
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
    """Main entry point for the chat client."""
    host, port = parse_arguments()

    if len(sys.argv) == 1:
        print("=" * 60)
        print("📱 Crypto Vibeness - Chat Client")
        print("=" * 60)
        print(f"Connecting to {host}:{port}...")
        print("Commands: /quit (exit), /list (show users)")
        print("=" * 60)

    client = ChatClient(host, port)
    client.run()


if __name__ == "__main__":
    main()
