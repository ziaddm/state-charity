# Validation Error & Warning Code Reference

**System**: Healthcare Compliance Analytics - State Charity Care Reporting
**Last Updated**: 2025-11-05
**Philosophy**: Fail open, not closed - Trust operators, flag concerns, only block catastrophic issues

---

## Table of Contents
1. [Error Codes (Block Submission)](#error-codes-block-submission)
2. [Warning Codes (Flag for Review)](#warning-codes-flag-for-review)
3. [Info Codes (Informational)](#info-codes-informational)
4. [Severity Override Guide](#severity-override-guide)

---

## Error Codes (Block Submission)

**Philosophy**: Only block submission for catastrophic issues that would cause state rejection or break processing.

| Code | Type | Description | Example | Recommended Action |
|------|------|-------------|---------|-------------------|
| **E001** | required_missing | Required field is missing or empty | Patient ID is blank | Add missing required field value |
| **E002** | too_long | Field exceeds maximum length (breaks fixed-width output) | Last name is 25 chars but max is 20 | Truncate or abbreviate field value |
| **E003** | too_short | Required field below minimum length | Required SSN is only 8 digits | Complete the field value |
| **E004** | invalid_enum | Invalid enum value (when explicitly configured as error) | Gender code "X" not in [M, F, U] | Use valid code or update schema if new valid code |
| **E005** | below_min | Numeric value below minimum bound (when critical) | Age is -5 | Correct the value or verify data entry |
| **E006** | above_max | Numeric value above maximum bound (when critical) | Total charges exceed $999,999,999 | Verify amount or split into multiple records |
| **E007** | invalid_type | Field value is wrong data type | Date field contains "N/A" text | Provide valid date or leave empty |
| **E008** | unparseable_date | Date format cannot be parsed | Birth date is "13/45/2020" | Use valid date format (MM/DD/YYYY) |
| **E100** | cross_field_violation | Cross-field rule violation (error level) | Payment received ($1000) > Total charges ($500) | Verify amounts and correct discrepancy |
| **E300** | duplicate_record_id | Duplicate record_id/encounter_id in submission | Encounter ID "12345" appears twice | Ensure unique identifier for each visit |
| **E500** | schema_mismatch | Input data missing required canonical column | Canonical field "patient_id" not found | Update field mappings in tenant config |
| **E501** | output_generation_failed | Failed to write output file | Disk full or permission denied | Check system resources and permissions |

---

## Warning Codes (Flag for Review)

**Philosophy**: Flag potential issues but allow submission with operator acknowledgment. Healthcare data is messy - trust the operator.

### Field Validation Warnings (W001-W099)

| Code | Type | Description | Example | Why Warning, Not Error |
|------|------|-------------|---------|----------------------|
| **W001** | too_short | Optional field below minimum length | Middle initial missing | Common, not critical |
| **W002** | recommended_missing | Recommended field is missing | Payor source not provided | Reduces data quality but not blocking |
| **W004** | invalid_enum | Value not in expected enum list | Payor code "XX" not recognized | Might be new valid code from state |
| **W005** | below_min | Numeric value below expected minimum | Family income is $1 | Might be edge case (unemployed, etc) |
| **W006** | above_max | Numeric value above expected maximum | Family size is 25 people | Might be legitimate (group home, etc) |
| **W010** | suspicious_length | Field length is unusual but not invalid | Last name is 2 characters | Might be legitimate (e.g., "Wu", "Li") |
| **W011** | suspicious_pattern | Field pattern is unusual | Phone number is all zeros | Might be placeholder, verify before submission |
| **W012** | future_date | Date is in the future | Visit date is tomorrow | Might be pre-scheduled visit |
| **W013** | very_old_date | Date is suspiciously old | Birth date is 1890 | Might be data entry error (typo) |
| **W020** | missing_leading_zero | Numeric code missing expected leading zero | ZIP code "8901" instead of "08901" | Common formatting issue |

### Data Quality Warnings (W100-W199)

| Code | Type | Description | Example | Recommendation |
|------|------|-------------|---------|----------------|
| **W100** | cross_field_violation | Cross-field rule violation (warn level) | Visit date before birth date by 1 day | Verify dates, might be timezone/typo |
| **W101** | unusual_combination | Unusual but not invalid field combination | Medicare + Age 25 | Possible disability Medicare, verify |
| **W102** | inconsistent_fields | Fields appear inconsistent | Self-pay + Medicaid insurance name | Review insurance classification |
| **W110** | missing_dependent_field | Related field missing when expected | Insurance name present but no payor code | Add payor code for completeness |
| **W111** | unexpected_dependent_field | Related field present when not expected | Uninsured but insurance name provided | Verify payor classification |
| **W120** | duplicate_diagnosis | Same diagnosis code appears multiple times | ICD code Z00.0 in slots 1 and 3 | Remove duplicate or verify |
| **W121** | conflicting_diagnosis | Diagnosis codes appear to conflict | Pregnancy (Z33) + Male gender | Verify gender or diagnosis |

### Financial Warnings (W200-W299)

| Code | Type | Description | Example | Recommendation |
|------|------|-------------|---------|----------------|
| **W200** | zero_charges | Total charges is zero | Visit with $0 charge | Verify if truly no-charge visit |
| **W201** | zero_payment | Payment received is zero | Visit with $0 payment | Common for charity care, verify intent |
| **W202** | high_payment_ratio | Payment exceeds 100% of charges | Payment $1000 > Charges $900 | Verify amounts or check for adjustments |
| **W203** | suspiciously_round | Amount is suspiciously round number | Charges exactly $1000.00 | Might be estimate, verify actual amount |
| **W210** | income_fpl_mismatch | Income doesn't match FPL calculation | Income $50k but FPL shows 100% | Verify FPL calculation |
| **W211** | uncompensated_with_payment | Uncompensated visit flag but payment received | Charity care = Y but payment = $100 | Verify classification |

### Demographic Warnings (W300-W399)

| Code | Type | Description | Example | Why Warning |
|------|------|-------------|---------|-------------|
| **W300** | missing_race | Race/ethnicity not provided | Race field empty | Common data gap, not blocking |
| **W301** | missing_address | Address information incomplete | City present but no street | Reduces data quality |
| **W310** | out_of_state | Patient address outside reporting state | NJ report but patient in PA | Common for border clinics |
| **W311** | missing_census_tract | Census tract not provided | Census tract field empty | Reduces geographic analysis |
| **W320** | gender_diagnosis_mismatch | Gender doesn't match typical diagnosis | Prostate exam + Female gender | Transgender/intersex patients exist |
| **W321** | age_diagnosis_mismatch | Age unusual for diagnosis | Alzheimer's diagnosis + Age 25 | Rare but possible early onset |
| **W330** | extreme_age | Patient age is extreme | Age 0 or 120+ | Verify birth date, might be typo |

### Visit/Encounter Warnings (W400-W499)

| Code | Type | Description | Example | Recommendation |
|------|------|-------------|---------|----------------|
| **W400** | missing_visit_time | Visit time not provided | Visit time field empty | Consider adding for completeness |
| **W401** | after_hours_visit | Visit time outside normal hours | Visit at 2:00 AM | Verify if emergency/after-hours |
| **W410** | multiple_visits_same_day | Multiple visits on same date for patient | 3 visits on 1/15/2024 | Verify if separate encounters |
| **W411** | rapid_readmission | Visit within 24h of previous visit | Visits 8 hours apart | Might indicate complication |
| **W420** | missing_diagnosis | No diagnosis codes provided | All ICD slots empty | Consider adding primary diagnosis |
| **W421** | single_diagnosis_only | Only one diagnosis when multiple expected | Only ICD_1 filled | Consider secondary diagnoses |

### Migrant/Special Population Warnings (W500-W599)

| Code | Type | Description | Example | Recommendation |
|------|------|-------------|---------|----------------|
| **W500** | missing_migrant_status | Migrant farmer status not indicated | Field empty or unknown | Consider completing if applicable |
| **W501** | missing_family_care_history | Family care history not provided | Medicaid/uninsured history empty | Reduces program eligibility insight |

### System/Processing Warnings (W600-W699)

| Code | Type | Description | Example | Action |
|------|------|-------------|---------|--------|
| **W600** | coercion_applied | Value was automatically coerced | "  SMITH  " → "SMITH" | Review coerced value |
| **W601** | default_value_used | Missing optional field filled with default | Empty payor → "UN" (Uninsured) | Verify assumption |
| **W602** | ambiguous_mapping | Source field mapping is ambiguous | "Comm Ins" could map to multiple codes | Verify mapping |
| **W603** | unmapped_source_field | Source field has no canonical mapping | Field "custom_flag" ignored | Update tenant config if needed |
| **W604** | schema_version_mismatch | Schema version differs from expected | Using v2 schema, v3 available | Consider updating |

---

## Info Codes (Informational)

**Philosophy**: Informational messages for auditing, statistics, and transparency. Never block submission.

| Code | Type | Description | Example | Purpose |
|------|------|-------------|---------|---------|
| **I001** | record_processed | Record successfully validated | Row 1 passed validation | Audit trail |
| **I002** | coercion_successful | Value successfully coerced to standard format | "01/15/2024" → 2024-01-15 | Transparency |
| **I003** | default_applied | Default value applied to optional field | Empty claim_type → "O" | Transparency |
| **I010** | statistical_summary | Summary statistics for submission | 500 records, 480 passed, 20 warnings | Overview |
| **I100** | new_value_detected | Previously unseen enum value detected | New payor code "ZZ" observed | State code updates |
| **I101** | data_quality_metric | Data quality score/metric | Completeness: 87% | Quality monitoring |

---

## Severity Override Guide

### Schema-Level Override

You can override default severities in the schema definition:

```python
"payor_source": {
    "dtype": "string",
    "required": False,
    "enum": ["MC", "MD", "PR", "UN", "OT"],
    "severity": {
        "invalid_enum": "error",  # Override default warning to error
        "below_min": "warning",   # Keep as warning (default)
    }
}
```

### When to Override to ERROR

Override to error when:
- State will reject submission for this specific violation
- Downstream processing will catastrophically fail
- Data correction is straightforward and non-controversial
- False positives are extremely rare

### When to Keep as WARNING

Keep as warning when:
- Edge cases exist (transgender, group homes, complex family structures)
- State codes change periodically (new diagnosis codes, new payor types)
- Data entry errors are common but operator can verify
- Clinical judgment needed to determine validity
- Historical data may use different standards

---

## Validation Flow

```
Input Record
    ↓
Field Validation
    ↓
├─ Required Check → E001 if missing
├─ Length Check → E002/E003/W001
├─ Enum Check → W004 (default) or E004 (if overridden)
├─ Bounds Check → W005/W006 (default) or E005/E006 (if overridden)
└─ Type Check → E007/E008 if invalid type
    ↓
Cross-Field Validation
    ↓
├─ Business Rules → E100 (error) or W100 (warning)
└─ Logical Consistency → W101-W121
    ↓
Financial Validation → W200-W299
    ↓
Demographic Validation → W300-W399
    ↓
Result
    ↓
├─ ERRORS > 0 → Block submission, status = "errors"
├─ ERRORS = 0, WARNINGS > 0 → Allow with acknowledgment, status = "ready"
└─ ERRORS = 0, WARNINGS = 0 → Pass, status = "ready"
```

---

## Examples

### Example 1: Lenient Enum Handling

**Scenario**: Payor source field receives "XX" but schema expects ["MC", "MD", "PR", "UN", "OT"]

**Old Behavior**: E004 ERROR - blocks submission
**New Behavior**: W004 WARNING - flags for review
**Rationale**: State might have introduced new payor code "XX". Operator can verify and state will either accept or reject with clear guidance.

### Example 2: Gender-Specific Diagnosis

**Scenario**: Female patient with prostate-related diagnosis code

**Behavior**: W320 WARNING - gender_diagnosis_mismatch
**Rationale**: Patient might be transgender, intersex, or diagnosis might be for family history. Clinical staff should review, but don't assume error.

### Example 3: Extreme Family Size

**Scenario**: Family size = 25 people

**Old Behavior**: E006 ERROR - blocks submission
**New Behavior**: W006 WARNING - flags for review
**Rationale**: Might be group home, multi-generational household, or data entry error. Operator can verify.

### Example 4: Critical Length Violation

**Scenario**: Last name is 30 characters but NJ fixed-width format allows 20

**Behavior**: E002 ERROR - blocks submission
**Rationale**: Will break fixed-width output file. Must be truncated or abbreviated. This is non-negotiable.

---

## Configuration Reference

### Default Severity Configuration

Located in: `app/validation/validator.py`

```python
VALIDATION_DEFAULTS = {
    "required_missing": "error",       # Always error
    "too_long": "error",              # Always error (breaks output)
    "too_short": "warning",           # Warning (might be incomplete)
    "invalid_enum": "warning",        # WARNING (might be new code)
    "below_min": "warning",           # WARNING (might be edge case)
    "above_max": "warning",           # WARNING (might be edge case)
    "invalid_type": "error",          # Error (breaks processing)
    "unparseable_date": "error",      # Error (breaks processing)
    "cross_field_violation": "error", # Default error, override per rule
}
```

### Per-Rule Configuration

Located in: `app/schema/nj_schema.py`

```python
CROSS_FIELD_RULES = [
    # ERRORS - block submission
    {"rule": "total_payment_received <= total_charges", "on_fail": "error"},

    # WARNINGS - flag but allow
    {"rule": "visit_date >= date_of_birth", "on_fail": "warn"},
]
```

---

## MVP Specification Compliance

Per **MVP Specification v1, Section 5.3**:

✅ **Errors**: Block submission, must be corrected
✅ **Warnings**: Flagged, operator acknowledgment required
✅ **Each event carries**: code, severity, message, field reference
✅ **Structured format**: JSON output with error_count, warning_count

**Spec Quote**:
> "Validation failures shall be categorized as either errors (blocking submission) or warnings (requiring operator acknowledgment). Each validation event shall include an error code, severity level, human-readable message, and reference to the affected field(s)."

This implementation maintains full spec compliance while adopting a pragmatic, healthcare-appropriate validation philosophy.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-11-05 | Initial release with lenient validation approach |

---

## Support

For questions about validation codes or to request severity overrides, contact the compliance analytics team or refer to:
- Schema definitions: `app/schema/nj_schema.py`
- Validator logic: `app/validation/validator.py`
- Tenant configs: `config/tenants/*.yaml`
