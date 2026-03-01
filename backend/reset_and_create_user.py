"""
Reset database and create admin user properly
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from models.db import create_db_and_tables, engine
from models.user_model import User
from api.auth import get_password_hash
from sqlmodel import Session

print("Recreating database tables...")
# Drop existing data directory and recreate
import shutil
if os.path.exists('data/family_emotion.db'):
    os.remove('data/family_emotion.db')
    print("Removed old database")

create_db_and_tables()
print("Database tables created")

print("\nCreating admin user...")
try:
    with Session(engine) as session:
        admin_user = User(
            username="admin",
            email="admin@example.com",
            hashed_password=get_password_hash("admin123"),
            is_active=True,
            is_admin=True
        )
        session.add(admin_user)
        session.commit()
        session.refresh(admin_user)

        print("Admin user created successfully!")
        print(f"  ID: {admin_user.id}")
        print(f"  Username: {admin_user.username}")
        print(f"  Email: {admin_user.email}")
        print(f"  Is Admin: {admin_user.is_admin}")
        print("\nLogin credentials:")
        print("  Username: admin")
        print("  Password: admin123")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
