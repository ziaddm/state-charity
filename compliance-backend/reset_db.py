"""
Database reset script - drops all tables and recreates them from models.
This will give us a clean slate for implementing analytics.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect

# Add parent directory to path so we can import app
sys.path.insert(0, str(Path(__file__).parent))

from app.database.models import Base

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in .env file")

# URL encode the password if it contains special characters
from urllib.parse import quote_plus, urlparse, urlunparse

# Parse the URL
parsed = urlparse(DATABASE_URL)
if parsed.password and any(char in parsed.password for char in ['/', '*', '#', '&', '@', '%']):
    # Reconstruct URL with encoded password
    encoded_password = quote_plus(parsed.password)
    netloc = f"{parsed.username}:{encoded_password}@{parsed.hostname}:{parsed.port}"
    DATABASE_URL = urlunparse((parsed.scheme, netloc, parsed.path, '', '', ''))

print("Connecting to database...")
engine = create_engine(DATABASE_URL)

# Get all table names
inspector = inspect(engine)
existing_tables = inspector.get_table_names()

print(f"\nFound {len(existing_tables)} existing tables:")
for table in existing_tables:
    print(f"  - {table}")

# Ask for confirmation
print("\n⚠️  WARNING: This will DROP all existing tables and data!")
confirm = input("Type 'yes' to proceed: ")

if confirm.lower() != 'yes':
    print("Aborted.")
    exit(0)

print("\nDropping all tables...")
with engine.connect() as conn:
    # Drop all tables (including alembic_version if it exists)
    for table in existing_tables:
        print(f"  Dropping {table}...")
        conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
    conn.commit()

print("\nRecreating tables from models...")
Base.metadata.create_all(bind=engine)

# Verify new tables
inspector = inspect(engine)
new_tables = inspector.get_table_names()

print(f"\n✅ Database reset complete!")
print(f"Created {len(new_tables)} tables:")
for table in new_tables:
    print(f"  - {table}")

print("\nYou now have a clean database ready for analytics implementation.")
