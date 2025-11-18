import pandas as pd
from datetime import datetime
from app.schema.nj_schema import SCHEMA_META

empty_values = SCHEMA_META["defaults"]["empty_values"]

def coerce_trim(value):
    if isinstance(value, str):
        trimmed = value.strip()
        if trimmed in empty_values:
            return None
        return trimmed
    return value

def coerce_to_upper(value):
    if isinstance(value, str):
        upper = value.upper()
        return upper
    return value

def coerce_to_lower(value):
    if isinstance(value, str):
        lower = value.lower()
        return lower
    return value

def coerce_parse_date(value, formats):
    if not isinstance(value, str):
        return value
    for fmt in formats:
        try:
            python_fmt = fmt.replace("YYYY", "%Y").replace("MM", "%m").replace("DD", "%d")
            parsed = datetime.strptime(value, python_fmt)
            return parsed.date()
        except ValueError:
            continue
    return None

def coerce_parse_time(value, formats):
    if not isinstance(value, str):
        return value
    for fmt in formats:
        try:
            python_fmt = fmt.replace("HH", "%H").replace("mm", "%M").replace("ss", "%S")
            parsed = datetime.strptime(value, python_fmt)
            return parsed.time()
        except ValueError:
            continue
    return None

def apply_coercions(df, schema):
    df_coerced = df.copy()

    for field_name, field_spec in schema.items():
        if field_name not in df_coerced.columns:
            continue
        coercions = field_spec.get("coercion", [])
    
        for coercion in coercions:
            if coercion == "trim":
                df_coerced[field_name] = df_coerced[field_name].apply(coerce_trim)
            elif coercion == "to_upper":
                df_coerced[field_name] = df_coerced[field_name].apply(coerce_to_upper)
            elif coercion == "to_lower":
                df_coerced[field_name] = df_coerced[field_name].apply(coerce_to_lower)
            elif isinstance(coercion, dict):
                if "parse_date" in coercion:
                    formats = coercion["parse_date"]
                    df_coerced[field_name] = df_coerced[field_name].apply(
                        lambda x: coerce_parse_date(x, formats)
                    )
                elif "parse_time" in coercion:
                        formats = coercion["parse_time"]
                        df_coerced[field_name] = df_coerced[field_name].apply(
                            lambda x: coerce_parse_time(x, formats)
                        )
    return df_coerced
