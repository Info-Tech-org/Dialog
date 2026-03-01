"""
Simplest way to create admin user using raw SQL
"""
import sqlite3
import hashlib
import uuid

# Create a simple hashed password (not bcrypt, just for testing)
def simple_hash(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Connect to database
conn = sqlite3.connect('E:/Innox-SZ/info-tech/backend/data/family_emotion.db')
cursor = conn.cursor()

# Check if user table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user'")
if not cursor.fetchone():
    print("User table doesn't exist. Creating tables...")
    # Create user table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        )
    ''')
    conn.commit()
    print("User table created.")

# Check if admin exists
cursor.execute("SELECT * FROM user WHERE username = 'admin'")
existing = cursor.fetchone()

if existing:
    print("Admin user already exists!")
    print(f"Row: {existing}")
else:
    # Insert admin user with simple hash
    user_id = str(uuid.uuid4())
    # Use a simple hash for now
    hashed_pw = simple_hash("admin123")

    cursor.execute('''
        INSERT INTO user (id, username, email, hashed_password, is_active)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, 'admin', 'admin@example.com', hashed_pw, 1))

    conn.commit()
    print("Admin user created successfully!")
    print("  Username: admin")
    print("  Password: admin123")
    print("  Note: Using simple hash for testing")

conn.close()
