"""
Jour 3: E2EE Chat Client

End-to-end encrypted client with:
- RSA keypair generation/persistence
- Public key exchange
- Encrypted message transmission
- Digital signature verification
"""

import socket
import threading
import json
import sys
import os
import getpass
from pathlib import Path
from crypto_utils import derive_key_from_password, encrypt_message, decrypt_message
from crypto_rsa import (
    generate_rsa_keypair, load_private_key, save_private_key,
    save_public_key, load_public_key, public_key_to_pem,
    pem_to_public_key, sign_message, verify_signature
)


class E2EEClient:
    def __init__(self, host='localhost', port=5001):
        self.host = host
        self.port = port
        self.socket = None
        self.username = None
        self.password = None
        self.shutdown_event = threading.Event()
        
        # RSA keys
        self.private_key = None
        self.public_key = None
        
        # Session keys with other users
        self.session_keys = {}  # {username: session_key}
        
        # Other users' public keys
        self.user_public_keys = {}  # {username: public_key}
        
        # Key directory
        self.key_dir = Path.home() / '.crypto_vibeness'
        self.key_dir.mkdir(exist_ok=True)
        
        print(f"[CLIENT] Keys stored in {self.key_dir}")
    
    def connect(self):
        """Connect to server and authenticate."""
        print(f"[CLIENT] Connecting to {self.host}:{self.port}...")
        
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        try:
            self.socket.connect((self.host, self.port))
            print("[CLIENT] Connected")
        except ConnectionRefusedError:
            print(f"[CLIENT] ERROR: Could not connect to {self.host}:{self.port}")
            sys.exit(1)
        
        # Setup username and password
        self.username = input("Username: ").strip()
        self.password = getpass.getpass("Password: ")
        
        # Setup RSA keys
        self._setup_rsa_keys()
        
        # Phase 1: Authenticate
        auth_msg = {
            'type': 'AUTH',
            'username': self.username,
            'password': self.password
        }
        self.socket.send(json.dumps(auth_msg).encode('utf-8'))
        
        response = json.loads(self.socket.recv(1024).decode('utf-8'))
        if response.get('type') != 'AUTH_OK':
            print(f"[CLIENT] Authentication failed")
            sys.exit(1)
        
        print(f"[CLIENT] Authenticated as {self.username}")
        
        # Phase 2: Send public key
        pub_key_pem = public_key_to_pem(self.public_key).decode('utf-8')
        pub_key_msg = {
            'type': 'PUBLIC_KEY',
            'public_key': pub_key_pem
        }
        self.socket.send(json.dumps(pub_key_msg).encode('utf-8'))
        print("[CLIENT] Public key sent")
        
        # Start receive thread
        recv_thread = threading.Thread(target=self._receive_messages, daemon=True)
        recv_thread.start()
        
        # Start input handler
        self._handle_input()
    
    def _setup_rsa_keys(self):
        """Generate or load RSA keypair."""
        priv_file = self.key_dir / f"{self.username}.priv"
        pub_file = self.key_dir / f"{self.username}.pub"
        
        if priv_file.exists() and pub_file.exists():
            print(f"[CLIENT] Loading existing keys...")
            self.private_key = load_private_key(str(priv_file))
            self.public_key = load_public_key(str(pub_file))
        else:
            print(f"[CLIENT] Generating new RSA keypair...")
            self.private_key, self.public_key = generate_rsa_keypair()
            
            save_private_key(self.private_key, str(priv_file))
            save_public_key(self.public_key, str(pub_file))
            print(f"[CLIENT] Keys saved to {self.key_dir}")
    
    def _receive_messages(self):
        """Receive messages from server."""
        try:
            while not self.shutdown_event.is_set():
                data = self.socket.recv(4096)
                if not data:
                    break
                
                try:
                    msg = json.loads(data.decode('utf-8'))
                    
                    if msg['type'] == 'MSG':
                        self._handle_received_message(msg)
                    
                    elif msg['type'] == 'USER_LIST':
                        self._handle_user_list(msg)
                    
                    elif msg['type'] == 'PUBLIC_KEY':
                        self._handle_public_key_response(msg)
                    
                except Exception as e:
                    print(f"[CLIENT] Message error: {e}")
                    
        except Exception as e:
            if not self.shutdown_event.is_set():
                print(f"[CLIENT] Receive error: {e}")
        finally:
            self.shutdown()
    
    def _handle_received_message(self, msg):
        """Decrypt and verify received message."""
        sender = msg['from']
        encrypted_msg = msg['encrypted_msg']
        signature = msg['signature']
        
        if sender not in self.session_keys:
            print(f"\n[CLIENT] Message from {sender} but no session key")
            return
        
        try:
            # Decrypt message
            session_key = self.session_keys[sender]
            plaintext = decrypt_message(encrypted_msg, session_key)
            
            # Verify signature
            if sender not in self.user_public_keys:
                print(f"\n[CLIENT] Cannot verify signature from {sender}: no public key")
                return
            
            sender_pub_key = self.user_public_keys[sender]
            signature_bytes = bytes.fromhex(signature)
            
            if verify_signature(plaintext, signature_bytes, sender_pub_key):
                print(f"\n[{sender}]: {plaintext.decode('utf-8')}")
                print(">>> ", end="", flush=True)
            else:
                print(f"\n[CLIENT] ⚠️ Signature verification failed from {sender}")
                print(">>> ", end="", flush=True)
                
        except Exception as e:
            print(f"\n[CLIENT] Decryption/verification error: {e}")
            print(">>> ", end="", flush=True)
    
    def _handle_user_list(self, msg):
        """Handle updated user list."""
        users = msg['users']
        other_users = [u for u in users if u != self.username]
        if other_users:
            print(f"\n[SERVER] Online users: {', '.join(other_users)}")
            print(">>> ", end="", flush=True)
    
    def _handle_public_key_response(self, msg):
        """Handle received public key."""
        username = msg['username']
        pub_key_pem = msg['public_key'].encode('utf-8')
        pub_key = pem_to_public_key(pub_key_pem)
        
        self.user_public_keys[username] = pub_key
        print(f"\n[CLIENT] Received public key for {username}")
        print(">>> ", end="", flush=True)
    
    def _handle_input(self):
        """Handle user input."""
        print("Commands: @user message (to send), /list (show users), /quit (exit)")
        print(">>> ", end="", flush=True)
        
        try:
            while not self.shutdown_event.is_set():
                try:
                    user_input = input()
                    
                    if user_input.startswith('/quit'):
                        break
                    
                    elif user_input.startswith('/list'):
                        self.socket.send(json.dumps({
                            'type': 'GET_USER_LIST'
                        }).encode('utf-8'))
                    
                    elif user_input.startswith('@'):
                        # Send message to specific user
                        parts = user_input.split(' ', 1)
                        if len(parts) == 2:
                            recipient = parts[0][1:]  # Remove @
                            message = parts[1]
                            self._send_e2ee_message(recipient, message)
                        else:
                            print("Usage: @username message")
                    
                    else:
                        print("Usage: @username message, /list, /quit")
                    
                    print(">>> ", end="", flush=True)
                    
                except EOFError:
                    break
                    
        except Exception as e:
            print(f"[CLIENT] Input error: {e}")
        finally:
            self.shutdown()
    
    def _send_e2ee_message(self, recipient, message):
        """Send end-to-end encrypted message."""
        # Request recipient's public key if needed
        if recipient not in self.user_public_keys:
            print(f"[CLIENT] Requesting public key for {recipient}...")
            self.socket.send(json.dumps({
                'type': 'GET_PUBLIC_KEY',
                'username': recipient
            }).encode('utf-8'))
            return
        
        # Get or establish session key
        if recipient not in self.session_keys:
            print(f"[CLIENT] Establishing session with {recipient}...")
            # For now, generate a random session key
            import os
            session_key = os.urandom(32)
            self.session_keys[recipient] = session_key
        
        try:
            # Sign message with private key
            msg_bytes = message.encode('utf-8')
            signature = sign_message(msg_bytes, self.private_key)
            signature_hex = signature.hex()
            
            # Encrypt message with session key
            session_key = self.session_keys[recipient]
            encrypted_msg = encrypt_message(msg_bytes, session_key)
            
            # Send to server
            send_msg = {
                'type': 'MSG',
                'to': recipient,
                'encrypted_msg': encrypted_msg,
                'signature': signature_hex
            }
            
            self.socket.send(json.dumps(send_msg).encode('utf-8'))
            print(f"[CLIENT] Message sent to {recipient} (encrypted)")
            
        except Exception as e:
            print(f"[CLIENT] Error sending message: {e}")
    
    def shutdown(self):
        """Gracefully shutdown client."""
        print("\n[CLIENT] Disconnecting...")
        self.shutdown_event.set()
        
        try:
            self.socket.close()
        except:
            pass


def main():
    host = 'localhost'
    port = 5001
    
    if len(sys.argv) > 1:
        host = sys.argv[1]
    if len(sys.argv) > 2:
        try:
            port = int(sys.argv[2])
        except ValueError:
            pass
    
    client = E2EEClient(host=host, port=port)
    client.connect()


if __name__ == '__main__':
    main()
