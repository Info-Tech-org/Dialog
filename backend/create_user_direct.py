"""
Create admin user using bcrypt directly
"""
import sqlite3
import uuid
import bcrypt

# Database path
db_path = 'E:/Innox-SZ/info-tech/backend/data/family_emotion.db'

# Hash password using bcrypt directly
password = "admin123"
# Convert to bytes and hash
salt = bcrypt.gensalt()
hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
hashed_str = hashed.decode('utf-8')

print("Creating admin user...")
print(f"Password hash: {hashed_str}")

# Connect to database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check if user table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user'")
if not cursor.fetchone():
    print("User table doesn't exist. Creating...")
    cursor.execute('''
        CREATE TABLE user (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            is_admin INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    print("User table created.")

# Check if admin already exists
cursor.execute("SELECT id, username FROM user WHERE username = 'admin'")
existing = cursor.fetchone()

if existing:
    print(f"Admin user already exists with ID: {existing[0]}")
    # Update password
    cursor.execute("UPDATE user SET hashed_password = ? WHERE username = 'admin'", (hashed_str,))
    conn.commit()
    print("Password updated!")
else:
    # Create new admin user
    user_id = str(uuid.uuid4())
    cursor.execute('''
        INSERT INTO user (id, username, email, hashed_password, is_active, is_admin)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, 'admin', 'admin@example.com', hashed_str, 1, 1))
    conn.commit()
    print("Admin user created successfully!")

print("\nLogin credentials:")
print("  Username: admin")
print("  Password: admin123")

# Verify we can read it back
cursor.execute("SELECT username, email, is_active FROM user WHERE username = 'admin'")
user = cursor.fetchone()
if user:
    print(f"\nVerified user in database:")
    print(f"  Username: {user[0]}")
    print(f"  Email: {user[1]}")
    print(f"  Active: {user[2]}")

conn.close()
