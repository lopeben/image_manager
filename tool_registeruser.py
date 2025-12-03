#!/usr/bin/env python3
"""
User Registration Script for File Manager
Adds new users with hashed passwords to user_credentials.txt
"""

import os
import sys
import getpass
from werkzeug.security import generate_password_hash

USER_CREDENTIALS_FILE = 'user_credentials.txt'

def load_existing_users():
    """Load existing usernames from credentials file"""
    users = set()
    if os.path.exists(USER_CREDENTIALS_FILE):
        with open(USER_CREDENTIALS_FILE, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    parts = line.strip().split(':', 1)
                    if len(parts) == 2:
                        users.add(parts[0])
    return users

def register_user(username, password):
    """Register a new user with hashed password"""
    # Load existing users
    existing_users = load_existing_users()
    
    # Check if username already exists
    if username in existing_users:
        print(f"❌ Error: Username '{username}' already exists!")
        return False
    
    # Validate username
    if not username or len(username) < 3:
        print("❌ Error: Username must be at least 3 characters long!")
        return False
    
    if not username.replace('_', '').replace('-', '').isalnum():
        print("❌ Error: Username can only contain letters, numbers, hyphens, and underscores!")
        return False
    
    # Validate password
    if not password or len(password) < 6:
        print("❌ Error: Password must be at least 6 characters long!")
        return False
    
    # Generate password hash (using pbkdf2:sha256 for Python 3.9 compatibility)
    password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    # Append to credentials file
    with open(USER_CREDENTIALS_FILE, 'a') as f:
        f.write(f"{username}:{password_hash}\n")
    
    print(f"✅ User '{username}' registered successfully!")
    return True

def main():
    print("=" * 50)
    print("File Manager - User Registration")
    print("=" * 50)
    print()
    
    # Get username
    while True:
        username = input("Enter username (or 'q' to quit): ").strip()
        
        if username.lower() == 'q':
            print("Registration cancelled.")
            sys.exit(0)
        
        if username:
            break
        print("❌ Username cannot be empty!")
    
    # Get password (hidden input)
    while True:
        password = getpass.getpass("Enter password: ")
        
        if not password:
            print("❌ Password cannot be empty!")
            continue
        
        password_confirm = getpass.getpass("Confirm password: ")
        
        if password != password_confirm:
            print("❌ Passwords do not match! Try again.")
            continue
        
        break
    
    # Register the user
    if register_user(username, password):
        print()
        print("You can now login with these credentials.")
    else:
        sys.exit(1)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nRegistration cancelled.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)
