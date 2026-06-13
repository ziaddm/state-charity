import sys
sys.path.insert(0, '.')
from app.database.connection import engine, init_db
from sqlalchemy import text

# Test connection
with engine.connect() as conn:
    result = conn.execute(text('SELECT version()'))
    print('Connected:', result.fetchone()[0][:60])

# Create all tables
print('Creating tables...')
init_db()
print('Done.')

# Verify
with engine.connect() as conn:
    result = conn.execute(text(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
    ))
    tables = [r[0] for r in result]
    print('Tables:', tables)
