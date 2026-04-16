#!/usr/bin/env python3
"""
Notifications Demo - Test all notification types
"""
import sys
import time
from notifications import (
    Notifications,
    notify_message, notify_user_joined, notify_user_left,
    notify_error, notify_success, notify_encrypted,
    set_notification_settings
)

def demo_all_notifications():
    """Demonstrate all notification types."""
    print("\n" + "="*60)
    print("🎵 CRYPTO VIBENESS - NOTIFICATIONS DEMO 🎵")
    print("="*60)
    
    # Create notification system
    set_notification_settings(enable_sound=True, enable_visual=True)
    
    print("\n[1] Testing Message Notifications...")
    time.sleep(1)
    notify_message("Alice", "Hey! This is a test message 👋")
    time.sleep(2)
    
    print("\n[2] Testing Mention Notification (with urgent ringtone)...")
    time.sleep(1)
    notifications = Notifications(enable_sound=True, enable_visual=True)
    notifications.notify_new_message("Bob", f"@user Check this out!", is_mention=True)
    time.sleep(3)
    
    print("\n[3] Testing User Join Notification...")
    time.sleep(1)
    notify_user_joined("Charlie")
    time.sleep(2)
    
    print("\n[4] Testing User Leave Notification...")
    time.sleep(1)
    notify_user_left("Diana")
    time.sleep(2)
    
    print("\n[5] Testing Success Notification...")
    time.sleep(1)
    notify_success("Connected to server successfully!")
    time.sleep(2)
    
    print("\n[6] Testing Encryption Notification...")
    time.sleep(1)
    notify_encrypted("messages")
    time.sleep(2)
    
    print("\n[7] Testing Error Notification...")
    time.sleep(1)
    notify_error("Connection timeout! Please reconnect.")
    time.sleep(2)
    
    print("\n" + "="*60)
    print("✅ Notification Demo Complete!")
    print("="*60)
    print("\nFeatures Demonstrated:")
    print("  ✓ System beeps (different frequencies for different events)")
    print("  ✓ ASCII art borders")
    print("  ✓ Colored text notifications")
    print("  ✓ Mention alerts with ringtones")
    print("  ✓ User join/leave notifications")
    print("  ✓ Encryption status notifications")
    print("  ✓ Error and success alerts")
    print("\n")

def demo_ringtones():
    """Demonstrate different ringtone patterns."""
    print("\n" + "="*60)
    print("🎵 RINGTONE DEMO")
    print("="*60)
    
    notifications = Notifications(enable_sound=True, enable_visual=True)
    
    ringtones = ['simple', 'standard', 'melodic', 'urgent']
    
    for ringtone in ringtones:
        print(f"\nPlaying '{ringtone}' ringtone...")
        notifications.play_ringtone(ringtone)
        time.sleep(1)
    
    print("\n✅ Ringtone demo complete!")
    print("\n")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Notification System Demo')
    parser.add_argument('--demo', choices=['all', 'ringtones'], default='all',
                       help='Which demo to run (default: all)')
    parser.add_argument('--sound', action='store_true', default=True,
                       help='Enable sound notifications (default: on)')
    parser.add_argument('--no-sound', dest='sound', action='store_false',
                       help='Disable sound notifications')
    
    args = parser.parse_args()
    
    if args.demo == 'ringtones':
        demo_ringtones()
    else:
        demo_all_notifications()
