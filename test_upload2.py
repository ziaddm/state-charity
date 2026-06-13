import requests

# Login first
login_response = requests.post(
    "http://localhost:8000/api/auth/login",
    json={"email": "admin@charity.local", "password": "admin123"}
)
print(f"Login status: {login_response.status_code}")
token = login_response.json()["token"]

# Upload file
with open(r"C:\Users\ziadm\Desktop\VS Code\compliance-analytics\test_data\acme_health_1000_records.csv", "rb") as f:
    files = {"file": ("acme_health_1000_records.csv", f, "text/csv")}
    headers = {"Authorization": f"Bearer {token}"}

    upload_response = requests.post(
        "http://localhost:8000/api/validation/upload",
        files=files,
        headers=headers
    )

    print(f"\nUpload status: {upload_response.status_code}")
    result = upload_response.json()
    print(f"Success: {result.get('success')}")
    print(f"Status: {result.get('status')}")
    print(f"Errors: {result.get('error_count')}")
    print(f"Warnings: {result.get('warning_count')}")
    print(f"Total records: {result.get('total_records')}")
    print(f"Records ingested: {result.get('records_ingested')}")

    if result.get('records_ingested', 0) > 0:
        print("\nSUCCESS! Records were ingested!")
    else:
        print("\nFAILED! No records were ingested!")
