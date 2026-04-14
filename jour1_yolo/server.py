#!/usr/bin/env python3
"""
Crypto Vibeness - Day 1: IRC-like Chat Server
A basic multi-user chat server without security features.

Features:
- Multi-threaded socket server accepting multiple concurrent clients
- User registry with thread-safe access
- Message broadcasting to all connected clients
- Join/leave notifications
- Graceful shutdown on Ctrl+C
- Comprehensive logging with timestamps
"""

import socket
import threading
import sys
import json
import logging
from datetime import datetime
from typing import Dict, Optional

# Configure logging with timestamps
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Configuration constants
DEFAULT_PORT = 5000
BUFFER_SIZE = 1024
ENCODING = 'utf-8'
HOST = '0.0.0.0'  # Listen on all interfaces


class ChatServer:
    """Multi-threaded IRC-like chat server."""

    def __init__(self, host: str, port: int):
        """
        Initialize chat server.

        Args:
            host: Host address to bind to
            port: Port number to listen on
        """
        self.host = host
        self.port = port
        self.server_socket: Optional[socket.socket] = None
        self.users: Dict[str, socket.socket] = {}
        self.users_lock = threading.Lock()
        self.running = True

    def start(self) -> None:
        """
        Start the chat server and accept client connections.

        Handles incoming connections in a loop, spawning a new thread for
        each client. Catches KeyboardInterrupt for graceful shutdown.
        """
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            logger.info(f"Server started on {self.host}:{self.port}")

            while self.running:
                try:
                    client_socket, client_address = self.server_socket.accept()
                    logger.info(f"Connection received from {client_address}")
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
            logger.info("\nServer interrupt received (Ctrl+C)")
            self.shutdown()
        except Exception as e:
            logger.error(f"Server error: {e}")
            self.shutdown()

    def _handle_client(self, client_socket: socket.socket, client_address: tuple) -> None:
        """
        Handle a single client connection.

        Manages username negotiation, message reception, broadcasting,
        and graceful disconnection.

        Args:
            client_socket: Connected socket to the client
            client_address: Tuple of (host, port) for the client
        """
        username: Optional[str] = None
        try:
            # Request username from client
            client_socket.send(b"Enter your username: ")
            username = client_socket.recv(BUFFER_SIZE).decode(ENCODING).strip()

            if not username:
                logger.warning(f"Client {client_address} provided empty username")
                client_socket.close()
                return

            # Check if username already taken
            with self.users_lock:
                if username in self.users:
                    logger.warning(
                        f"Username '{username}' already taken (attempted by {client_address})"
                    )
                    client_socket.send(
                        b"Username already taken. Connection closed.\n"
                    )
                    client_socket.close()
                    return

                self.users[username] = client_socket
                logger.info(f"User '{username}' connected from {client_address}")

            # Notify all users of new user joining
            self._broadcast_system_message(f"[{username}] has joined")

            # Send welcome message to user
            welcome_msg = f"Welcome to Chat, {username}! Type /quit to exit.\n"
            client_socket.send(welcome_msg.encode(ENCODING))

            # Receive and broadcast messages
            while self.running:
                message = client_socket.recv(BUFFER_SIZE).decode(ENCODING).strip()

                if not message:
                    break

                if message.startswith('/quit'):
                    logger.info(f"User '{username}' requested to quit")
                    break

                # Broadcast message to all users
                self._broadcast_message(username, message)

        except ConnectionResetError:
            logger.warning(f"Connection reset by {client_address}")
        except UnicodeDecodeError:
            logger.error(f"Invalid UTF-8 encoding from {client_address}")
        except Exception as e:
            logger.error(f"Error handling client {client_address}: {e}")
        finally:
            # Clean up disconnected user
            if username:
                with self.users_lock:
                    if username in self.users:
                        del self.users[username]
                        logger.info(f"User '{username}' disconnected")

                # Notify all users of user leaving
                self._broadcast_system_message(f"[{username}] has left")

            try:
                client_socket.close()
            except Exception:
                pass

    def _broadcast_message(self, username: str, message: str) -> None:
        """
        Broadcast a user message to all connected clients.

        Args:
            username: Name of the user sending the message
            message: Message content
        """
        formatted_message = f"{username}: {message}\n"
        logger.info(f"Message from '{username}': {message}")
        self._send_to_all(formatted_message)

    def _broadcast_system_message(self, message: str) -> None:
        """
        Broadcast a system message to all connected clients.

        Args:
            message: System message content
        """
        formatted_message = f"{message}\n"
        logger.info(f"System: {message}")
        self._send_to_all(formatted_message)

    def _send_to_all(self, message: str) -> None:
        """
        Send a message to all connected users.

        Thread-safe access to user registry.

        Args:
            message: Message to send
        """
        message_bytes = message.encode(ENCODING)
        with self.users_lock:
            disconnected_users = []
            for username, user_socket in self.users.items():
                try:
                    user_socket.send(message_bytes)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    logger.warning(f"Failed to send message to '{username}'")
                    disconnected_users.append(username)

            # Clean up disconnected sockets
            for username in disconnected_users:
                if username in self.users:
                    del self.users[username]

    def shutdown(self) -> None:
        """
        Gracefully shut down the server.

        Closes all client connections, closes server socket, and logs shutdown.
        """
        logger.info("Initiating graceful shutdown...")
        self.running = False

        # Close all client connections
        with self.users_lock:
            for username, user_socket in list(self.users.items()):
                try:
                    user_socket.close()
                    logger.info(f"Closed connection for '{username}'")
                except Exception as e:
                    logger.error(f"Error closing socket for '{username}': {e}")
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


def parse_arguments() -> int:
    """
    Parse command-line arguments to get the port number.

    Returns:
        Port number (default: 5000)
    """
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
            if not (1 <= port <= 65535):
                raise ValueError("Port must be between 1 and 65535")
            return port
        except ValueError as e:
            logger.error(f"Invalid port argument: {e}")
            sys.exit(1)
    return DEFAULT_PORT


def main() -> None:
    """Main entry point for the chat server."""
    port = parse_arguments()
    server = ChatServer(HOST, port)
    server.start()


if __name__ == "__main__":
    main()
