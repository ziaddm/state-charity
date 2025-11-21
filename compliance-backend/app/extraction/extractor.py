"""
Data Extraction Module
======================

This module handles the first step of the compliance reporting pipeline: extracting
tenant data from various file formats into a standardized pandas DataFrame.

Purpose:
    - Accept tenant files in multiple formats (CSV, TSV, Excel)
    - Auto-detect format and encoding
    - Normalize column headers to a standard format
    - Add row tracking for validation error reporting
    - Return clean DataFrame + metadata for downstream processing

Key Features:
    - Multi-format support: CSV, TSV, Excel (.xlsx, .xls)
    - Auto-encoding detection: tries UTF-8, UTF-8-BOM, CP1252, Latin-1
    - CSV delimiter sniffing: auto-detects comma, tab, semicolon, pipe
    - Header normalization: "Patient MRN" → "patient_mrn"
    - Empty row removal: filters out blank rows
    - Row number tracking: adds __rownum column for error reporting

Design Philosophy:
    - Be lenient with input formats (healthcare data is messy)
    - Fail fast if file is truly unreadable
    - Preserve all data as strings (type coercion happens later)
    - Provide detailed metadata for audit trail

Example Usage:
    >>> from app.extraction.extractor import load_source
    >>> df, meta = load_source("tenant_data.csv")
    >>> print(f"Loaded {meta['n_rows']} rows, {meta['n_cols']} columns")
    >>> print(f"Encoding: {meta['encoding']}, Format: {meta['fmt']}")
"""

import pandas as pd
from pathlib import Path
import csv

# ============================================================================
# CONSTANTS
# ============================================================================
# Supported file formats - these are the file extensions we can handle
SUPPORTED = {"csv", "tsv", "txt", "xlsx", "xls"}


# ============================================================================
# MAIN EXTRACTION FUNCTION
# ============================================================================
def load_source(path, fmt='auto', sheet=None, delimiter=None, encoding='auto', max_rows=None):
    """
    Load a tenant data file into a normalized pandas DataFrame.

    This is the main entry point for data extraction. It handles multiple file formats,
    auto-detects encoding, normalizes headers, and returns both the data and metadata.

    Args:
        path (str|Path): Path to the source file
        fmt (str): File format - 'auto', 'csv', 'tsv', or 'xlsx'
                   Default 'auto' detects from file extension
        sheet (str|int): Excel sheet name or index (0-based). None = first sheet
        delimiter (str): CSV delimiter. None = auto-detect
        encoding (str): File encoding. 'auto' tries common encodings
        max_rows (int): Maximum rows to read. None = read all rows

    Returns:
        tuple: (df, metadata)
            - df: pandas DataFrame with normalized headers and __rownum column
            - metadata: dict with source path, format, encoding, row/col counts, etc.

    Raises:
        ValueError: If format is unsupported or cannot be auto-detected
        UnicodeError: If file cannot be decoded with any tried encoding
        FileNotFoundError: If path doesn't exist

    Example:
        >>> df, meta = load_source("data.csv")
        >>> print(df.columns)  # ['__rownum', 'patient_id', 'visit_date', ...]
        >>> print(meta['encoding'])  # 'utf-8'
        >>> print(meta['n_rows'])  # 1000
    """
    # Convert string path to Path object for easier manipulation
    p = Path(path)

    # ========================================================================
    # STEP 1: Detect file format from extension (if fmt='auto')
    # ========================================================================
    if fmt == "auto":
        # Get file extension (e.g., "data.csv" → "csv")
        ext = p.suffix.lower().lstrip(".")  # Remove leading dot

        # Map extension to format
        if ext in {"tsv"}:
            fmt = "tsv"  # Tab-separated values
        elif ext in {"csv", "txt"}:
            fmt = "csv"  # Comma-separated (or sniff delimiter)
        elif ext in {"xlsx", "xls"}:
            fmt = "xlsx"  # Excel format
        else:
            raise ValueError(f"Cannot auto-detect format from extension {ext}")

    # Validate format is supported
    if fmt not in {"csv", "tsv", "xlsx"}:
        raise ValueError(f"Unsupported format: {fmt}")

    # Track which encoding was successfully used
    enc_used = None

    # ========================================================================
    # STEP 2: Load data based on format
    # ========================================================================

    if fmt in {"csv", "tsv"}:
        # ====================================================================
        # CSV/TSV LOADING
        # ====================================================================

        # Determine delimiter
        # - If delimiter provided explicitly, use it
        # - TSV always uses tab
        # - CSV sniffs the delimiter from file content
        delim = delimiter or ("\t" if fmt == "tsv" else sniff_delimiter(p))

        # Try multiple encodings until one works
        # Healthcare data often has weird encodings from different EHR systems
        encodings_to_try = (
            ["utf-8", "utf-8-sig", "cp1252", "latin-1"]  # Common encodings
            if encoding == "auto"
            else [encoding]  # User specified encoding
        )

        for enc in encodings_to_try:
            try:
                # Load CSV with pandas
                df = pd.read_csv(
                    p,
                    dtype=str,              # Force all columns to string (prevent auto-type inference)
                    keep_default_na=False,  # Don't convert "NA" to NaN
                    na_filter=False,        # Don't interpret any value as missing
                    sep=delim,              # Use detected/specified delimiter
                    nrows=max_rows,         # Limit rows if specified (for testing)
                    encoding=enc,           # Try this encoding
                    engine="python"         # Python engine handles more edge cases than C engine
                )
                enc_used = enc  # Success! Remember which encoding worked
                break  # Exit the loop - we successfully loaded the file
            except Exception:
                # This encoding didn't work, try the next one
                continue

        # If we tried all encodings and none worked, fail
        if enc_used is None:
            raise UnicodeError("Could not read file with tried encodings")

    else:
        # ====================================================================
        # EXCEL LOADING
        # ====================================================================
        df = pd.read_excel(
            p,
            sheet_name=sheet,  # Which sheet to read (None = first sheet)
            dtype=object,      # Force all columns to object type (like string)
            nrows=max_rows     # Limit rows if specified
        )

        # Excel reads NaN for empty cells - convert to empty strings
        # applymap applies a function to every cell in the DataFrame
        df = df.applymap(lambda x: "" if pd.isna(x) else str(x))

        enc_used = "binary-excel"  # Excel is binary format, not text

    # ========================================================================
    # STEP 3: Normalize column headers
    # ========================================================================
    # Healthcare files have inconsistent headers:
    #   "Patient MRN", "patient_mrn", "PATIENT-MRN", etc.
    # We normalize to: lowercase_with_underscores
    #
    # Example: "Patient MRN" → "patient_mrn"
    #          "Date of Birth" → "date_of_birth"
    header_map = normalize_headers(df.columns.tolist())
    df.columns = [header_map[c] for c in df.columns]

    # ========================================================================
    # STEP 4: Remove empty rows
    # ========================================================================
    # Healthcare exports often have trailing empty rows
    # Filter out rows where ALL cells are empty strings
    df = df[~(df.eq("").all(axis=1))].copy()

    # ========================================================================
    # STEP 5: Add source row number column
    # ========================================================================
    # Add __rownum as the FIRST column (position 0)
    # This allows validation errors to report: "Error in row 42"
    # Row numbers are 1-based (like Excel) for operator familiarity
    df.insert(0, "__rownum", range(1, len(df) + 1))

    # ========================================================================
    # STEP 6: Build metadata dict
    # ========================================================================
    # Return detailed metadata for audit trail and debugging
    meta = {
        "source_path": str(p),                       # Full file path
        "fmt": fmt,                                  # Detected format (csv, tsv, xlsx)
        "sheet": sheet if fmt == "xlsx" else None,   # Excel sheet name (if applicable)
        "encoding": enc_used,                        # Encoding used to read file
        "delimiter": delim if fmt in {"csv","tsv"} else None,  # CSV delimiter
        "n_rows": int(df.shape[0]),                  # Number of data rows (after empty row removal)
        "n_cols": int(df.shape[1]),                  # Number of columns (including __rownum)
        "header_original": list(header_map.keys()),  # Original headers from file
        "header_normalized": list(header_map.values()),  # Normalized headers
        "header_map": header_map,                    # Full mapping dict
    }

    return df, meta


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def sniff_delimiter(path, sample_bytes=16384):
    """
    Auto-detect the delimiter used in a CSV file.

    This function reads the first 16KB of the file and uses Python's csv.Sniffer
    to detect whether the file uses commas, semicolons, pipes, or tabs as delimiters.

    Why this matters:
        Different EHR systems export with different delimiters:
        - Epic: usually comma (,)
        - Some European systems: semicolon (;)
        - Legacy systems: pipe (|) or tab (\t)

    Args:
        path (Path): Path to the CSV file
        sample_bytes (int): Number of bytes to read for sniffing (default 16KB)

    Returns:
        str: Detected delimiter character (',', ';', '|', or '\t')
             Falls back to ',' if detection fails

    Example:
        >>> delimiter = sniff_delimiter(Path("data.csv"))
        >>> print(delimiter)  # ','
    """
    # Read the first 16KB of the file
    # We only need a sample - full file read would be slow for large files
    with open(path, "rb") as f:
        head = f.read(sample_bytes).decode("utf-8", errors="ignore")

    try:
        # Use Python's csv.Sniffer to detect delimiter
        # Sniffer looks at the structure and guesses which delimiter makes sense
        # We limit to common delimiters to avoid false positives
        dialect = csv.Sniffer().sniff(head, delimiters=[",", ";", "|", "\t"])
        return dialect.delimiter
    except Exception:
        # If sniffing fails (e.g., file has weird structure), default to comma
        # Comma is most common, so it's a safe fallback
        return ","


def normalize_headers(cols):
    """
    Normalize column headers to a standard format: lowercase_with_underscores.

    This function converts messy, inconsistent column headers into a clean, standardized
    format that's easier to work with programmatically.

    Transformations applied:
        1. Strip leading/trailing whitespace
        2. Collapse multiple spaces into single spaces
        3. Replace special characters with underscores
        4. Replace spaces with underscores
        5. Convert to lowercase
        6. Remove leading/trailing underscores
        7. Handle duplicates by appending _2, _3, etc.

    Examples:
        "Patient MRN"           → "patient_mrn"
        "Date of Birth"         → "date_of_birth"
        "PATIENT-ID"            → "patient_id"
        "  First Name  "        → "first_name"
        "Total $ Charges"       → "total_charges"
        "" (empty)              → "col"
        "Name" (duplicate)      → "name_2"

    Args:
        cols (list): List of original column names from file

    Returns:
        dict: Mapping of {original_name: normalized_name}

    Example:
        >>> headers = ["Patient MRN", "Date of Birth", "Total $ Charges"]
        >>> normalized = normalize_headers(headers)
        >>> print(normalized)
        # {'Patient MRN': 'patient_mrn',
        #  'Date of Birth': 'date_of_birth',
        #  'Total $ Charges': 'total_charges'}
    """
    out = {}  # Final mapping: {original: normalized}
    used = set()  # Track which normalized names are already taken (avoid duplicates)

    for c in cols:
        # STEP 1: Convert to string and strip whitespace
        s = str(c).strip()

        # STEP 2: Collapse multiple spaces into single spaces
        # "First    Name" → "First Name"
        s = " ".join(s.split())

        # STEP 3: Replace special characters with underscores
        # "Total $ Charges" → "Total _ Charges"
        # Keep only alphanumeric characters and spaces
        s = "".join(ch if ch.isalnum() or ch == " " else "_" for ch in s)

        # STEP 4: Replace spaces with underscores
        # "Total _ Charges" → "Total__Charges"
        s = s.replace(" ", "_")

        # STEP 5: Convert to lowercase
        # "Total__Charges" → "total__charges"
        s = s.lower()

        # STEP 6: Strip leading/trailing underscores
        # "total__charges" → "total_charges" (consecutive underscores preserved for now)
        s = s.strip("_")

        # STEP 7: Handle empty column names
        # If column name was empty or only special characters, use "col" as base
        base = s or "col"
        name = base

        # STEP 8: Handle duplicate names by appending _2, _3, etc.
        # If "patient_id" already exists, use "patient_id_2"
        i = 2
        while name in used:
            name = f"{base}_{i}"
            i += 1

        # Store the mapping and mark this normalized name as used
        out[c] = name
        used.add(name)

    return out