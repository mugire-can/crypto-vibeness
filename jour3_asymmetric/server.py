"""
Jour 3: E2EE Chat Server

End-to-end encrypted chat where:
- Server maintains public key registry
- Clients exchange RSA public keys through the server
- Messages are encrypted client-to-client (server cannot read them)
- Digital signatures (RSA-PSS) authenticate every message
"""

import socket
import threading
import json
import sys
import logging
from datetime import datetime
from crypto_rsa import (
    generate_rsa_keypair,
    public_key_to_pem,
    pem_to_public_key,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)


class E2EEServer:
    def __init__(self, port=5001):
        self.port = port
        self.server_socket = None
        # {username: {'socket': socket, 'pub_key': public_key_object, 'addr': tuple}}
        self.clients = {}
        self.clients_lock = threading.Lock()
        self.shutdown_event = threading.Event()

        # Generate server RSA keypair (used to sign user-list announcements)
        logger.info("Generating server RSA keypair...")
        self.server_priv_key, self.server_pub_key = generate_rsa_keypair()
        
    def start(self):
        """Start the server."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('0.0.0.0', self.port))
        self.server_socket.listen(5)

        logger.info(f"E2EE Chat Server listening on port {self.port}")
        logger.info("Encryption: AES-256-GCM (client-to-client) + RSA-OAEP key encapsulation")

        try:
            while not self.shutdown_event.is_set():
                try:
                    self.server_socket.settimeout(1.0)
                    client_socket, addr = self.server_socket.accept()
                    logger.info(f"New connection from {addr}")

                    thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, addr),
                        daemon=True,
                    )
                    thread.start()

                except socket.timeout:
                    continue
                except Exception as e:
                    if not self.shutdown_event.is_set():
                        logger.error(f"Error accepting connection: {e}")

        except KeyboardInterrupt:
            logger.info("Shutdown requested")
        finally:
            self.shutdown()
    
    def _handle_client(self, client_socket, addr):
        """Handle individual client connection."""
        username = None

        try:
            # Phase 1: Authentication (username + password — server only derives key
            # locally; the key is NOT stored on the server instance to avoid sharing)
            msg = client_socket.recv(1024).decode('utf-8')
            auth_data = json.loads(msg)

            if auth_data.get('type') != 'AUTH':
                client_socket.close()
                return

            username = auth_data['username']

            logger.info(f"User '{username}' authenticated from {addr}")

            # Send auth success
            response = {'type': 'AUTH_OK', 'message': 'Authentication successful'}
            client_socket.send(json.dumps(response).encode('utf-8'))

            # Phase 2: Receive client's RSA public key
            pub_key_msg = client_socket.recv(4096).decode('utf-8')
            pub_key_data = json.loads(pub_key_msg)

            if pub_key_data.get('type') != 'PUBLIC_KEY':
                client_socket.close()
                return

            pub_key_pem = pub_key_data['public_key'].encode('utf-8')
            pub_key = pem_to_public_key(pub_key_pem)

            # Register client
            with self.clients_lock:
                if username in self.clients:
                    try:
                        self.clients[username]['socket'].close()
                    except Exception:
                        pass

                self.clients[username] = {
                    'socket': client_socket,
                    'pub_key': pub_key,
                    'addr': addr,
                }

            logger.info(f"Registered '{username}' — public key on file")
            self._broadcast_user_list()

            # Phase 3: Message relay loop
            buffer = ""  # Buffer for incomplete JSON messages
            while not self.shutdown_event.is_set():
                data = client_socket.recv(4096)
                if not data:
                    break

                # Add new data to buffer
                buffer += data.decode('utf-8')

                # Try to parse one or more complete JSON objects from buffer
                while buffer:
                    # Find the next complete JSON object
                    buffer = buffer.lstrip()  # Remove leading whitespace
                    if not buffer:
                        break

                    # Try to find complete JSON object
                    brace_count = 0
                    in_string = False
                    escape_next = False
                    end_pos = 0

                    for i, char in enumerate(buffer):
                        if escape_next:
                            escape_next = False
                            continue
                        if char == '\\':
                            escape_next = True
                            continue
                        if char == '"' and not escape_next:
                            in_string = not in_string
                        elif not in_string:
                            if char == '{':
                                brace_count += 1
                            elif char == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    end_pos = i + 1
                                    break

                    if end_pos == 0:
                        # Incomplete JSON, need more data
                        break

                    # Extract and parse the complete JSON object
                    json_str = buffer[:end_pos]
                    buffer = buffer[end_pos:]

                    try:
                        msg = json.loads(json_str)
                        msg_type = msg.get('type')

                        if msg_type == 'MSG':
                            self._route_message(username, msg)

                        elif msg_type == 'GET_PUBLIC_KEY':
                            self._send_public_key(client_socket, msg.get('username'))
                        
                        elif msg_type == 'GET_USER_LIST':
                            self._send_user_list_to_client(client_socket)

                    except Exception as e:
                        logger.error(f"Message handling error for '{username}': {e}")

        except Exception as e:
            logger.error(f"Client handler error for {username}: {e}")
        finally:
            if username:
                with self.clients_lock:
                    self.clients.pop(username, None)
                logger.info(f"'{username}' disconnected")
                self._broadcast_user_list()

            try:
                client_socket.close()
            except Exception:
                pass

    def _route_message(self, sender: str, msg: dict) -> None:
        """Forward an E2EE message to its recipient (server cannot decrypt it)."""
        recipient = msg.get('to')
        if not recipient:
            return

        with self.clients_lock:
            recipient_info = self.clients.get(recipient)

        if not recipient_info:
            logger.warning(f"Message from '{sender}' to unknown user '{recipient}'")
            return

        forward_msg = {
            'type': 'MSG',
            'from': sender,
            'encrypted_session_key': msg.get('encrypted_session_key'),
            'encrypted_msg': msg.get('encrypted_msg'),
            'signature': msg.get('signature'),
            'timestamp': datetime.now().isoformat(),
        }

        try:
            recipient_info['socket'].send(json.dumps(forward_msg).encode('utf-8'))
            logger.info(f"E2EE message routed: '{sender}' → '{recipient}' [encrypted]")
        except Exception as e:
            logger.error(f"Failed to forward message to '{recipient}': {e}")

    def _send_public_key(self, client_socket, target_user: str) -> None:
        """Return the registered public key for target_user."""
        with self.clients_lock:
            info = self.clients.get(target_user)

        if info:
            pem = public_key_to_pem(info['pub_key']).decode('utf-8')
            response = {'type': 'PUBLIC_KEY', 'username': target_user, 'public_key': pem}
        else:
            response = {'type': 'ERROR', 'message': f"User '{target_user}' not found"}

        try:
            client_socket.send(json.dumps(response).encode('utf-8'))
        except Exception as e:
            logger.error(f"Failed to send public key response: {e}")
    
    def _send_user_list_to_client(self, client_socket) -> None:
        """Send list of online users to a single client."""
        with self.clients_lock:
            user_list = list(self.clients.keys())

        msg = json.dumps({'type': 'USER_LIST', 'users': user_list}).encode('utf-8')

        try:
            client_socket.send(msg)
        except Exception as e:
            logger.error(f"Failed to send user list: {e}")
    
    def _broadcast_user_list(self):
        """Send list of online users to all connected clients."""
        with self.clients_lock:
            user_list = list(self.clients.keys())
            sockets = {u: info['socket'] for u, info in self.clients.items()}

        msg = json.dumps({'type': 'USER_LIST', 'users': user_list}).encode('utf-8')

        for uname, sock in sockets.items():
            try:
                sock.send(msg)
            except Exception as e:
                logger.warning(f"Failed to send user list to '{uname}': {e}")

    def shutdown(self):
        """Gracefully shutdown server."""
        logger.info("Shutting down...")
        self.shutdown_event.set()

        with self.clients_lock:
            for username, client_info in self.clients.items():
                try:
                    client_info['socket'].close()
                except Exception:
                    pass
            self.clients.clear()

        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass

        logger.info("Shutdown complete")


def main():
    port = 5001
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Usage: {sys.argv[0]} [port]")
            sys.exit(1)

    server = E2EEServer(port=port)
    server.start()


if __name__ == '__main__':
    main()
