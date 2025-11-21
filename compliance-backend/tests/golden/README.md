# Golden File Tests

**Status**: ✅ Implemented
**Spec Reference**: MVP Spec Section 5.5 - Golden-file tests for each state

---

## What Are Golden Files?

Golden files are **byte-perfect reference outputs** used for regression testing. They ensure that:

1. **Same input → Same output** (determinism)
2. **Format never changes unexpectedly** (catches regressions)
3. **State submission files remain compliant** (byte-for-byte accuracy)

---

## Running Golden File Tests

```bash
# Run all golden file tests
python tests/run_golden_tests.py

# Expected output:
# [PASS] NJ Golden File Match: PASSED
# [PASS] NJ Determinism: PASSED
# Total: 2/2 passed
```

---

## Directory Structure

```
tests/golden/
├── README.md                    # This file
├── nj/
│   ├── nj_submission_input.csv  # Input that generates golden file
│   ├── nj_submission.golden.txt # THE reference output for NJ
│   └── test_output/             # Temporary test outputs (gitignored)
└── ny/                          # Future: NY state golden files
    └── ...
```

---

## What The Tests Do

### Test 1: Golden File Match
- Generates NJ submission from `nj_submission_input.csv`
- Compares byte-for-byte against `nj_submission.golden.txt`
- **Fails if output differs** → regression detected!

### Test 2: Determinism
- Runs generation **twice** with same input
- Verifies outputs are **identical**
- Per MVP Spec Section 3.1: "same input must always yield same output"

---

## When Tests Fail

### Scenario 1: Unintentional Change (Regression)
```
[FAIL] NJ Golden File Match: FAILED
  Output differs from golden file

DIFF:
- ACME HEALTH    NJHOSP01  20250131
+ ACME HEALTH    NJ-HOSP01 20250131  # REGRESSION!
```

**Action**: Fix the regression! The format changed unexpectedly.

### Scenario 2: Intentional Change (Bug Fix)
```
[FAIL] NJ Golden File Match: FAILED
  Output differs from golden file
```

You fixed a bug that changes the output format (e.g., date formatting).

**Action**: Update the golden file:
```bash
# Regenerate output with fixed code
python -m app.main acme_health NJ tests/golden/nj/nj_submission_input.csv --output-dir tests/golden/nj

# Copy new output to golden file
cp tests/golden/nj/acme_health/.../acme_health_NJ_*.txt tests/golden/nj/nj_submission.golden.txt

# Tests now pass
python tests/run_golden_tests.py
```

---

## Golden File Details

### NJ Golden File
- **Input**: `nj_submission_input.csv` (5 records)
- **Output**: `nj_submission.golden.txt` (1,065 bytes)
- **Format**: Fixed-width, 212 bytes per record + 1 byte newline
- **Fields**: 31 fields per NJ spec (Appendix B)

### Calculation
```
1 header row:    0 bytes  (NJ has no header)
5 data rows:     5 × 213 bytes = 1,065 bytes
Total:           1,065 bytes
```

---

## Why This Matters

State submission systems are **extremely strict**:

1. **One wrong byte** = entire file rejected
2. **Rejections are costly** (delays reimbursement)
3. **May not discover issues until submission** (weeks later)

**Golden files catch these issues in seconds**, not weeks.

---

## Example: What Golden Files Catch

### Bug 1: Field Position Drift
```diff
# Before (correct):
ENC001MRN1234520250115...
      ^--- Patient ID at position 3-14

# After (broken):
ENC001 MRN1234520250115...  # Added space!
      ^--- Patient ID now at position 4-15 → REJECTED
```

### Bug 2: Formatting Change
```diff
- 0000012345  # Charges: zero-padded 10 digits
+ 12345       # Lost padding → field positions wrong → REJECTED
```

### Bug 3: Date Format
```diff
- 20250115    # YYYYMMDD (correct)
+ 01/15/2025  # MM/DD/YYYY (breaks fixed-width) → REJECTED
```

---

## Adding New Golden Files

### For a New State (e.g., NY)

1. **Create directory**:
   ```bash
   mkdir -p tests/golden/ny
   ```

2. **Generate golden output**:
   ```bash
   python -m app.main acme_health NY test_data/acme_health_sample_ny.csv --output-dir tests/golden/ny
   ```

3. **Manually verify output is correct**:
   ```bash
   cat tests/golden/ny/.../acme_health_NY_*.txt
   # Visually inspect or compare against NY spec
   ```

4. **Save as golden**:
   ```bash
   cp tests/golden/ny/.../acme_health_NY_*.txt tests/golden/ny/ny_submission.golden.txt
   cp test_data/acme_health_sample_ny.csv tests/golden/ny/ny_submission_input.csv
   ```

5. **Add test** in `run_golden_tests.py`:
   ```python
   def test_ny_golden_file():
       # Similar to NJ test
       ...
   ```

---

## Best Practices

1. **Keep golden input small** (5-50 records)
   - Fast tests
   - Easy to understand diffs

2. **Use clean data** (no errors/warnings)
   - Golden file represents "happy path"
   - Validation errors tested separately

3. **Version control golden files**
   - Commit both `.golden.txt` and `_input.csv`
   - Changes show in pull request diffs

4. **Run before every commit**
   - Catches regressions immediately
   - Prevents broken submissions

5. **Update intentionally**
   - Only update golden files when format change is intentional
   - Document why in commit message

---

## CI/CD Integration

Add to your CI pipeline:

```yaml
# .github/workflows/test.yml
- name: Run golden file tests
  run: python tests/run_golden_tests.py
```

Failures will block merges, preventing regressions from reaching production.

---

## Current Test Coverage

| State | Golden File | Records | Status |
|-------|-------------|---------|--------|
| NJ    | ✅ | 5 | Passing |
| NY    | ❌ | - | Not yet implemented |

---

## Spec Compliance

✅ **MVP Spec Section 5.5**: "Golden-file tests for each state"
✅ **MVP Spec Section 3.1**: "Same input must always yield same output"
✅ **MVP Spec Section 5.7**: "Idempotent: same input → same output"

---

**Status**: ✅ Golden file tests implemented and passing
**Last Updated**: 2025-11-08
