"""
Jour 4: ECDH/ECDSA Chat Server

Key differences from Jour 3:
- ECDH (X25519) for ephemeral, forward-secret session-key establishment
- ECDSA (P-256) for digital signatures (smaller and faster than RSA)
- AES-256-GCM for authenticated encryption (single AEAD primitive)
- Server is a *blind relay*: it only routes opaque ciphertext blobs

Protocol overview
-----------------
1. Client connects → sends AUTH (username)
2. Client uploads its ECDSA public key (for signature verification by peers)
3. Clients request each other's ECDSA public keys through the server
4. When sending a message to a peer:
     a. Sender generates a fresh X25519 ephemeral keypair
     b. Sender requests peer's "ECDH ephemeral public key" (or uses one
        pre-published by the peer during connection)
     c. Both sides derive the same AES session key via ECDH + HKDF
     d. Sender encrypts with AES-256-GCM and signs with ECDSA
     e. Server forwards the bundle; peer decrypts and verifies
"""

import socket
import threading
import json
import sys
import logging
from datetime import datetime
from crypto_ecdh import (
    x25519_public_key_to_bytes,
    x25519_public_key_from_bytes,
    ecdsa_public_key_from_pem,
    ecdsa_public_key_to_pem,
)
from config import SERVER_HOST, SERVER_PORT, SERVER_LISTEN_BACKLOG, SERVER_SOCKET_TIMEOUT

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)


class ECDHServer:
    """
    Blind-relay chat server for the ECDH/ECDSA/AES-GCM chat protocol.

    The server stores:
      - Each client's ECDSA public key (for distribution to peers)
      - Each client's *current* X25519 ECDH public key (for key agreement)
    It cannot read any message content.
    """

    def __init__(self, host: str = SERVER_HOST, port: int = SERVER_PORT):
        self.host = host
        self.port = port
        self.server_socket = None
        self.shutdown_event = threading.Event()

        # {username: {socket, ecdsa_pub_key, ecdh_pub_key_bytes, addr}}
        self.clients: dict = {}
        self.clients_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        """Bind, listen, and accept connections."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(SERVER_LISTEN_BACKLOG)

        logger.info(f"ECDH E2EE Server listening on {self.host}:{self.port}")
        logger.info("Crypto: X25519 ECDH + ECDSA/P-256 + AES-256-GCM")

        try:
            while not self.shutdown_event.is_set():
                try:
                    self.server_socket.settimeout(SERVER_SOCKET_TIMEOUT)
                    client_socket, addr = self.server_socket.accept()
                    logger.info(f"Connection from {addr}")
                    threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, addr),
                        daemon=True,
                    ).start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if not self.shutdown_event.is_set():
                        logger.error(f"Accept error: {e}")

        except KeyboardInterrupt:
            logger.info("Shutdown requested")
        finally:
            self.shutdown()

    def shutdown(self):
        """Gracefully shut down the server."""
        logger.info("Shutting down...")
        self.shutdown_event.set()

        with self.clients_lock:
            for info in self.clients.values():
                try:
                    info['socket'].close()
                except Exception:
                    pass
            self.clients.clear()

        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass

        logger.info("Shutdown complete")

    # ------------------------------------------------------------------
    # Client handler
    # ------------------------------------------------------------------

    def _handle_client(self, client_socket: socket.socket, addr: tuple):
        """Handle a single client connection."""
        username = None

        try:
            # Phase 1: Receive AUTH
            raw = client_socket.recv(1024).decode('utf-8')
            auth = json.loads(raw)

            if auth.get('type') != 'AUTH':
                client_socket.close()
                return

            username = auth['username']
            logger.info(f"AUTH from '{username}' at {addr}")

            # Send AUTH_OK
            client_socket.send(json.dumps({'type': 'AUTH_OK'}).encode('utf-8'))

            # Phase 2: Receive ECDSA public key + ECDH public key
            raw = client_socket.recv(4096).decode('utf-8')
            keys_msg = json.loads(raw)

            if keys_msg.get('type') != 'KEYS':
                client_socket.close()
                return

            ecdsa_pub = ecdsa_public_key_from_pem(keys_msg['ecdsa_pub'].encode('utf-8'))
            ecdh_pub_bytes = bytes.fromhex(keys_msg['ecdh_pub_hex'])

            # Register client
            with self.clients_lock:
                if username in self.clients:
                    try:
                        self.clients[username]['socket'].close()
                    except Exception:
                        pass

                self.clients[username] = {
                    'socket': client_socket,
                    'ecdsa_pub': ecdsa_pub,
                    'ecdh_pub_bytes': ecdh_pub_bytes,
                    'addr': addr,
                }

            logger.info(f"'{username}' registered with ECDSA + ECDH keys")
            self._broadcast_user_list()

            # Phase 3: Message relay loop
            while not self.shutdown_event.is_set():
                data = client_socket.recv(8192)
                if not data:
                    break

                try:
                    msg = json.loads(data.decode('utf-8'))
                    t = msg.get('type')

                    if t == 'MSG':
                        self._route_message(username, msg)
                    elif t == 'GET_KEYS':
                        self._send_peer_keys(client_socket, msg.get('username'))
                    elif t == 'UPDATE_ECDH':
                        # Refresh ephemeral ECDH public key
                        new_ecdh_bytes = bytes.fromhex(msg['ecdh_pub_hex'])
                        with self.clients_lock:
                            if username in self.clients:
                                self.clients[username]['ecdh_pub_bytes'] = new_ecdh_bytes
                        logger.debug(f"'{username}' refreshed ECDH public key")

                except Exception as e:
                    logger.error(f"Message error for '{username}': {e}")

        except Exception as e:
            logger.error(f"Handler error for '{username}': {e}")
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

    # ------------------------------------------------------------------
    # Routing helpers
    # ------------------------------------------------------------------

    def _route_message(self, sender: str, msg: dict):
        """Forward an encrypted message to its recipient."""
        recipient = msg.get('to')
        if not recipient:
            return

        with self.clients_lock:
            recipient_info = self.clients.get(recipient)

        if not recipient_info:
            logger.warning(f"Message from '{sender}' to unknown '{recipient}'")
            return

        forward = {
            'type': 'MSG',
            'from': sender,
            'sender_ecdh_pub_hex': msg.get('sender_ecdh_pub_hex'),
            'encrypted_msg': msg.get('encrypted_msg'),
            'signature': msg.get('signature'),
            'timestamp': datetime.now().isoformat(),
        }

        try:
            recipient_info['socket'].send(json.dumps(forward).encode('utf-8'))
            logger.info(f"E2EE message routed: '{sender}' → '{recipient}' [encrypted]")
        except Exception as e:
            logger.error(f"Failed to forward to '{recipient}': {e}")

    def _send_peer_keys(self, client_socket: socket.socket, target: str):
        """Send a peer's ECDSA + ECDH public keys to the requesting client."""
        with self.clients_lock:
            info = self.clients.get(target)

        if info:
            ecdsa_pem = ecdsa_public_key_to_pem(info['ecdsa_pub']).decode('utf-8')
            response = {
                'type': 'PEER_KEYS',
                'username': target,
                'ecdsa_pub': ecdsa_pem,
                'ecdh_pub_hex': info['ecdh_pub_bytes'].hex(),
            }
        else:
            response = {'type': 'ERROR', 'message': f"User '{target}' not found"}

        try:
            client_socket.send(json.dumps(response).encode('utf-8'))
        except Exception as e:
            logger.error(f"Failed to send peer keys: {e}")

    def _broadcast_user_list(self):
        """Send the current online user list to every connected client."""
        with self.clients_lock:
            user_list = list(self.clients.keys())
            sockets = {u: info['socket'] for u, info in self.clients.items()}

        payload = json.dumps({'type': 'USER_LIST', 'users': user_list}).encode('utf-8')

        for uname, sock in sockets.items():
            try:
                sock.send(payload)
            except Exception as e:
                logger.warning(f"Failed to send user list to '{uname}': {e}")


def main():
    port = SERVER_PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Usage: {sys.argv[0]} [port]")
            sys.exit(1)

    server = ECDHServer(port=port)
    server.start()


if __name__ == '__main__':
    main()
