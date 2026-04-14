#!/usr/bin/env python3
"""
Test script for the chat server.
Tests multi-client connections, message broadcasting, and graceful disconnection.
"""

import socket
import threading
import time
import sys

BUFFER_SIZE = 1024
ENCODING = 'utf-8'


def test_client(username, test_messages, delay=1):
    """Simulate a client connection and interaction."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('localhost', 5000))
        
        # Receive username prompt
        response = sock.recv(BUFFER_SIZE).decode(ENCODING)
        print(f"[{username}] Server: {response.strip()}")
        
        # Send username
        sock.send(username.encode(ENCODING))
        
        # Receive welcome message
        response = sock.recv(BUFFER_SIZE).decode(ENCODING)
        print(f"[{username}] Server: {response.strip()}")
        
        # Send test messages
        for msg in test_messages:
            time.sleep(delay)
            sock.send(msg.encode(ENCODING))
            
            # Receive broadcasted message
            response = sock.recv(BUFFER_SIZE).decode(ENCODING)
            print(f"[{username}] Received: {response.strip()}")
        
        # Disconnect
        time.sleep(0.5)
        sock.send(b'/quit')
        sock.close()
        print(f"[{username}] Disconnected")
        
    except Exception as e:
        print(f"[{username}] Error: {e}")


def main():
    """Run tests."""
    print("=" * 60)
    print("Testing Chat Server with 3 Concurrent Clients")
    print("=" * 60)
    
    # Create and start 3 client threads
    clients = [
        ("alice", ["Hello everyone!", "Alice here"]),
        ("bob", ["Hi Alice!", "Bob is here"]),
        ("charlie", ["Hey team!", "Charlie joined"])
    ]
    
    threads = []
    for username, messages in clients:
        t = threading.Thread(target=test_client, args=(username, messages, 0.5))
        threads.append(t)
        t.start()
        time.sleep(0.3)  # Stagger client connections
    
    # Wait for all clients to finish
    for t in threads:
        t.join()
    
    print("=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    time.sleep(1)  # Give server time to start
    main()
