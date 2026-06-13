import sys
sys.path.insert(0, r"C:\Users\ziadm\Desktop\VS Code\compliance-analytics\compliance-backend")

from app.database.connection import engine
from sqlalchemy import text

conn = engine.connect()
result = conn.execute(text("SELECT COUNT(*) FROM patient_visits WHERE tenant_id = 'acme_health'"))
count = result.scalar()
print(f"Total records for acme_health: {count}")

# Check if there are records from the 1000 record file
result2 = conn.execute(text("SELECT DISTINCT source_file_hash FROM patient_visits WHERE tenant_id = 'acme_health' LIMIT 5"))
hashes = [row[0][:16] for row in result2]
print(f"File hashes: {hashes}")

conn.close()
