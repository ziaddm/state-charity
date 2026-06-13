import sys
sys.path.insert(0, r"C:\Users\ziadm\Desktop\VS Code\compliance-analytics\compliance-backend")

from app.database.connection import SessionLocal
from app.database.models import User

db = SessionLocal()

# Get all users
users = db.query(User).all()
for user in users:
    print(f"User ID: {user.id}")
    print(f"Email: {user.email}")
    print(f"Tenant ID: {user.tenant_id}")
    print("---")

db.close()
