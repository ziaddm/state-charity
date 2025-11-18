# app/writers/writer.py
"""
Writers for generating state compliance report outputs in multiple formats.
Supports fixed-width, CSV, and Excel formats based on OUTPUT_LAYOUT configuration.
"""
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, date, time
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


# ============================================================================
# EMITTER FUNCTIONS
# ============================================================================
# These functions handle data type conversion and formatting for fixed-width output
# Each emitter takes (value, width) and returns a string of exactly `width` characters

def emit_left_justify_space_pad(value: Any, width: int) -> str:
    """
    Emitter: x - Left-justify and space-pad to width.
    Used for: alphanumeric fields (patient_id, insurance_name, etc.)
    """
    if pd.isna(value) or value is None or value == "":
        return " " * width
    s = str(value).strip()
    if len(s) > width:
        logger.warning(f"Value '{s}' truncated from {len(s)} to {width} chars")
        s = s[:width]
    return s.ljust(width)


def emit_left_justify_space_pad_fix2(value: Any, width: int) -> str:
    """
    Emitter: x2 - Enforce exactly 2 characters, left-justify.
    Used for: 2-char codes (payor_source, location_code, etc.)
    """
    if pd.isna(value) or value is None or value == "":
        return " " * width
    s = str(value).strip()
    if len(s) != width:
        logger.warning(f"2-char field expected but got '{s}' ({len(s)} chars)")
    return s.ljust(width)[:width]


def emit_right_justify_zero_pad(value: Any, width: int) -> str:
    """
    Emitter: n - Right-justify and zero-pad to width.
    Used for: numeric fields like family_size (9(2)), family_income (9(9))
    """
    if pd.isna(value) or value is None or value == "":
        return "0" * width

    # Handle numeric types
    if isinstance(value, (int, float)):
        num_val = int(value)
    else:
        try:
            num_val = int(str(value).strip())
        except (ValueError, AttributeError):
            logger.warning(f"Non-numeric value '{value}' for numeric field, using 0")
            return "0" * width

    s = str(num_val)
    if len(s) > width:
        logger.error(f"Numeric value {num_val} exceeds width {width}")
        return "9" * width  # max representable value
    return s.rjust(width, "0")


def emit_date_yyyymmdd(value: Any, width: int) -> str:
    """
    Emitter: date8 - Format date as YYYYMMDD (8 chars).
    Used for: visit_date, date_of_birth
    Accepts: datetime, date, or string in ISO format
    """
    if pd.isna(value) or value is None or value == "":
        return " " * width

    try:
        # Handle pandas Timestamp
        if isinstance(value, pd.Timestamp):
            dt = value.to_pydatetime().date()
        elif isinstance(value, datetime):
            dt = value.date()
        elif isinstance(value, date):
            dt = value
        elif isinstance(value, str):
            # Try parsing common formats
            dt = pd.to_datetime(value).date()
        else:
            logger.warning(f"Unexpected date type: {type(value)}")
            return " " * width

        return dt.strftime("%Y%m%d")
    except Exception as e:
        logger.warning(f"Failed to format date '{value}': {e}")
        return " " * width


def emit_time_hhmm_ss(value: Any, width: int) -> str:
    """
    Emitter: time8 - Format time as HH:MM:SS (8 chars).
    Used for: visit_time
    Accepts: time object, datetime, or string
    """
    if pd.isna(value) or value is None or value == "":
        return " " * width

    try:
        # Handle pandas Timestamp
        if isinstance(value, pd.Timestamp):
            t = value.to_pydatetime().time()
        elif isinstance(value, datetime):
            t = value.time()
        elif isinstance(value, time):
            t = value
        elif isinstance(value, str):
            # Parse time string
            t = pd.to_datetime(value, format="%H:%M:%S").time()
        else:
            logger.warning(f"Unexpected time type: {type(value)}")
            return " " * width

        return t.strftime("%H:%M:%S")
    except Exception as e:
        logger.warning(f"Failed to format time '{value}': {e}")
        return " " * width


def emit_money_9digits_implied2(value: Any, width: int) -> str:
    """
    Emitter: money9 - Format decimal as 9 digits with 2 implied decimals.
    Used for: total_charges, total_payment_received
    Example: 12345.67 -> "001234567" (9 chars)
    """
    if pd.isna(value) or value is None or value == "":
        return "0" * width

    try:
        # Convert to float then to cents
        amount = float(value)
        cents = int(round(amount * 100))

        if cents < 0:
            logger.warning(f"Negative amount {amount} converted to 0")
            cents = 0

        s = str(cents)
        if len(s) > width:
            logger.error(f"Amount {amount} exceeds {width} digits (cents={cents})")
            return "9" * width  # max value

        return s.rjust(width, "0")
    except Exception as e:
        logger.warning(f"Failed to format money '{value}': {e}")
        return "0" * width


def emit_bool_YN(value: Any, width: int) -> str:
    """
    Emitter: boolYN - Format boolean as Y/N (1 char).
    Used for: new_patient, uncompensated_visit, medicaid_family_care_ever, etc.
    True -> "Y", False -> "N", None/NA -> " "
    """
    if pd.isna(value) or value is None or value == "":
        return " " * width

    # Handle boolean types
    if isinstance(value, bool):
        return "Y" if value else "N"

    # Handle string representations
    val_str = str(value).upper().strip()
    if val_str in ("Y", "YES", "TRUE", "1"):
        return "Y"
    elif val_str in ("N", "NO", "FALSE", "0"):
        return "N"
    else:
        logger.warning(f"Ambiguous boolean value '{value}', treating as blank")
        return " "


def emit_zip_first5_or_blank(value: Any, width: int) -> str:
    """
    Emitter: zip5 - Extract first 5 digits of ZIP code.
    Used for: zip field
    Handles both 5-digit and ZIP+4 formats
    """
    if pd.isna(value) or value is None or value == "":
        return " " * width

    s = str(value).strip()
    # Extract first 5 digits
    digits = "".join(c for c in s if c.isdigit())[:5]
    return digits.ljust(width)


def emit_visit_type_code(value: Any, width: int, code_map: Optional[Dict[str, str]] = None) -> str:
    """
    Emitter: visitType2 - Map visit type to 2-char code.
    Used for: visit_type field
    Canonical stores: "initial" or "follow-up"
    Output requires: "IN" or "FU"
    """
    if pd.isna(value) or value is None or value == "":
        return " " * width

    # Default code map from schema
    if code_map is None:
        code_map = {"initial": "IN", "follow-up": "FU"}

    val_str = str(value).lower().strip()
    code = code_map.get(val_str, "")

    if not code:
        logger.warning(f"Unknown visit type '{value}', using blank")
        return " " * width

    return code.ljust(width)[:width]


# Emitter registry - maps emitter names to functions
EMITTER_REGISTRY = {
    "x": emit_left_justify_space_pad,
    "x2": emit_left_justify_space_pad_fix2,
    "n": emit_right_justify_zero_pad,
    "date8": emit_date_yyyymmdd,
    "time8": emit_time_hhmm_ss,
    "money9": emit_money_9digits_implied2,
    "boolYN": emit_bool_YN,
    "zip5": emit_zip_first5_or_blank,
    "visitType2": emit_visit_type_code,
}


# ============================================================================
# VECTORIZED EMITTERS (for performance)
# ============================================================================

def vectorized_emit_x(series: pd.Series, width: int) -> pd.Series:
    """Vectorized left-justify space-pad."""
    return series.fillna("").astype(str).str.strip().str[:width].str.ljust(width)


def vectorized_emit_x2(series: pd.Series, width: int) -> pd.Series:
    """Vectorized 2-char code."""
    return series.fillna("").astype(str).str.strip().str[:width].str.ljust(width)


def vectorized_emit_n(series: pd.Series, width: int) -> pd.Series:
    """Vectorized right-justify zero-pad."""
    result = series.fillna(0).astype(int).astype(str).str.zfill(width)
    # Handle values that exceed width
    mask = result.str.len() > width
    result[mask] = "9" * width
    return result


def vectorized_emit_date8(series: pd.Series, width: int) -> pd.Series:
    """Vectorized date formatting to YYYYMMDD."""
    return pd.to_datetime(series, errors='coerce').dt.strftime('%Y%m%d').fillna(" " * width)


def vectorized_emit_time8(series: pd.Series, width: int) -> pd.Series:
    """Vectorized time formatting to HH:MM:SS."""
    # Handle time strings - already in HH:MM:SS format in most cases
    def format_time(val):
        if pd.isna(val) or val == "":
            return " " * width
        s = str(val).strip()
        if len(s) >= 8:
            return s[:8]
        return s.ljust(width)
    return series.apply(format_time)


def vectorized_emit_money9(series: pd.Series, width: int) -> pd.Series:
    """Vectorized money formatting with implied 2 decimals."""
    cents = (series.fillna(0).astype(float) * 100).round().astype(int)
    cents = cents.clip(lower=0)  # No negatives
    result = cents.astype(str).str.zfill(width)
    # Handle overflow
    mask = result.str.len() > width
    result[mask] = "9" * width
    return result


def vectorized_emit_boolYN(series: pd.Series, width: int) -> pd.Series:
    """Vectorized boolean to Y/N."""
    # Convert to string, handle various boolean representations
    s = series.fillna("").astype(str).str.upper().str.strip()
    result = s.replace({
        "TRUE": "Y", "FALSE": "N",
        "YES": "Y", "NO": "N",
        "Y": "Y", "N": "N",
        "1": "Y", "0": "N",
        "": " "
    })
    # Anything not matched becomes space
    mask = ~result.isin(["Y", "N", " "])
    result[mask] = " "
    return result


def vectorized_emit_zip5(series: pd.Series, width: int) -> pd.Series:
    """Vectorized ZIP first 5 digits."""
    # Extract first 5 digits
    result = series.fillna("").astype(str).str.extract('(\d{5})', expand=False).fillna("").str.ljust(width)
    return result


def vectorized_emit_visit_type(series: pd.Series, width: int, code_map: Dict[str, str] = None) -> pd.Series:
    """Vectorized visit type code mapping."""
    if code_map is None:
        code_map = {"initial": "IN", "follow-up": "FU"}
    s = series.fillna("").astype(str).str.lower().str.strip()
    result = s.replace(code_map).fillna("").str.ljust(width)
    return result


VECTORIZED_EMITTERS = {
    "x": vectorized_emit_x,
    "x2": vectorized_emit_x2,
    "n": vectorized_emit_n,
    "date8": vectorized_emit_date8,
    "time8": vectorized_emit_time8,
    "money9": vectorized_emit_money9,
    "boolYN": vectorized_emit_boolYN,
    "zip5": vectorized_emit_zip5,
    "visitType2": vectorized_emit_visit_type,
}


# ============================================================================
# WRITER CLASSES
# ============================================================================

class FixedWidthWriter:
    """
    Writes canonical DataFrame to fixed-width format per state specification.
    """

    def __init__(self, layout: List[Dict[str, Any]], record_length: int):
        """
        Initialize writer with output layout specification.

        Args:
            layout: List of field specifications from OUTPUT_LAYOUT
            record_length: Expected fixed-width record length in bytes
        """
        self.layout = layout
        self.record_length = record_length
        self.fixed_width_fields = [
            f for f in layout if "fixed_width" in f.get("include_in", [])
        ]

    def write(self, df: pd.DataFrame, output_path: Path) -> Dict[str, Any]:
        """
        Write DataFrame to fixed-width text file using vectorized operations.

        Args:
            df: Canonical DataFrame to write
            output_path: Path to output file

        Returns:
            Dict with metadata (record_count, bytes_written, etc.)
        """
        logger.info(f"Writing {len(df)} records to fixed-width file: {output_path}")

        # Build all formatted columns as a list using vectorized operations
        formatted_columns = []

        for field_spec in self.fixed_width_fields:
            field_name = field_spec["field"]
            width = field_spec["width"]
            emitter_name = field_spec["emitter"]

            # Get column values or use constant
            if "value" in field_spec:
                # Constant value for all rows - create as numpy array for speed
                col_data = pd.Series([field_spec["value"]] * len(df), dtype=str)
            elif field_name in df.columns:
                col_data = df[field_name].copy()
            else:
                logger.warning(f"Field '{field_name}' not found in data, using blanks")
                col_data = pd.Series([""] * len(df), dtype=str)

            # Apply vectorized emitter function
            vec_emitter = VECTORIZED_EMITTERS.get(emitter_name)
            if not vec_emitter:
                logger.error(f"Unknown emitter '{emitter_name}' for field '{field_name}'")
                formatted_col = pd.Series([" " * width] * len(df), dtype=str)
            else:
                # Use vectorized emitter
                if emitter_name == "visitType2":
                    from app.schema.nj_schema import CANONICAL_VISITS_SCHEMA
                    code_map = CANONICAL_VISITS_SCHEMA.get("visit_type", {}).get("code_map")
                    formatted_col = vec_emitter(col_data, width, code_map)
                else:
                    formatted_col = vec_emitter(col_data, width)

            formatted_columns.append(formatted_col)

        # Concatenate all columns horizontally - much faster with str.cat
        all_lines = formatted_columns[0]
        for col in formatted_columns[1:]:
            all_lines = all_lines.str.cat(col)

        # Validate record length on first record only (for speed)
        if len(all_lines) > 0:
            first_line_len = len(all_lines.iloc[0])
            if first_line_len != self.record_length:
                logger.error(
                    f"Record length mismatch: Expected {self.record_length} chars, got {first_line_len}"
                )

        # Write all lines at once
        with open(output_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(all_lines) + "\n")

        records_written = len(all_lines)
        bytes_written = (self.record_length * records_written) + records_written  # data + newlines

        logger.info(
            f"Fixed-width write complete: {records_written} records, {bytes_written} bytes"
        )

        return {
            "format": "fixed_width",
            "records_written": records_written,
            "bytes_written": bytes_written,
            "record_length": self.record_length,
            "output_path": str(output_path),
        }



class CSVWriter:
    """
    Writes canonical DataFrame to CSV format.
    """

    def __init__(self, layout: List[Dict[str, Any]]):
        """
        Initialize CSV writer with layout specification.

        Args:
            layout: List of field specifications from OUTPUT_LAYOUT
        """
        self.layout = layout
        self.csv_fields = [
            f for f in layout if "csv" in f.get("include_in", [])
        ]

    def write(self, df: pd.DataFrame, output_path: Path) -> Dict[str, Any]:
        """
        Write DataFrame to CSV file.

        Args:
            df: Canonical DataFrame to write
            output_path: Path to output CSV file

        Returns:
            Dict with metadata
        """
        logger.info(f"Writing {len(df)} records to CSV file: {output_path}")

        # Build output DataFrame with proper column order and labels
        output_data = {}

        for field_spec in self.csv_fields:
            field_name = field_spec["field"]
            label = field_spec.get("label", field_name)

            # Get column data or use constant value
            if "value" in field_spec:
                output_data[label] = [field_spec["value"]] * len(df)
            elif field_name in df.columns:
                output_data[label] = df[field_name]
            else:
                logger.warning(f"Field '{field_name}' not found in data, using blank")
                output_data[label] = [""] * len(df)

        output_df = pd.DataFrame(output_data)
        output_df.to_csv(output_path, index=False, encoding="utf-8")

        logger.info(f"CSV write complete: {len(output_df)} records, {len(output_df.columns)} columns")

        return {
            "format": "csv",
            "records_written": len(output_df),
            "columns": len(output_df.columns),
            "output_path": str(output_path),
        }


class ExcelWriter:
    """
    Writes canonical DataFrame to Excel format.
    """

    def __init__(self, layout: List[Dict[str, Any]]):
        """
        Initialize Excel writer with layout specification.

        Args:
            layout: List of field specifications from OUTPUT_LAYOUT
        """
        self.layout = layout
        self.excel_fields = [
            f for f in layout if "excel" in f.get("include_in", [])
        ]

    def write(self, df: pd.DataFrame, output_path: Path) -> Dict[str, Any]:
        """
        Write DataFrame to Excel file.

        Args:
            df: Canonical DataFrame to write
            output_path: Path to output Excel file

        Returns:
            Dict with metadata
        """
        logger.info(f"Writing {len(df)} records to Excel file: {output_path}")

        # Build output DataFrame with proper column order and labels
        output_data = {}

        for field_spec in self.excel_fields:
            field_name = field_spec["field"]
            label = field_spec.get("label", field_name)

            # Get column data or use constant value
            if "value" in field_spec:
                output_data[label] = [field_spec["value"]] * len(df)
            elif field_name in df.columns:
                output_data[label] = df[field_name]
            else:
                logger.warning(f"Field '{field_name}' not found in data, using blank")
                output_data[label] = [""] * len(df)

        output_df = pd.DataFrame(output_data)

        # Write to Excel with formatting
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            output_df.to_excel(writer, sheet_name="Submission Data", index=False)

            # Auto-adjust column widths
            worksheet = writer.sheets["Submission Data"]
            for idx, col in enumerate(output_df.columns, 1):
                max_length = max(
                    output_df[col].astype(str).map(len).max(),
                    len(str(col))
                )
                worksheet.column_dimensions[chr(64 + idx)].width = min(max_length + 2, 50)

        logger.info(f"Excel write complete: {len(output_df)} records, {len(output_df.columns)} columns")

        return {
            "format": "excel",
            "records_written": len(output_df),
            "columns": len(output_df.columns),
            "output_path": str(output_path),
        }


# ============================================================================
# PUBLIC API
# ============================================================================

def write_fixed_width(
    df: pd.DataFrame,
    output_path: Path,
    state_code: str = "NJ"
) -> Dict[str, Any]:
    """
    Write canonical DataFrame to fixed-width format for state submission.

    Args:
        df: Canonical DataFrame to write
        output_path: Path to output file
        state_code: State code (default: "NJ")

    Returns:
        Dict with write metadata
    """
    # Import schema for the state
    if state_code == "NJ":
        from app.schema.nj_schema import OUTPUT_LAYOUT, RECORD_LENGTH
    else:
        raise ValueError(f"Unsupported state code: {state_code}")

    writer = FixedWidthWriter(OUTPUT_LAYOUT, RECORD_LENGTH)
    return writer.write(df, output_path)


def write_csv(
    df: pd.DataFrame,
    output_path: Path,
    state_code: str = "NJ"
) -> Dict[str, Any]:
    """
    Write canonical DataFrame to CSV format.

    Args:
        df: Canonical DataFrame to write
        output_path: Path to output file
        state_code: State code (default: "NJ")

    Returns:
        Dict with write metadata
    """
    if state_code == "NJ":
        from app.schema.nj_schema import OUTPUT_LAYOUT
    else:
        raise ValueError(f"Unsupported state code: {state_code}")

    writer = CSVWriter(OUTPUT_LAYOUT)
    return writer.write(df, output_path)


def write_excel(
    df: pd.DataFrame,
    output_path: Path,
    state_code: str = "NJ"
) -> Dict[str, Any]:
    """
    Write canonical DataFrame to Excel format.

    Args:
        df: Canonical DataFrame to write
        output_path: Path to output file
        state_code: State code (default: "NJ")

    Returns:
        Dict with write metadata
    """
    if state_code == "NJ":
        from app.schema.nj_schema import OUTPUT_LAYOUT
    else:
        raise ValueError(f"Unsupported state code: {state_code}")

    writer = ExcelWriter(OUTPUT_LAYOUT)
    return writer.write(df, output_path)
