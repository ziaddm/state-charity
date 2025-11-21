"""
Quick database connection test
Run with: python test_db.py
"""
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database.connection import engine, init_db
from app.database.models import Tenant, User

print("Testing database connection...\n")

# Test 1: Connect to database
try:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    print("✅ Connected to database successfully")
except Exception as e:
    print(f"❌ Connection failed: {e}")
    exit(1)

# Test 2: Create all tables
try:
    init_db()
    print("✅ Tables created successfully")
except Exception as e:
    print(f"❌ Failed to create tables: {e}")
    exit(1)

# Test 3: Insert and retrieve a tenant
try:
    db = Session(engine)

    test_tenant = Tenant(
        id="test-tenant-123",
        name="Test Organization",
        state_code="NJ"
    )
    db.add(test_tenant)
    db.commit()
    print("✅ Successfully inserted test tenant")

    # Query it back
    result = db.query(Tenant).filter(Tenant.id == "test-tenant-123").first()
    if result:
        print(f"✅ Retrieved tenant: {result.name} (state: {result.state_code})")
    else:
        print("❌ Failed to retrieve tenant")
        exit(1)

    # Clean up
    db.delete(result)
    db.commit()
    print("✅ Cleanup successful (deleted test tenant)")

except Exception as e:
    print(f"❌ Database operations failed: {e}")
    exit(1)
finally:
    db.close()

# Test 4: Insert and retrieve a user
try:
    db = Session(engine)

    # First create a tenant (users need a tenant_id)
    test_tenant = Tenant(
        id="test-tenant-user",
        name="Test Org for User",
        state_code="NJ"
    )
    db.add(test_tenant)
    db.commit()

    test_user = User(
        id="test-user-123",
        email="testuser@example.com",
        password_hash="hashed_password_example",
        tenant_id="test-tenant-user",
        role="operator",
        is_active=True,
        must_change_password=True
    )
    db.add(test_user)
    db.commit()
    print("✅ Successfully inserted test user")

    # Query it back
    result = db.query(User).filter(User.email == "testuser@example.com").first()
    if result:
        print(f"✅ Retrieved user: {result.email} (role: {result.role})")
    else:
        print("❌ Failed to retrieve user")
        exit(1)

    # Clean up
    db.delete(result)
    db.delete(db.query(Tenant).filter(Tenant.id == "test-tenant-user").first())
    db.commit()
    print("✅ Cleanup successful (deleted test user and tenant)")

except Exception as e:
    print(f"❌ User operations failed: {e}")
    exit(1)
finally:
    db.close()

print("\n🎉 All database tests passed!")
