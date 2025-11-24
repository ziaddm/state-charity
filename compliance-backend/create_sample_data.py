"""
Create sample tenant (Acme Health) with sample validation runs and data
"""
import os
import uuid
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import bcrypt
from datetime import datetime, timezone, timedelta
import random

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in .env file")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# Import models directly
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Integer, Text
from datetime import datetime, timezone

Base = declarative_base()

class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    state_code = Column(String(2))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String)
    is_active = Column(Boolean, default=False)
    must_change_password = Column(Boolean, default=True)
    last_login = Column(DateTime)
    created_by_user_id = Column(String, ForeignKey("users.id"))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class ValidationRun(Base):
    __tablename__ = "runs"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    created_by_user_id = Column(String, ForeignKey("users.id"))
    state_code = Column(String(2))
    status = Column(String)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_count = Column(Integer, default=0)
    warning_count = Column(Integer, default=0)
    record_count = Column(Integer, default=0)
    valid_count = Column(Integer, default=0)
    source_filename = Column(String)
    source_file_hash = Column(String)
    submission_file_path = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class ValidationError(Base):
    __tablename__ = "errors"
    id = Column(String, primary_key=True)
    run_id = Column(String, ForeignKey("runs.id"), nullable=False)
    row_number = Column(Integer)
    field_name = Column(String)
    error_type = Column(String)
    error_message = Column(Text)
    severity = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

# Create sample data
db = SessionLocal()

try:
    # Check if Acme Health already exists
    existing_tenant = db.query(Tenant).filter(Tenant.name == "Acme Health").first()
    existing_user = db.query(User).filter(User.email == "user@acmehealth.com").first()

    if existing_tenant and existing_user:
        print("Acme Health tenant and user already exist. Using existing data...")
        acme_tenant_id = existing_tenant.id
        acme_user_id = existing_user.id
        print(f"[OK] Using tenant: Acme Health (ID: {acme_tenant_id})")
        print(f"[OK] Using user: user@acmehealth.com")
    else:
        print("Creating Acme Health tenant...")

        # Create Acme Health tenant
        if not existing_tenant:
            acme_tenant_id = str(uuid.uuid4())
            acme_tenant = Tenant(
                id=acme_tenant_id,
                name="Acme Health",
                state_code="CA"
            )
            db.add(acme_tenant)
            db.commit()
            print(f"[OK] Created tenant: Acme Health (ID: {acme_tenant_id})")
        else:
            acme_tenant_id = existing_tenant.id
            print(f"[OK] Using existing tenant: Acme Health (ID: {acme_tenant_id})")

        # Create a user for Acme Health
        if not existing_user:
            print("\nCreating user for Acme Health...")
            password = "acme123"
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

            acme_user_id = str(uuid.uuid4())
            acme_user = User(
                id=acme_user_id,
                tenant_id=acme_tenant_id,
                email="user@acmehealth.com",
                password_hash=hashed_password,
                role="user",
                is_active=True,
                must_change_password=False
            )
            db.add(acme_user)
            db.commit()
            print(f"[OK] Created user: user@acmehealth.com (password: acme123)")
        else:
            acme_user_id = existing_user.id
            print(f"[OK] Using existing user: user@acmehealth.com")

    # Create sample validation runs with varying success/error rates
    print("\nCreating sample validation runs...")

    # Generate runs over the past 30 days
    runs_created = 0
    for days_ago in range(30, 0, -1):
        # Create 1-3 runs per day
        num_runs = random.randint(1, 3)

        for _ in range(num_runs):
            run_date = datetime.now(timezone.utc) - timedelta(days=days_ago, hours=random.randint(0, 23))

            # Vary the outcomes
            outcome = random.choices(
                ['success', 'warnings', 'errors'],
                weights=[70, 20, 10]  # 70% success, 20% warnings, 10% errors
            )[0]

            record_count = random.randint(50, 500)

            if outcome == 'success':
                error_count = 0
                warning_count = 0
                valid_count = record_count
                status = 'completed'
            elif outcome == 'warnings':
                error_count = 0
                warning_count = random.randint(1, 10)
                valid_count = record_count - warning_count
                status = 'completed_with_warnings'
            else:  # errors
                error_count = random.randint(1, 20)
                warning_count = random.randint(0, 5)
                valid_count = record_count - error_count - warning_count
                status = 'completed_with_errors'

            run_id = str(uuid.uuid4())
            validation_run = ValidationRun(
                id=run_id,
                tenant_id=acme_tenant_id,
                created_by_user_id=acme_user_id,
                state_code="CA",
                status=status,
                started_at=run_date,
                completed_at=run_date + timedelta(seconds=random.randint(10, 120)),
                error_count=error_count,
                warning_count=warning_count,
                record_count=record_count,
                valid_count=valid_count,
                source_filename=f"acme_health_submission_{run_date.strftime('%Y%m%d')}.csv",
                source_file_hash=str(uuid.uuid4()),
                submission_file_path=f"/submissions/{run_id}/submission.csv",
                created_at=run_date
            )
            db.add(validation_run)
            db.commit()  # Commit the run before adding errors

            # Add some sample errors if there were errors
            if error_count > 0:
                for i in range(min(error_count, 5)):  # Add up to 5 error records
                    error_id = str(uuid.uuid4())
                    error_types = ['missing_required_field', 'invalid_format', 'invalid_value', 'duplicate_record']
                    field_names = ['patient_id', 'service_date', 'amount', 'diagnosis_code', 'provider_npi']

                    error = ValidationError(
                        id=error_id,
                        run_id=run_id,
                        row_number=random.randint(1, record_count),
                        field_name=random.choice(field_names),
                        error_type=random.choice(error_types),
                        error_message=f"Sample error message for validation",
                        severity='error',
                        created_at=run_date
                    )
                    db.add(error)

                db.commit()  # Commit errors for this run

            runs_created += 1

    print(f"[OK] Created {runs_created} validation runs with sample data")

    print("\n" + "="*60)
    print("[SUCCESS] Sample data created!")
    print("="*60)
    print(f"\nTenant: Acme Health")
    print(f"  ID: {acme_tenant_id}")
    print(f"  State: CA")
    print(f"\nUser Credentials:")
    print(f"  Email: user@acmehealth.com")
    print(f"  Password: acme123")
    print(f"\nValidation Runs: {runs_created} runs over the past 30 days")
    print(f"  - Mix of successful, warning, and error outcomes")
    print(f"  - Record counts: 50-500 per run")
    print(f"  - Sample error records included")
    print("\nYou can now log in and see analytics data!")

except Exception as e:
    db.rollback()
    print(f"[ERROR] Failed to create sample data: {e}")
    raise
finally:
    db.close()
