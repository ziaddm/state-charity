# app/mapping/mapper.py

import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class MappingError(Exception):
    pass


# ---------------------------------------------------------------------------
# Column-name normalisation (must match extractor.normalize_headers exactly)
# ---------------------------------------------------------------------------
def _norm(col_name: str) -> str:
    """Normalise a source column name the same way the extractor does."""
    s = str(col_name).strip()
    s = " ".join(s.split())
    s = "".join(ch if ch.isalnum() or ch == " " else "_" for ch in s)
    s = s.replace(" ", "_")
    s = s.lower()
    s = s.strip("_")
    return s or "col"


class TenantMapper:

    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        if not self.config_path.exists():
            raise FileNotFoundError(f"Mapping config not found: {config_path}")

        logger.debug(f"Loading tenant config: {config_path}")
        with open(self.config_path) as f:
            self.config = yaml.safe_load(f)

        self.validate_config()

        # field_map is kept for the pre_validator (column-presence checks only)
        self.field_map = self._build_field_map()
        self.reverse_map = {v: k for k, v in self.field_map.items()}

        self.tenant_id = self.config.get("tenant_id")
        self.tenant_name = self.config.get("tenant_name", "Unknown")
        self.constants = self.config.get("constants", {})

        # These are read by the pipeline but handled internally now:
        self.transforms = self.config.get("transforms", [])
        self.value_maps = self._extract_value_maps()
        self.field_transforms = self._extract_field_transforms()

    # ------------------------------------------------------------------
    # Config validation
    # ------------------------------------------------------------------
    def validate_config(self):
        required = ["tenant_id", "field_mappings"]
        missing = [k for k in required if k not in self.config]
        if missing:
            raise MappingError(f"Config missing required keys: {missing}")
        logger.info(f"Config validated for tenant: {self.config.get('tenant_id')}")

    # ------------------------------------------------------------------
    # Build field_map for pre_validator (source_col → canonical, last-wins)
    # ------------------------------------------------------------------
    def _build_field_map(self) -> Dict[str, str]:
        mappings = self.config["field_mappings"]
        field_map = {}
        for canonical_field, tenant_config in mappings.items():
            if isinstance(tenant_config, str):
                field_map[_norm(tenant_config)] = canonical_field
            elif isinstance(tenant_config, dict):
                source = tenant_config.get("source")
                if source:
                    field_map[_norm(source)] = canonical_field
        logger.debug(f"Built field_map with {len(field_map)} entries")
        return field_map

    # Keep original names for backward compat
    def build_field_map(self) -> Dict[str, str]:
        return self._build_field_map()

    def _extract_value_maps(self) -> Dict[str, Dict[str, str]]:
        value_maps = {}
        for canonical_field, cfg in self.config.get("field_mappings", {}).items():
            if isinstance(cfg, dict) and "value_map" in cfg:
                value_maps[canonical_field] = cfg["value_map"]
        return value_maps

    def _extract_field_transforms(self) -> Dict[str, str]:
        field_transforms = {}
        for canonical_field, cfg in self.config.get("field_mappings", {}).items():
            if isinstance(cfg, dict) and "transform" in cfg:
                field_transforms[canonical_field] = cfg["transform"]
        return field_transforms

    def extract_value_maps(self):
        return self._extract_value_maps()

    def extract_field_transforms(self):
        return self._extract_field_transforms()

    # ------------------------------------------------------------------
    # Named transform implementations
    # ------------------------------------------------------------------
    def _apply_named_transform(self, series: pd.Series, transform_name: str) -> pd.Series:
        """Apply a named transform to a Series. Returns the transformed Series."""

        if transform_name == "split_last_name":
            return series.apply(
                lambda x: str(x).split(",")[0].strip()
                if pd.notna(x) and "," in str(x) else x
            )

        elif transform_name == "split_first_name":
            def _first(x):
                if pd.isna(x):
                    return x
                parts = str(x).split(",")
                return parts[1].strip() if len(parts) > 1 else ""
            return series.apply(_first)

        elif transform_name == "clean_gender":
            # Remove " [ Male ]" style bracketed duplicates
            return series.apply(
                lambda x: re.sub(r'\s*\[.*?\]', '', str(x)).strip()
                if pd.notna(x) else x
            )

        elif transform_name == "clean_zip":
            # Extract first 5 digits, handling "07060 USA" and "07063-1652 USA"
            def _zip(x):
                if pd.isna(x) or str(x).strip() == "":
                    return x
                m = re.search(r'(\d{5})', str(x))
                return m.group(1) if m else ""
            return series.apply(_zip)

        elif transform_name == "clean_multi_value_first":
            return series.apply(
                lambda x: str(x).split(",")[0].strip() if pd.notna(x) else x
            )

        elif transform_name == "map_payer_to_code":
            # value_map is applied separately — nothing extra needed here
            return series

        else:
            logger.warning(f"Unknown named transform: '{transform_name}' — skipping")
            return series

    # ------------------------------------------------------------------
    # Core mapping: iterate field_mappings directly to avoid overwrite bug
    # when multiple canonical fields share the same source column
    # ------------------------------------------------------------------
    def map_dataframe(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[Dict]]:
        logger.info(f"Mapping dataframe: {len(df)} rows, {len(df.columns)} columns")
        warnings = []
        mapped_data: Dict[str, pd.Series] = {}
        used_cols: set = set()

        mappings = self.config["field_mappings"]

        for canonical_field, tenant_config in mappings.items():
            if isinstance(tenant_config, str):
                source = tenant_config
                transform_name = None
                value_map = None
            elif isinstance(tenant_config, dict):
                source = tenant_config.get("source", "")
                transform_name = tenant_config.get("transform")
                value_map = tenant_config.get("value_map")
            else:
                continue

            tenant_col = _norm(source) if source else ""

            if tenant_col and tenant_col in df.columns:
                col_data = df[tenant_col].copy()

                # Normalise empty-string-like values to None
                col_data = col_data.replace("", None)
                col_data = col_data.replace(r"^\s*$", None, regex=True)

                # Apply named transform (e.g. split_last_name, clean_zip)
                if transform_name:
                    col_data = self._apply_named_transform(col_data, transform_name)

                # Apply value_map; "*" key acts as catch-all for unmapped values
                if value_map:
                    catchall = value_map.get("*")
                    col_data = col_data.map(
                        lambda x, vm=value_map, ca=catchall: (
                            vm.get(x, ca if ca is not None else x)
                        ) if pd.notna(x) else x
                    )

                mapped_data[canonical_field] = col_data
                used_cols.add(tenant_col)

            else:
                # Fall back to constant if defined
                if canonical_field in self.constants:
                    const_val = self.constants[canonical_field]
                    mapped_data[canonical_field] = pd.Series(
                        [const_val] * len(df), dtype=object
                    )
                    logger.debug(f"Constant for {canonical_field}: {repr(const_val)}")
                else:
                    warnings.append({
                        "code": "W603",
                        "severity": "warning",
                        "type": "missing_source_column",
                        "field": canonical_field,
                        "row": "All",
                        "message": (
                            f"Missing column '{source}' — cannot populate '{canonical_field}'. "
                            f"Add this column to your CSV file."
                        ),
                        "action": f"Add '{source}' column to input file",
                    })

        # Add constant fields not covered by any field_mapping entry
        for canonical_field, const_val in self.constants.items():
            if canonical_field not in mapped_data:
                mapped_data[canonical_field] = pd.Series(
                    [const_val] * len(df), dtype=object
                )
                logger.debug(f"Added constant field {canonical_field}")

        # Warn about unmapped tenant columns
        actual_cols = set(df.columns) - {"__rownum"}
        for col in actual_cols - used_cols:
            warnings.append({
                "code": "I003",
                "severity": "info",
                "type": "unmapped_tenant_column",
                "field": col,
                "row": "All",
                "message": (
                    f"Extra column '{col}' in your file will be ignored "
                    f"(not needed for submission)"
                ),
                "action": "No action needed — column will be skipped",
            })

        # Preserve __rownum
        if "__rownum" in df.columns:
            mapped_data["__rownum"] = df["__rownum"]

        mapped_df = pd.DataFrame(mapped_data)
        logger.info(
            f"Mapping complete: {len(mapped_df.columns)} canonical fields, "
            f"{len(warnings)} warnings"
        )
        return mapped_df, warnings

    # ------------------------------------------------------------------
    # Global transforms: applied to canonical DataFrame after mapping,
    # before schema coercions
    # ------------------------------------------------------------------
    def apply_global_transforms(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply the YAML 'transforms' list to the canonical DataFrame."""
        transforms = self.config.get("transforms", [])
        if not transforms:
            return df

        df = df.copy()

        for transform in transforms:
            field = transform.get("field", "")
            t_type = transform.get("type", "")

            # Determine target columns
            if field == "*":
                target_cols = [c for c in df.columns if c != "__rownum"]
            elif field in df.columns:
                target_cols = [field]
            else:
                continue  # field not present — skip silently

            for col in target_cols:
                try:
                    if t_type == "strip":
                        df[col] = df[col].apply(
                            lambda x: str(x).strip()
                            if pd.notna(x) and str(x).strip() != "" else x
                        )

                    elif t_type == "regex_replace":
                        pattern = transform.get("pattern", "")
                        replacement = transform.get("replacement", "")
                        def _regex_replace(x, p=pattern, r=replacement):
                            if pd.isna(x) or str(x).strip() == "":
                                return x
                            return re.sub(p, r, str(x)).strip()
                        df[col] = df[col].apply(_regex_replace)

                    elif t_type == "regex_extract":
                        pattern = transform.get("pattern", "")
                        default = transform.get("default", "")
                        def _regex_extract(x, p=pattern, d=default):
                            if pd.isna(x) or str(x).strip() == "":
                                return x
                            m = re.search(p, str(x))
                            return m.group(1) if m else d
                        df[col] = df[col].apply(_regex_extract)

                    elif t_type == "split":
                        delimiter = transform.get("delimiter", ",")
                        index = transform.get("index", 0)
                        do_strip = transform.get("strip", True)
                        def _split(x, d=delimiter, i=index, s=do_strip):
                            if pd.isna(x) or str(x).strip() == "":
                                return x
                            parts = str(x).split(d)
                            if i < len(parts):
                                return parts[i].strip() if s else parts[i]
                            return ""
                        df[col] = df[col].apply(_split)

                    elif t_type == "date_format":
                        input_fmt = transform.get("input_format", "%Y-%m-%d")
                        output_fmt = transform.get("output_format", "%Y-%m-%d")
                        from datetime import datetime as _dt
                        def _reformat_date(x, ifmt=input_fmt, ofmt=output_fmt):
                            if pd.isna(x) or str(x).strip() == "":
                                return x
                            try:
                                return _dt.strptime(str(x).strip(), ifmt).strftime(ofmt)
                            except Exception:
                                return x
                        df[col] = df[col].apply(_reformat_date)

                    elif t_type == "empty_to_null":
                        df[col] = df[col].apply(
                            lambda x: None
                            if (pd.isna(x) or str(x).strip() == "") else x
                        )

                    elif t_type == "truncate":
                        max_len = transform.get("max_length", 255)
                        df[col] = df[col].apply(
                            lambda x: str(x)[:max_len] if pd.notna(x) and str(x).strip() != "" else x
                        )

                    elif t_type == "abs_if_negative":
                        def _abs_neg(x):
                            if pd.isna(x) or str(x).strip() == "":
                                return x
                            try:
                                val = float(str(x).strip())
                                return str(abs(val)) if val < 0 else x
                            except Exception:
                                return x
                        df[col] = df[col].apply(_abs_neg)

                except Exception as exc:
                    logger.warning(
                        f"Global transform '{t_type}' on '{col}' failed: {exc}"
                    )

        return df

    # ------------------------------------------------------------------
    # Quality filters: filter out rows before aggregation
    # ------------------------------------------------------------------
    def apply_quality_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove rows that match quality_checks rules (operates on raw DataFrame)."""
        qc = self.config.get("quality_checks", {})
        if not qc:
            return df

        mask = pd.Series(True, index=df.index)

        # skip_if_empty — drop rows where any of these source columns is blank
        for col_name in qc.get("skip_if_empty", []):
            norm_col = _norm(col_name)
            if norm_col in df.columns:
                is_blank = (
                    df[norm_col].isna()
                    | (df[norm_col].astype(str).str.strip() == "")
                )
                mask &= ~is_blank
                n_dropped = is_blank.sum()
                if n_dropped:
                    logger.info(
                        f"quality_check skip_if_empty '{col_name}': "
                        f"removing {n_dropped} rows"
                    )

        # skip_if_contains — drop rows where field contains any value (substring)
        for rule in qc.get("skip_if_contains", []):
            col_name = rule.get("field", "")
            values = rule.get("values", [])
            norm_col = _norm(col_name)
            if norm_col in df.columns and values:
                col_str = df[norm_col].astype(str)
                for val in values:
                    hit = col_str.str.contains(str(val), na=False, regex=False)
                    n_dropped = (mask & hit).sum()
                    if n_dropped:
                        logger.info(
                            f"quality_check skip_if_contains '{val}' in '{col_name}': "
                            f"removing {n_dropped} rows"
                        )
                    mask &= ~hit

        # skip_if_equals — drop rows where field exactly equals a value
        for rule in qc.get("skip_if_equals", []):
            col_name = rule.get("field", "")
            val = str(rule.get("value", ""))
            norm_col = _norm(col_name)
            if norm_col in df.columns:
                hit = df[norm_col].astype(str).str.strip() == val
                n_dropped = (mask & hit).sum()
                if n_dropped:
                    logger.info(
                        f"quality_check skip_if_equals '{val}' in '{col_name}': "
                        f"removing {n_dropped} rows"
                    )
                mask &= ~hit

        filtered = df[mask].copy()
        total_removed = len(df) - len(filtered)
        if total_removed:
            logger.info(
                f"Quality filters removed {total_removed} rows "
                f"({len(df)} → {len(filtered)})"
            )
        return filtered

    # ------------------------------------------------------------------
    # Aggregation: collapse service-item rows to encounter level
    # ------------------------------------------------------------------
    def aggregate_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregate service-item level rows to encounter level.

        Supports three aggregation strategies per the YAML 'aggregation.rules':
          sum          — numeric sum across all rows in the group
          first        — first non-empty value in the group
          collect_icd  — collect all non-null ICD values across multiple source
                         columns and all rows, deduplicate, then fill target slots
        """
        agg_config = self.config.get("aggregation", {})
        if not agg_config.get("enabled", False):
            return df

        group_col_raw = agg_config.get("group_by", "")
        group_col = _norm(group_col_raw)

        if not group_col or group_col not in df.columns:
            logger.warning(
                f"Aggregation: group_by column '{group_col_raw}' not found "
                f"— skipping aggregation"
            )
            return df

        rules = agg_config.get("rules", {})
        sum_cols = {_norm(c) for c in rules.get("sum", [])}
        sum_positive_cols = {_norm(c) for c in rules.get("sum_positive", [])}
        first_cols = {_norm(c) for c in rules.get("first", [])}

        icd_cfg = rules.get("collect_icd", {})
        icd_sources = [_norm(c) for c in icd_cfg.get("sources", [])]
        icd_targets = [_norm(c) for c in icd_cfg.get("targets", [])]

        all_icd_cols = set(icd_sources) | set(icd_targets)

        def _first_non_empty(series: pd.Series):
            """Return the first non-null, non-blank value; else empty string."""
            for val in series:
                if val is not None and pd.notna(val) and str(val).strip() != "":
                    return val
            return ""

        records = []

        for enc_key, group in df.groupby(group_col, sort=False):
            row: Dict = {group_col: enc_key}

            # __rownum — keep the first row number for traceability
            if "__rownum" in group.columns:
                row["__rownum"] = group["__rownum"].iloc[0]

            for col in df.columns:
                if col in (group_col, "__rownum"):
                    continue
                if col in all_icd_cols:
                    continue  # handled separately below

                if col in sum_cols:
                    numeric = pd.to_numeric(group[col], errors="coerce").fillna(0)
                    row[col] = str(numeric.sum())
                elif col in sum_positive_cols:
                    numeric = pd.to_numeric(group[col], errors="coerce").fillna(0)
                    row[col] = str(numeric[numeric > 0].sum())
                else:
                    # first (explicit) or default for anything else
                    row[col] = _first_non_empty(group[col])

            # Collect ICD codes across all source columns and all rows
            if icd_sources:
                all_icds: List[str] = []
                seen: set = set()
                for src_col in icd_sources:
                    if src_col not in group.columns:
                        continue
                    for val in group[src_col]:
                        if val is None or pd.isna(val):
                            continue
                        v = str(val).strip()
                        if v and v not in seen:
                            seen.add(v)
                            all_icds.append(v)

                for i, tgt in enumerate(icd_targets):
                    row[tgt] = all_icds[i] if i < len(all_icds) else ""

            records.append(row)

        result = pd.DataFrame(records)

        # Ensure every original column is present (handles edge cases)
        for col in df.columns:
            if col not in result.columns:
                result[col] = ""

        logger.info(
            f"Aggregation complete: {len(df)} service-item rows "
            f"→ {len(result)} encounter records"
        )
        return result

    # ------------------------------------------------------------------
    # Misc helpers kept for backward compat
    # ------------------------------------------------------------------
    def get_field_metadata(self, canonical_field: str) -> Optional[Dict]:
        mappings = self.config.get("field_mappings", {})
        field_config = mappings.get(canonical_field)
        if isinstance(field_config, dict):
            return field_config
        return None

    def get_mapping_summary(self) -> Dict:
        return {
            "tenant_id": self.tenant_id,
            "tenant_name": self.tenant_name,
            "config_path": str(self.config_path),
            "mapped_fields": len(self.field_map),
            "constant_fields": len(self.constants),
            "value_mapped_fields": len(self.value_maps),
            "field_mappings": self.field_map,
            "constants": self.constants,
        }


def load_tenant_config(tenant_id: str, config_dir: str = "config/tenants") -> TenantMapper:
    config_path = Path(config_dir) / f"{tenant_id}.yaml"
    return TenantMapper(str(config_path))
