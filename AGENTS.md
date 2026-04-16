# Crypto Vibeness — Agent Context

## Project Overview
Educational cryptography project at La Plateforme_ Marseille.
Goal: build a progressively more secure Python chat system using an AI agent.
Language rule: communicate in French, but ALL code must be in English.

## Current State — Jour 1
`jour1_yolo/server.py` (278 lines) and `jour1_yolo/client.py` (338 lines) implement a basic
multi-user IRC-style chat. What already works:
- Multi-threaded server accepting multiple clients simultaneously
- Username uniqueness check
- Message broadcasting to all connected clients
- Join/leave notifications
- /quit and /list commands
- Graceful shutdown on Ctrl+C

## Task — Jour 1 Part 1: Missing Features to Add

Extend the EXISTING files `jour1_yolo/server.py` and `jour1_yolo/client.py`.
Do NOT rewrite from scratch. Add the following features:

### 1. Room System
- Every client starts in the `general` room by default
- Server maintains a dict: `rooms = { room_name: {"password": str|None, "members": set} }`
- Commands to implement:
  - `/join <room>` — join an existing room (prompt for password if protected)
  - `/join <room> <password>` — join a password-protected room directly
  - `/create <room>` — create a new public room and join it
  - `/create <room> <password>` — create a password-protected room and join it
  - `/rooms` — list all rooms (protected rooms display differently, see below)
  - `/leave` — go back to `general`
- A client only receives messages from the room they are currently in
- When a user joins/leaves a room, only members of that room are notified

### 2. Visual Distinction for Password-Protected Rooms
- In `/rooms` output, protected rooms must display with a lock symbol: 🔒
- Example output:### 3. Deterministic Color Assignment
- The server assigns a color to each client based on their username (hash of username % number of colors)
- Available ANSI colors: red, green, yellow, blue, magenta, cyan (at least 6)
- The color is sent to the client as part of every message so ALL clients see the same color for a given user
- Format messages as: `\033[<color_code>m<username>\033[0m: <message>`
- The color must be consistent for the entire session and identical on all clients

### 4. Timestamps on Messages
- Every message displayed on clients must have a timestamp prefix
- Format: `[HH:MM:SS] \033[<color>m<username>\033[0m: <message>`

### 5. Server Log File
- In addition to stdout logging, the server must write all events to a file
- Filename format: `log_YYYY-MM-DD_HH-MM-SS.txt` (timestamp = server start time)
- Example: `log_2026-04-16_10-23-45.txt`
- Log every event: connection, disconnection, room join/leave/create, messages, errors
- Log format per line: `[YYYY-MM-DD HH:MM:SS] EVENT: details`

## Architecture Constraints
- Keep the existing ChatServer and ChatClient class structure
- Keep all existing error handling
- Thread-safety: use self.users_lock (already exists) and add a self.rooms_lock for rooms
- All new constants go in config.py
- Message protocol: plain text lines ending with newline
- Buffer size: use BUFFER_SIZE = 4096

## Files to Modify
- `jour1_yolo/server.py` — add room management, color assignment, log file
- `jour1_yolo/client.py` — add room commands, display colors and timestamps
- `jour1_yolo/config.py` — add new constants

## Validation Checklist
- [ ] New user lands in general room automatically
- [ ] /create myroom creates a public room, user is moved there
- [ ] /create secret pass123 creates a protected room
- [ ] /rooms shows all rooms, protected ones with 🔒
- [ ] /join myroom works; /join secret wrongpass is rejected
- [ ] Messages are only visible to users in the same room
- [ ] Colors are consistent: username X always gets the same color on all clients
- [ ] Every message shows a timestamp
- [ ] A log file log_YYYY-MM-DD_HH-MM-SS.txt is created on server start
- [ ] Log file contains all events

## What NOT to Do
- Do not add authentication or passwords for users (that is Jour 1 Part 2)
- Do not add encryption (that is Jour 2)
- Do not switch to asyncio
- Do not use external libraries beyond Python stdlib
