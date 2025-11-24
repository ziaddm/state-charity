"""
Add patient_visits table to database
"""
from sqlalchemy import create_engine
from dotenv import load_dotenv
from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(__file__).parent))

load_dotenv(Path(__file__).parent.parent / ".env", override=True)
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found")

engine = create_engine(DATABASE_URL)

from app.database.models import Base, PatientVisit

print("Creating patient_visits table...")
PatientVisit.__table__.create(bind=engine, checkfirst=True)
print("[SUCCESS] patient_visits table created!")
