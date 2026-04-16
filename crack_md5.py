#!/usr/bin/env python3
"""
MD5 Hash Cracking Script - For Educational Purposes Only
Breaks the mask: ?u?u?l?l?u?u?s (UULLNUS pattern)
Target hash: 35b95f7c0f63631c453220fb2a86f218

This script demonstrates MD5 hash cracking. In production, use hashcat:
  hashcat -m 0 -a 3 md5_yolo.txt "?u?u?l?l?u?u?s"
"""

import hashlib
import string
import itertools
import sys
from multiprocessing import Pool, Manager

TARGET_HASH = "35b95f7c0f63631c453220fb2a86f218"
MASK_PATTERN = "?u?u?l?l?u?u?s"

UPPERCASE = list(string.ascii_uppercase)
LOWERCASE = list(string.ascii_lowercase)
SPECIAL = list(string.punctuation)

def check_password(args):
    """Check single password candidate."""
    prefix, candidate_special = args
    for spec in candidate_special:
        password = prefix + spec
        if hashlib.md5(password.encode()).hexdigest() == TARGET_HASH:
            return password
    return None

def crack_md5_optimized():
    """Optimized MD5 cracking using prefix generation."""
    print(f"🔐 Cracking MD5 Hash: {TARGET_HASH}")
    print(f"📋 Pattern: {MASK_PATTERN}")
    print(f"📊 Generating candidates: UU LL UU S\n")
    
    count = 0
    total_special = len(SPECIAL)
    total = len(UPPERCASE) ** 4 * len(LOWERCASE) ** 2 * total_special
    
    print(f"⚠️  Estimated total tries: ~{total:,}")
    print(f"⏳ Cracking with prefix method...\n")
    
    # Generate prefixes: UULLUU
    for u1 in UPPERCASE:
        for u2 in UPPERCASE:
            for l1 in LOWERCASE:
                for l2 in LOWERCASE:
                    for u3 in UPPERCASE:
                        for u4 in UPPERCASE:
                            prefix = f"{u1}{u2}{l1}{l2}{u3}{u4}"
                            # Try all special chars with this prefix
                            for spec in SPECIAL:
                                password = prefix + spec
                                md5_hash = hashlib.md5(password.encode()).hexdigest()
                                count += 1
                                
                                if count % 10000000 == 0:
                                    pct = (count / total) * 100
                                    print(f"✓ Checked {count:,} ({pct:.1f}%)... Last: {password}")
                                
                                if md5_hash == TARGET_HASH:
                                    return password, count
    
    return None, count

if __name__ == "__main__":
    password, attempts = crack_md5_optimized()
    
    if password:
        print(f"\n✅ SUCCESS! Password found: {password}")
        print(f"🔑 MD5 Hash: {TARGET_HASH}")
        print(f"📈 Attempts: {attempts:,}\n")
    else:
        print(f"\n❌ Password not found after {attempts:,} attempts")
        sys.exit(1)
    
    # Output format for md5_decrypted.txt
    print("=" * 60)
    print("FOR md5_decrypted.txt:")
    print("=" * 60)
    print(f"Message: {password}")
    print(f"Hash: {TARGET_HASH}")
    print(f"Hashcat command: hashcat -m 0 -a 3 md5_yolo.txt \"{MASK_PATTERN}\"")
    print("=" * 60)
