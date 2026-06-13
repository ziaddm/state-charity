"""
Clear test data from patient_visits table
"""
from app.database.connection import get_db
from app.database.models import PatientVisit

db = next(get_db())

# Delete all test records
count = db.query(PatientVisit).delete()
db.commit()

print(f"✓ Deleted {count} test records from patient_visits table")
print("Database is now clean - try uploading your file again!")
