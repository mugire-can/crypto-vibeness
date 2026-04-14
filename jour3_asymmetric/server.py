"""
Jour 3: E2EE Chat Server

End-to-end encrypted chat where:
- Server maintains public key registry
- Clients establish encrypted sessions
- Messages encrypted with AES, signed with RSA
- Server cannot read messages
"""

import socket
import threading
import json
import sys
import os
from datetime import datetime
from crypto_utils import derive_key_from_password, encrypt_message, decrypt_message
from crypto_rsa import (
    load_private_key, load_public_key, generate_rsa_keypair,
    save_private_key, save_public_key, public_key_to_pem,
    pem_to_public_key, sign_message, verify_signature
)


class E2EEServer:
    def __init__(self, port=5001):
        self.port = port
        self.server_socket = None
        self.clients = {}  # {username: {'socket': sock, 'thread': t, 'pub_key': bytes}}
        self.clients_lock = threading.Lock()
        self.shutdown_event = threading.Event()
        
        # Server-side AES key for transport encryption (client password auth)
        self.aes_key = None
        
        # Generate server RSA keypair (not used for E2EE, but for signatures)
        print("[SERVER] Generating server RSA keypair...")
        self.server_priv_key, self.server_pub_key = generate_rsa_keypair()
        
    def start(self):
        """Start the server."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('0.0.0.0', self.port))
        self.server_socket.listen(5)
        
        print(f"[SERVER] E2EE Chat Server listening on port {self.port}")
        
        try:
            while not self.shutdown_event.is_set():
                try:
                    self.server_socket.settimeout(1.0)
                    client_socket, addr = self.server_socket.accept()
                    print(f"[SERVER] New connection from {addr}")
                    
                    # Spawn thread to handle client
                    thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, addr),
                        daemon=True
                    )
                    thread.start()
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    if not self.shutdown_event.is_set():
                        print(f"[SERVER] Error accepting connection: {e}")
                        
        except KeyboardInterrupt:
            print("\n[SERVER] Shutdown requested")
        finally:
            self.shutdown()
    
    def _handle_client(self, client_socket, addr):
        """Handle individual client connection."""
        username = None
        
        try:
            # Phase 1: Authentication with password
            msg = client_socket.recv(1024).decode('utf-8')
            auth_data = json.loads(msg)
            
            if auth_data['type'] != 'AUTH':
                client_socket.close()
                return
            
            username = auth_data['username']
            password = auth_data['password']
            
            # Derive shared AES key
            self.aes_key, salt = derive_key_from_password(password)
            
            print(f"[SERVER] User '{username}' authenticated from {addr}")
            
            # Send auth success + public key request
            response = {
                'type': 'AUTH_OK',
                'message': 'Authentication successful'
            }
            client_socket.send(json.dumps(response).encode('utf-8'))
            
            # Phase 2: Receive public key
            pub_key_msg = client_socket.recv(4096).decode('utf-8')
            pub_key_data = json.loads(pub_key_msg)
            
            if pub_key_data['type'] != 'PUBLIC_KEY':
                client_socket.close()
                return
            
            pub_key_pem = pub_key_data['public_key'].encode('utf-8')
            pub_key = pem_to_public_key(pub_key_pem)
            
            # Register client
            with self.clients_lock:
                if username in self.clients:
                    # Disconnect old session
                    old_socket = self.clients[username]['socket']
                    try:
                        old_socket.close()
                    except:
                        pass
                
                self.clients[username] = {
                    'socket': client_socket,
                    'thread': threading.current_thread(),
                    'pub_key': pub_key,
                    'addr': addr
                }
            
            print(f"[SERVER] Registered {username}, public key received")
            
            # Broadcast online users
            self._broadcast_user_list()
            
            # Listen for messages
            while not self.shutdown_event.is_set():
                data = client_socket.recv(4096)
                if not data:
                    break
                
                try:
                    msg = json.loads(data.decode('utf-8'))
                    
                    if msg['type'] == 'MSG':
                        # Route encrypted message (server cannot read)
                        recipient = msg.get('to')
                        if recipient and recipient in self.clients:
                            encrypted_msg = msg.get('encrypted_msg')
                            signature = msg.get('signature')
                            
                            # Forward with sender info
                            forward_msg = {
                                'type': 'MSG',
                                'from': username,
                                'encrypted_msg': encrypted_msg,
                                'signature': signature,
                                'timestamp': datetime.now().isoformat()
                            }
                            
                            try:
                                self.clients[recipient]['socket'].send(
                                    json.dumps(forward_msg).encode('utf-8')
                                )
                                print(f"[SERVER] Encrypted message: {username} -> {recipient} [encrypted]")
                            except:
                                pass
                    
                    elif msg['type'] == 'GET_PUBLIC_KEY':
                        # Send requested public key
                        target_user = msg.get('username')
                        if target_user and target_user in self.clients:
                            target_pub_key = self.clients[target_user]['pub_key']
                            target_pub_key_pem = public_key_to_pem(target_pub_key).decode('utf-8')
                            
                            response = {
                                'type': 'PUBLIC_KEY',
                                'username': target_user,
                                'public_key': target_pub_key_pem
                            }
                            client_socket.send(json.dumps(response).encode('utf-8'))
                        else:
                            response = {'type': 'ERROR', 'message': 'User not found'}
                            client_socket.send(json.dumps(response).encode('utf-8'))
                    
                except Exception as e:
                    print(f"[SERVER] Message handling error: {e}")
                    
        except Exception as e:
            print(f"[SERVER] Client handler error for {username}: {e}")
        finally:
            # Cleanup
            if username:
                with self.clients_lock:
                    if username in self.clients:
                        del self.clients[username]
                print(f"[SERVER] {username} disconnected")
                self._broadcast_user_list()
            
            try:
                client_socket.close()
            except:
                pass
    
    def _broadcast_user_list(self):
        """Send list of online users to all clients."""
        with self.clients_lock:
            user_list = list(self.clients.keys())
        
        msg = {
            'type': 'USER_LIST',
            'users': user_list
        }
        
        with self.clients_lock:
            for username, client_info in self.clients.items():
                try:
                    client_info['socket'].send(json.dumps(msg).encode('utf-8'))
                except:
                    pass
    
    def shutdown(self):
        """Gracefully shutdown server."""
        print("[SERVER] Shutting down...")
        self.shutdown_event.set()
        
        with self.clients_lock:
            for username, client_info in self.clients.items():
                try:
                    client_info['socket'].close()
                except:
                    pass
            self.clients.clear()
        
        if self.server_socket:
            self.server_socket.close()
        
        print("[SERVER] Shutdown complete")


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
