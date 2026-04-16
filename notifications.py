#!/usr/bin/env python3
"""
Notification System for Crypto Vibeness
Handles:
- System beeps/sounds
- Visual notifications with colored text
- Console alerts with images/ASCII art
- Ringtone effects
"""

import sys
import os
import platform
from pathlib import Path

# Import winsound only on Windows
if platform.system() == "Windows":
    import winsound
else:
    winsound = None

# Colors and styles
class NotificationColors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'
    
# ASCII Art notifications
NOTIFICATION_ICONS = {
    'message': """
    ┌─────────────────┐
    │  💬 NEW MESSAGE │
    └─────────────────┘
    """,
    'user_joined': """
    ┌─────────────────┐
    │  ✅ USER JOINED │
    └─────────────────┘
    """,
    'user_left': """
    ┌─────────────────┐
    │  👋 USER LEFT   │
    └─────────────────┘
    """,
    'error': """
    ┌─────────────────┐
    │  ⚠️  ERROR      │
    └─────────────────┘
    """,
    'success': """
    ┌─────────────────┐
    │  ✨ SUCCESS    │
    └─────────────────┘
    """,
    'mention': """
    ┌─────────────────────┐
    │  🔔 YOU'RE MENTIONED │
    └─────────────────────┘
    """,
    'encrypted': """
    ┌──────────────────┐
    │  🔐 ENCRYPTED    │
    └──────────────────┘
    """,
}

class Notifications:
    """Handle all types of notifications."""
    
    # Notification sounds (system beep frequencies for Windows)
    BEEP_SOUNDS = {
        'message': {'frequency': 1000, 'duration': 200},
        'user_joined': {'frequency': 1200, 'duration': 150},
        'user_left': {'frequency': 800, 'duration': 150},
        'mention': {'frequency': 1500, 'duration': 300},
        'error': {'frequency': 500, 'duration': 500},
        'success': {'frequency': 1200, 'duration': 100},
        'encrypted': {'frequency': 1100, 'duration': 200},
    }
    
    def __init__(self, enable_sound=True, enable_visual=True):
        """Initialize notification system."""
        self.enable_sound = enable_sound
        self.enable_visual = enable_visual
        self.platform = platform.system()
        
    def play_beep(self, notification_type='message'):
        """Play system beep sound."""
        if not self.enable_sound:
            return
        
        if self.platform == "Windows":
            try:
                sound = self.BEEP_SOUNDS.get(notification_type, self.BEEP_SOUNDS['message'])
                winsound.Beep(sound['frequency'], sound['duration'])
            except Exception as e:
                pass  # Silently fail if no sound device
        elif self.platform == "Darwin":  # macOS
            try:
                os.system(f'afplay /System/Library/Sounds/Glass.aiff')
            except:
                pass
        else:  # Linux
            try:
                os.system(f'play -nq -t alsa synth 0.3 sine 1000 2>/dev/null')
            except:
                print('\a', end='', flush=True)  # Terminal bell
    
    def play_ringtone(self, ringtone_type='standard'):
        """Play a custom ringtone pattern."""
        if not self.enable_sound or self.platform != "Windows":
            return
        
        ringtones = {
            'standard': [(1000, 100), (1000, 100), (1200, 100)],  # 3 ascending beeps
            'urgent': [(1500, 200), (500, 100), (1500, 200)],     # Urgent alert
            'melodic': [(1200, 100), (1000, 100), (1200, 100), (1400, 150)],  # Melody
            'simple': [(1000, 200)],  # Single beep
        }
        
        pattern = ringtones.get(ringtone_type, ringtones['standard'])
        try:
            for freq, duration in pattern:
                winsound.Beep(freq, duration)
        except:
            pass
    
    def show_notification(self, notification_type, title, message, username=None):
        """Display visual notification."""
        if not self.enable_visual:
            print(f"[{title}] {message}")
            return
        
        # Play sound
        self.play_beep(notification_type)
        
        # Get icon
        icon = NOTIFICATION_ICONS.get(notification_type, NOTIFICATION_ICONS['message'])
        
        # Format message
        if notification_type == 'message' and username:
            formatted = f"{NotificationColors.BOLD}{NotificationColors.CYAN}{username}{NotificationColors.END}: {message}"
        else:
            formatted = message
        
        # Print notification with color
        color = {
            'message': NotificationColors.CYAN,
            'user_joined': NotificationColors.GREEN,
            'user_left': NotificationColors.YELLOW,
            'error': NotificationColors.RED,
            'success': NotificationColors.GREEN,
            'mention': NotificationColors.RED + NotificationColors.BOLD,
            'encrypted': NotificationColors.CYAN,
        }.get(notification_type, NotificationColors.BLUE)
        
        print(f"\n{color}{icon}{NotificationColors.END}")
        print(f"{color}{title}{NotificationColors.END}")
        print(f"{formatted}")
    
    def notify_new_message(self, username, message, is_mention=False):
        """Notify about new message."""
        if is_mention:
            self.show_notification('mention', '🔔 MENTION', f"{username}: {message}", username)
            self.play_ringtone('urgent')
        else:
            self.show_notification('message', '💬 Message', f"{username}: {message}", username)
    
    def notify_user_joined(self, username):
        """Notify when user joins."""
        self.show_notification('user_joined', '✅ User Joined', f"{username} has joined")
    
    def notify_user_left(self, username):
        """Notify when user leaves."""
        self.show_notification('user_left', '👋 User Left', f"{username} has left")
    
    def notify_error(self, error_message):
        """Notify about error."""
        self.show_notification('error', '⚠️  Error', error_message)
    
    def notify_success(self, success_message):
        """Notify about success."""
        self.show_notification('success', '✨ Success', success_message)
    
    def notify_encrypted(self, message_type="message"):
        """Notify about encryption status."""
        self.show_notification('encrypted', '🔐 Encrypted', f"{message_type} encrypted with AES-256-GCM")
    
    def notify_room_changed(self, room_name):
        """Notify about room change."""
        msg = f"Switched to room: {room_name}"
        self.show_notification('success', '🏠 Room Changed', msg)


# Create default notification instance
_notifications = None

def get_notifications():
    """Get or create notification instance."""
    global _notifications
    if _notifications is None:
        _notifications = Notifications(enable_sound=True, enable_visual=True)
    return _notifications

def set_notification_settings(enable_sound=True, enable_visual=True):
    """Configure notification settings."""
    global _notifications
    _notifications = Notifications(enable_sound=enable_sound, enable_visual=enable_visual)

# Convenience functions
def notify_message(username, message, is_mention=False):
    """Quick notification for message."""
    get_notifications().notify_new_message(username, message, is_mention)

def notify_user_joined(username):
    """Quick notification for user join."""
    get_notifications().notify_user_joined(username)

def notify_user_left(username):
    """Quick notification for user left."""
    get_notifications().notify_user_left(username)

def notify_error(error_msg):
    """Quick notification for error."""
    get_notifications().notify_error(error_msg)

def notify_success(success_msg):
    """Quick notification for success."""
    get_notifications().notify_success(success_msg)

def notify_encrypted(msg_type="message"):
    """Quick notification for encryption."""
    get_notifications().notify_encrypted(msg_type)
