"""
Simple script to create admin user directly using the API
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

# First, make sure database exists
from models.db import create_db_and_tables, engine
from models.user_model import User
from api.auth import get_password_hash
from sqlmodel import Session

print("Creating database tables...")
create_db_and_tables()

print("Creating admin user...")
try:
    with Session(engine) as session:
        # Check if admin already exists
        from sqlmodel import select
        existing_user = session.exec(select(User).where(User.username == "admin")).first()

        if existing_user:
            print("Admin user already exists!")
            print(f"  Username: {existing_user.username}")
            print(f"  Email: {existing_user.email}")
        else:
            # Create admin user
            admin_user = User(
                username="admin",
                email="admin@example.com",
                hashed_password=get_password_hash("admin123"),
                is_active=True
            )
            session.add(admin_user)
            session.commit()
            print("Admin user created successfully!")
            print("  Username: admin")
            print("  Password: admin123")
            print("  Email: admin@example.com")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
