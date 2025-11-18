# Constant data dictionary for Charity Care - Canonical Visits

SCHEMA_META = {
    "version": "1.0.1",
    "dataset": "canonical_visits",
    "description": "Canonical dataset for state-ready visit submissions",
    "primary_key": ["record_id"],
    "defaults": {
        "timezone": "America/New_York",
        "date_format": "YYYY-MM-DD",   # input parsing shape
        "time_format": "HH:mm:ss",     # visit_time must serialize to 8 chars in output
        "decimal_mark": ".",
        "empty_values": ["", "NA", "N/A", "null", "Null", "NULL"],
    },
    "policies": {
        "allow_extra_columns": False,
        "require_all_columns": True,
        "fail_fast": False, # don't stop at first error, collect all
    },
}

CANONICAL_VISITS_SCHEMA = {
    # Patient Information
    "patient_id": {
        "dtype": "string", "required": True, "coercion": ["trim"],
        "length": {"max": 12},
    },
    "last_name":  {"dtype": "string", "required": False, "coercion": ["trim", "to_upper"]},
    "first_name": {"dtype": "string", "required": False, "coercion": ["trim", "to_upper"]},
    "middle_initial": {
        "dtype": "string", "required": False, "length": {"max": 1},
        "coercion": ["trim", "to_upper"],
    },
    "date_of_birth": {
        "dtype": "date", "required": False, "format": "YYYY-MM-DD",
        "coercion": [{"parse_date": ["YYYY-MM-DD", "YYYY/MM/DD", "YYYYMMDD", "MM/DD/YYYY"]}],
    },
    "gender": {
        "dtype": "string", "required": False, "coercion": ["trim", "to_upper"],
        "enum_ref": "gender.codes", "length": {"max": 1},
    },
    "ethnicity": {
        "dtype": "string", "required": False, "coercion": ["trim", "to_upper"],
        "enum_ref": "ethnicity.codes", "length": {"max": 1},
    },
    "race": {
        "dtype": "string", "required": False, "coercion": ["trim", "to_upper"],
        "enum_ref": "race.codes", "length": {"max": 1},
    },
    "street_address": {"dtype": "string", "required": False, "coercion": ["trim"]},
    "city": {
        "dtype": "string", "required": False, "coercion": ["trim", "to_upper"],
        "length": {"max": 20},
    },
    "state": {
        "dtype": "string", "required": False, "length": {"min": 2, "max": 2},
        "coercion": ["trim", "to_upper"],
    },
    "zip": {
        "dtype": "string", "required": False,
        # accept 5 or ZIP+4 in canonical; writer will emit 5-digit
        "pattern": r"^\d{5}(-\d{4})?$",
        "length": {"max": 10},
        "coercion": ["trim"],
        "notes": "Writer should emit first 5 digits for fixed-width X(5).",
    },
    "census_tract": {
        "dtype": "string", "required": False, "coercion": ["trim"],
        "length": {"max": 10},
    },
    "migrant_farmer": {
        "dtype": "boolean", "required": False, "coercion": ["to_upper", "trim"],
        "true_values": ["YES", "Y", "TRUE", "1"],
        "false_values": ["NO", "N", "FALSE", "0"],
    },

    # Eligibility & Coverage
    "family_size": {
        "dtype": "integer", "required": False, "bounds": {"min": 0, "max": 50}
    },
    "family_income": {
        # integer per artifact 9(9)
        "dtype": "integer", "required": False, "bounds": {"min": 0, "max": 999_999_999}
    },
    "payor_source": {
        "dtype": "string", "required": False, "coercion": ["trim", "to_upper"],
        "enum_ref": "payor_source.codes", "length": {"min": 2, "max": 2},  # 2-char code
        "warn_if_missing": True,  # Warn if payor source is not provided
    },
    "insurance_name": {
        "dtype": "string", "required": False, "coercion": ["trim"],
        "length": {"max": 35},
    },
    "medicaid_family_care_ever": {
        "dtype": "boolean", "required": False, "coercion": ["to_upper", "trim"],
        "true_values": ["YES", "Y", "TRUE", "1"],
        "false_values": ["NO", "N", "FALSE", "0"],
    },
    "uninsured_family_care_ever": {
        "dtype": "boolean", "required": False, "coercion": ["to_upper", "trim"],
        "true_values": ["YES", "Y", "TRUE", "1"],
        "false_values": ["NO", "N", "FALSE", "0"],
    },

    # Encounter Information
    "record_id": {"dtype": "string", "required": True, "unique": True, "coercion": ["trim"]},
    "visit_date": {
        "dtype": "date", "required": True, "format": "YYYY-MM-DD",
        "coercion": [{"parse_date": ["YYYY-MM-DD", "YYYY/MM/DD", "YYYYMMDD", "MM/DD/YYYY"]}],
        "notes": "Writer must emit YYYYMMDD for fixed-width X(8).",
    },
    "visit_time": {
        "dtype": "time", "required": False, "format": "HH:mm:ss",
        "coercion": [{"parse_time": ["HH:mm:ss", "HH:mm", "H:mm", "HHmm", "HHmmss", "Hmmss"]}],
        "notes": "Writer should emit HH:MM:SS to fill X(8).",
    },
    "invoice_number": {"dtype": "string", "required": False, "coercion": ["trim"]},
    "new_patient": {
        "dtype": "boolean", "required": False, "coercion": ["to_upper", "trim"],
        "true_values": ["YES", "Y", "TRUE", "1"],
        "false_values": ["NO", "N", "FALSE", "0"],
    },
    "visit_type": {
        "dtype": "string", "required": False, "coercion": ["trim", "to_lower"],
        "enum": ["initial", "follow-up"],
        # keep human-friendly in canonical; map to 2-char code on emit
        "code_map": {"initial": "IN", "follow-up": "FU"},
        "notes": "Writer uses code_map to emit X(2).",
    },
    "icd_1": {"dtype": "string", "required": False, "coercion": ["trim", "to_upper"], "ref": "icd10.codes", "length": {"max": 8}},
    "icd_2": {"dtype": "string", "required": False, "coercion": ["trim", "to_upper"], "ref": "icd10.codes", "length": {"max": 8}},
    "icd_3": {"dtype": "string", "required": False, "coercion": ["trim", "to_upper"], "ref": "icd10.codes", "length": {"max": 8}},
    "icd_4": {"dtype": "string", "required": False, "coercion": ["trim", "to_upper"], "ref": "icd10.codes", "length": {"max": 8}},
    "icd_5": {"dtype": "string", "required": False, "coercion": ["trim", "to_upper"], "ref": "icd10.codes", "length": {"max": 8}},
    "total_charges": {
        "dtype": "decimal", "required": False,
        "precision": {"total": 9, "scale": 2},  # fits 9 bytes with 2 implied decimals
        "bounds": {"min": 0, "max": 9_999_999.99},
        "notes": "Writer emits zero-padded 9 digits with cents implied.",
    },
    "total_payment_received": {
        "dtype": "decimal", "required": False,
        "precision": {"total": 9, "scale": 2},
        "bounds": {"min": 0, "max": 9_999_999.99},
        "notes": "Writer emits zero-padded 9 digits with cents implied.",
    },
    "claim_type": {
        "dtype": "string", "required": False, "coercion": ["trim", "to_upper"],
        "enum_ref": "claim_type.codes", "length": {"max": 1},  # single-char code
    },
    "uncompensated_visit": {
        "dtype": "boolean", "required": False, "coercion": ["to_upper", "trim"],
        "true_values": ["YES", "Y", "TRUE", "1"],
        "false_values": ["NO", "N", "FALSE", "0"],
    },
    "location_code": {
        "dtype": "string", "required": False, "coercion": ["trim", "to_upper"],
        "ref": "locations.codes", "length": {"min": 2, "max": 2},  # 2-char code
    },
}

# Putting these as placeholders for now until state codes are located
CODESETS = {
    "gender.codes": ["M", "F", "U"],
    "ethnicity.codes": ["H", "N", "U"],  # Hispanic, Non-Hispanic, Unknown
    "race.codes": ["W", "B", "A", "N", "O", "U"],  # example set
    "payor_source.codes": {
        "MC": "Medicaid",
        "MD": "Medicare",
        "PR": "Private",
        "UN": "Uninsured",
        "OT": "Other",
    },
    "claim_type.codes": {"I": "Inpatient", "O": "Outpatient", "E": "ED", "U": "Unknown"},
    # facility’s real list
    "locations.codes": {"01": "Main", "02": "SatelliteA", "03": "SatelliteB"},
}

# ???
FOREIGN_KEYS = [
    {"field": "location_code", "ref": "locations.codes"},   # from CODESETS above
]

CROSS_FIELD_RULES = [
    # ERRORS - block submission
    {"rule": "total_payment_received <= total_charges", "on_fail": "error"},

    # WARNINGS - flag but allow submission with operator acknowledgment
    {"rule": "visit_date >= date_of_birth", "on_fail": "warn"},
    # Add more as needed
]

PII_FIELDS = [
    "patient_id","last_name","first_name","middle_initial","date_of_birth",
    "street_address","city","state","zip"
]
MASK_RULES = {"default": {"keep_last": 2}}  # e.g., “********ID” leaving last 2 chars

# === NJ Output Layout — single source for all formats ===
# Note: Field 1 "Record ID" in the spec is a 2-char record type code (commonly "01").
# We emit it as a constant via `value`. Canonical `record_id` (your unique key) is NOT in NJ fixed-width,
# but we include it in CSV/Excel/XML for traceability.

OUTPUT_LAYOUT_SPEC = [
    # FieldNo 1 | Ref 1 | Record ID (record type)
    {"field": "record_type", "label": "Record ID", "width": 2, "emitter": "x2",
     "value": "01", "xml_tag": "RecordID", "include_in": ["fixed_width","csv","excel","xml"]},

    # FieldNo 2 | Ref 2 | Patient ID
    {"field": "patient_id", "label": "Patient ID", "width": 12, "emitter": "x",
     "xml_tag": "PatientID", "include_in": ["fixed_width","csv","excel","xml"]},

    # FieldNo 3 | Ref 9 | Visit Date (YYYYMMDD)
    {"field": "visit_date", "label": "Visit Date", "width": 8, "emitter": "date8",
     "xml_tag": "VisitDate", "include_in": ["fixed_width","csv","excel","xml"]},

    # FieldNo 4 | Ref 99 | Visit Time (HH:MM:SS)
    {"field": "visit_time", "label": "Visit Time", "width": 8, "emitter": "time8",
     "xml_tag": "VisitTime", "include_in": ["fixed_width","csv","excel","xml"]},

    # FieldNo 5 | Ref 10 | Invoice Number
    {"field": "invoice_number", "label": "Invoice Number", "width": 20, "emitter": "x",
     "xml_tag": "InvoiceNumber", "include_in": ["fixed_width","csv","excel","xml"]},

    # FieldNo 6 | Ref 11 | New Patient (Y/N)
    {"field": "new_patient", "label": "New Patient", "width": 1, "emitter": "boolYN",
     "xml_tag": "NewPatient", "include_in": ["fixed_width","csv","excel","xml"]},

    # FieldNo 7 | Ref 12 | Patient DOB (YYYYMMDD)
    {"field": "date_of_birth", "label": "Patient DOB", "width": 8, "emitter": "date8",
     "xml_tag": "PatientDOB", "include_in": ["fixed_width","csv","excel","xml"]},

    # FieldNo 8 | Ref 13 | Patient Gender
    {"field": "gender", "label": "Patient Gender", "width": 1, "emitter": "x",
     "xml_tag": "Gender", "include_in": ["fixed_width","csv","excel","xml"]},

    # FieldNo 9 | Ref 14 | Payor Source (2-char code)
    {"field": "payor_source", "label": "Payor Source", "width": 2, "emitter": "x2",
     "xml_tag": "PayorSource", "include_in": ["fixed_width","csv","excel","xml"]},

    # FieldNo 10 | Ref 15 | Insurance Name
    {"field": "insurance_name", "label": "Insurance Name", "width": 35, "emitter": "x",
     "xml_tag": "InsuranceName", "include_in": ["fixed_width","csv","excel","xml"]},

    # FieldNo 11 | Ref 16 | Visit Type (2-char code via schema code_map)
    {"field": "visit_type", "label": "Visit Type", "width": 2, "emitter": "visitType2",
     "xml_tag": "VisitType", "include_in": ["fixed_width","csv","excel","xml"]},

    # FieldNo 12 | Ref 17 | Ethnicity
    {"field": "ethnicity", "label": "Ethnicity", "width": 1, "emitter": "x",
     "xml_tag": "Ethnicity", "include_in": ["fixed_width","csv","excel","xml"]},

    # FieldNo 13 | Ref 18 | Race
    {"field": "race", "label": "Race", "width": 1, "emitter": "x",
     "xml_tag": "Race", "include_in": ["fixed_width","csv","excel","xml"]},

    # FieldNo 14-18 | Ref 19 | ICD_1..ICD_5
    {"field": "icd_1", "label": "ICD 1", "width": 8, "emitter": "x", "xml_tag": "ICD1",
     "include_in": ["fixed_width","csv","excel","xml"]},
    {"field": "icd_2", "label": "ICD 2", "width": 8, "emitter": "x", "xml_tag": "ICD2",
     "include_in": ["fixed_width","csv","excel","xml"]},
    {"field": "icd_3", "label": "ICD 3", "width": 8, "emitter": "x", "xml_tag": "ICD3",
     "include_in": ["fixed_width","csv","excel","xml"]},
    {"field": "icd_4", "label": "ICD 4", "width": 8, "emitter": "x", "xml_tag": "ICD4",
     "include_in": ["fixed_width","csv","excel","xml"]},
    {"field": "icd_5", "label": "ICD 5", "width": 8, "emitter": "x", "xml_tag": "ICD5",
     "include_in": ["fixed_width","csv","excel","xml"]},

    # FieldNo 19 | Ref 20 | Family Size (9(2))
    {"field": "family_size", "label": "Family Size", "width": 2, "emitter": "n",
     "xml_tag": "FamilySize", "include_in": ["fixed_width","csv","excel","xml"]},

    # FieldNo 20 | Ref 21 | Family Income (9(9))
    {"field": "family_income", "label": "Family Income", "width": 9, "emitter": "n",
     "xml_tag": "FamilyIncome", "include_in": ["fixed_width","csv","excel","xml"]},

    # FieldNo 21 | Ref 22 | City
    {"field": "city", "label": "City", "width": 20, "emitter": "x",
     "xml_tag": "City", "include_in": ["fixed_width","csv","excel","xml"]},

    # FieldNo 22 | Ref 23 | Zip (emit first 5)
    {"field": "zip", "label": "ZIP", "width": 5, "emitter": "zip5",
     "xml_tag": "Zip", "include_in": ["fixed_width","csv","excel","xml"]},

    # FieldNo 23 | Ref 24 | Census Tract (spec says “Track”)
    {"field": "census_tract", "label": "Census Tract", "width": 10, "emitter": "x",
     "xml_tag": "CensusTract", "include_in": ["fixed_width","csv","excel","xml"]},

    # FieldNo 24 | Ref 25 | Visit Total Charges (V9(6).99 -> 9 bytes implied 2 decimals)
    {"field": "total_charges", "label": "Visit Total Charges", "width": 9, "emitter": "money9",
     "xml_tag": "VisitTotalCharges", "include_in": ["fixed_width","csv","excel","xml"]},

    # FieldNo 25 | Ref 26 | Total Payment Received (V9(6).99)
    {"field": "total_payment_received", "label": "Total Payment Received", "width": 9, "emitter": "money9",
     "xml_tag": "TotalPaymentReceived", "include_in": ["fixed_width","csv","excel","xml"]},

    # FieldNo 26 | Ref 27 | Claim Type
    {"field": "claim_type", "label": "Claim Type", "width": 1, "emitter": "x",
     "xml_tag": "ClaimType", "include_in": ["fixed_width","csv","excel","xml"]},

    # FieldNo 27 | Ref 28 | Uncompensated Visit (Y/N)
    {"field": "uncompensated_visit", "label": "Uncompensated Visit", "width": 1, "emitter": "boolYN",
     "xml_tag": "UncompensatedVisit", "include_in": ["fixed_width","csv","excel","xml"]},

    # FieldNo 28 | Ref 29 | Location Code (2-char code)
    {"field": "location_code", "label": "Location Code", "width": 2, "emitter": "x2",
     "xml_tag": "LocationCode", "include_in": ["fixed_width","csv","excel","xml"]},

    # FieldNo 29 | Ref 30 | Medicaid Family Care Ever? (Y/N)
    {"field": "medicaid_family_care_ever", "label": "Medicaid Family Care Ever", "width": 1, "emitter": "boolYN",
     "xml_tag": "MedicaidFamilyCareEver", "include_in": ["fixed_width","csv","excel","xml"]},

    # FieldNo 30 | Ref 31 | Uninsured Family Care Ever? (Y/N)
    {"field": "uninsured_family_care_ever", "label": "Uninsured Family Care Ever", "width": 1, "emitter": "boolYN",
     "xml_tag": "UninsuredFamilyCareEver", "include_in": ["fixed_width","csv","excel","xml"]},

    # FieldNo 31 | Ref 32 | Migrant Farmer? (Y/N)
    {"field": "migrant_farmer", "label": "Migrant Farmer", "width": 1, "emitter": "boolYN",
     "xml_tag": "MigrantFarmer", "include_in": ["fixed_width","csv","excel","xml"]},

    # Internal only: include canonical record_id for CSV/Excel/XML so ops can trace rows
    {"field": "record_id", "label": "Canonical Record ID", "width": 36, "emitter": "x",
     "xml_tag": "CanonicalRecordID", "include_in": ["csv","excel","xml"]},
]

# Optional: crosswalk to the "Reference Number" column in Appendix B
REF_MAP = {
    "record_type": "1",
    "patient_id": "2",
    "visit_date": "9",
    "visit_time": "99",
    "invoice_number": "10",
    "new_patient": "11",
    "date_of_birth": "12",
    "gender": "13",
    "payor_source": "14",
    "insurance_name": "15",
    "visit_type": "16",
    "ethnicity": "17",
    "race": "18",
    "icd_1": "19",
    "icd_2": "19",
    "icd_3": "19",
    "icd_4": "19",
    "icd_5": "19",
    "family_size": "20",
    "family_income": "21",
    "city": "22",
    "zip": "23",
    "census_tract": "24",
    "total_charges": "25",
    "total_payment_received": "26",
    "claim_type": "27",
    "uncompensated_visit": "28",
    "location_code": "29",
    "medicaid_family_care_ever": "30",
    "uninsured_family_care_ever": "31",
    "migrant_farmer": "32",
}

def hydrate_layout(spec, ref_map=None):
    """Compute start/end/field_no only for fixed-width fields, keep labels and xml tags."""
    pos, out = 1, []
    for idx, item in enumerate(spec, start=1):
        include = item.get("include_in", ["fixed_width","csv","excel","xml"])
        rec = {**item, "field_no": idx}
        if ref_map and item["field"] in ref_map:
            rec["ref_no"] = ref_map[item["field"]]
        if "fixed_width" in include:
            w = rec["width"]
            rec["start"] = pos
            rec["end"] = pos + w - 1
            pos += w
        out.append(rec)
    record_len = pos - 1  # last byte position
    return out, record_len

# Build hydrated layout and record length constant for the writer
OUTPUT_LAYOUT, RECORD_LENGTH = hydrate_layout(OUTPUT_LAYOUT_SPEC, REF_MAP)

def headers_for(fmt="csv"):
    """CSV/Excel headers: prefer label if present, else field."""
    if fmt not in {"csv","excel"}:
        return []
    return [it.get("label") or it["field"]
            for it in OUTPUT_LAYOUT if fmt in it.get("include_in", [])]

def xml_tag_for(field_name):
    item = next((i for i in OUTPUT_LAYOUT if i["field"] == field_name), None)
    return item.get("xml_tag", field_name) if item else field_name



# emitters
EMITTERS = {
    "x": "left_justify_space_pad",
    "x2": "left_justify_space_pad_fix2",     # enforce exactly 2 chars
    "zip5": "zip_first5_or_blank",
    "n": "right_justify_zero_pad",           # for 9(n)
    "date8": "emit_date_yyyymmdd",
    "time8": "emit_time_hh:mm:ss",
    "money9": "emit_money_9digits_implied2", # 9 bytes, cents implied
    "boolYN": "emit_bool_YN",                # True->Y, False->N, blank->space
    "visitType2": "emit_visit_type_code",    # map from code_map in schema
}

# Validation/error messages
ERRORS = {
    "REQUIRED_MISSING": {"severity": "error", "template": "{field} is required"},
    "INVALID_ENUM":     {"severity": "error", "template": "{field} value '{value}' not in {enum}"},
    "TOO_LONG":         {"severity": "error", "template": "{field} exceeds max length {max}"},
    "BAD_DATE":         {"severity": "error", "template": "{field} not a valid date"},
    "XFIELD_OVERFLOW":  {"severity": "error", "template": "{field} will not fit in {width} bytes"},
    "CROSS_RULE_FAIL":  {"severity": "error", "template": "Rule failed: {rule}"},
    "WARN_DATE_ORDER":  {"severity": "warn",  "template": "{left} is before {right}"},
}

# Control totals
CONTROL_TOTALS = [
    {"name": "row_count", "type": "count", "field": "*"},
    {"name": "sum_total_charges", "type": "sum", "field": "total_charges"},
    {"name": "sum_total_payment_received", "type": "sum", "field": "total_payment_received"},
    {"name": "by_payor_source", "type": "count_by", "field": "payor_source"},
    {"name": "by_claim_type", "type": "count_by", "field": "claim_type"},
]

# changelog
CHANGELOG = [
    {"version": "1.0.1", "date": "2025-09-17", "notes": [
        "Set time_format to HH:mm:ss",
        "family_income to integer 9 digits",
        "Added max lengths to align with fixed-width",
        "Added OUTPUT_LAYOUT and EMITTERS registry",
    ]},
    {"version": "1.0.0", "date": "2025-09-17", "notes": ["Initial canonical schema"]},
]

