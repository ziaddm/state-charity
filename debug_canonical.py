import sys
sys.path.insert(0, r"C:\Users\ziadm\Desktop\VS Code\compliance-analytics\compliance-backend")

from pathlib import Path
from app.adapters.report_adapter import ReportAdapter

# Test with the sample file
adapter = ReportAdapter(
    tenant_id="acme_health",
    state_code="NJ",
    run_id="test123"
)

test_file = Path(r"C:\Users\ziadm\Desktop\VS Code\compliance-analytics\test_data\acme_health_sample.csv")

artifact = adapter.generate(source_file_path=test_file)

print("=== CANONICAL DATA ===")
if artifact.canonical_data:
    print(f"Number of records: {len(artifact.canonical_data)}")
    print("\nFirst record fields:")
    for key, value in artifact.canonical_data[0].items():
        print(f"  {key}: {value} (type: {type(value).__name__})")
else:
    print("No canonical data!")
