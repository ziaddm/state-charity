from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv(Path('.').parent / '.env', override=True)
DATABASE_URL = os.getenv('DATABASE_URL')
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    conn.execute(text('ALTER TABLE tenants ADD COLUMN IF NOT EXISTS config_path VARCHAR'))
    conn.commit()
    print('Added config_path column to tenants table')
