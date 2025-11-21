# app/mapping/mapper.py

# Tenant field mapping module.
# Maps tenant-specific column names to canonical schema fields.

import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class MappingError(Exception):
    # Raised when mapping configuration or execution fails
    pass


class TenantMapper:
    
    #Maps tenant-specific column names to canonical schema fields.
    #Handles field mappings, constants, and value transformations.
    
    
    def __init__(self, config_path: str):
        
        #Load tenant mapping configuration from YAML.
        
        #Args:
        #config_path: Path to tenant's mapping YAML file
            
        #Raises:
            #FileNotFoundError: If config file doesn't exist
            #MappingError: If config is invalid

        self.config_path = Path(config_path)
        if not self.config_path.exists():
            raise FileNotFoundError(f"Mapping config not found: {config_path}")
        
        logger.debug(f"Loading tenant config: {config_path}")
        with open(self.config_path) as f:
            self.config = yaml.safe_load(f)
        
        self.validate_config()
        
        # Build forward and reverse maps
        self.field_map = self.build_field_map()
        self.reverse_map = {v: k for k, v in self.field_map.items()}
        
        # Extract other useful config sections
        self.tenant_id = self.config.get("tenant_id")
        self.tenant_name = self.config.get("tenant_name", "Unknown")
        self.constants = self.config.get("constants", {})
        self.transforms = self.config.get("transforms", {})
        self.value_maps = self.extract_value_maps()
    
    def validate_config(self):
        #Ensure required config sections exist
        required = ["tenant_id", "field_mappings"]
        missing = [k for k in required if k not in self.config]
        if missing:
            raise MappingError(f"Config missing required keys: {missing}")
        
        logger.info(f"Config validated for tenant: {self.config.get('tenant_id')}")
    
    def build_field_map(self) -> Dict[str, str]:
        
        #Build mapping from tenant columns to canonical fields.
        
        #Returns:
            #Dict mapping tenant column name (normalized) -> canonical field name
        
        mappings = self.config["field_mappings"]
        field_map = {}
        
        for canonical_field, tenant_config in mappings.items():
            if isinstance(tenant_config, str):
                # Simple mapping: canonical_field: "tenant_column"
                normalized = tenant_config.lower().replace(" ", "_").strip("_")
                field_map[normalized] = canonical_field
            elif isinstance(tenant_config, dict):
                # Complex mapping with source and optional transforms
                source = tenant_config.get("source")
                if source:
                    normalized = source.lower().replace(" ", "_").strip("_")
                    field_map[normalized] = canonical_field
        
        logger.debug(f"Built field map with {len(field_map)} mappings")
        return field_map
    
    def extract_value_maps(self) -> Dict[str, Dict[str, str]]:
        #Extract value_map definitions from field_mappings
        value_maps = {}
        mappings = self.config.get("field_mappings", {})
        
        for canonical_field, tenant_config in mappings.items():
            if isinstance(tenant_config, dict) and "value_map" in tenant_config:
                value_maps[canonical_field] = tenant_config["value_map"]
        
        return value_maps
    
    def map_dataframe(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[Dict]]:
        
        #Map tenant DataFrame columns to canonical schema.
        
        # Args:
            #df: DataFrame with normalized tenant column names (from extractor)
        
        # Returns:
            # Tuple of (mapped_df, warnings)
            #  - mapped_df: DataFrame with canonical column names
            #  - warnings: List of mapping issues (missing columns, unmapped columns)

        logger.info(f"Mapping dataframe: {len(df)} rows, {len(df.columns)} columns")
        warnings = []
        mapped_data = {}
        
        # Track which tenant columns we've used
        used_cols = set()
        
        # Map each canonical field
        for tenant_col, canonical_field in self.field_map.items():
            if tenant_col in df.columns:
                col_data = df[tenant_col].copy()
                
                # Apply value mapping if defined
                if canonical_field in self.value_maps:
                    value_map = self.value_maps[canonical_field]
                    col_data = col_data.map(lambda x: value_map.get(x, x))
                    logger.debug(f"Applied value_map to {canonical_field}")
                
                mapped_data[canonical_field] = col_data
                used_cols.add(tenant_col)
            else:
                # Check if this field has a constant or default value
                if canonical_field in self.constants:
                    const_val = self.constants[canonical_field]
                    mapped_data[canonical_field] = [const_val] * len(df)
                    logger.debug(f"Using constant value for {canonical_field}: {const_val}")
                else:
                    warnings.append({
                        "code": "W603",
                        "severity": "warning",
                        "type": "missing_source_column",
                        "field": canonical_field,
                        "row": "All",
                        "message": f"Missing column '{tenant_col}' - Add this column to your CSV file to provide data for {canonical_field}",
                        "action": f"Add '{tenant_col}' column to input file"
                    })
        
        # Add any constant fields not in mappings
        for canonical_field, const_val in self.constants.items():
            if canonical_field not in mapped_data:
                mapped_data[canonical_field] = [const_val] * len(df)
                logger.debug(f"Added constant field {canonical_field}")
        
        # Warn about unmapped tenant columns (except __rownum)
        unmapped = set(df.columns) - used_cols - {"__rownum"}
        for col in unmapped:
            warnings.append({
                "code": "I003",
                "severity": "info",
                "type": "unmapped_tenant_column",
                "field": col,
                "row": "All",
                "message": f"Extra column '{col}' in your file - This column will be ignored (not needed for submission)",
                "action": "No action needed - column will be skipped"
            })
        
        # Preserve __rownum if present
        if "__rownum" in df.columns:
            mapped_data["__rownum"] = df["__rownum"]
        
        mapped_df = pd.DataFrame(mapped_data)
        
        logger.info(f"Mapping complete: {len(mapped_df.columns)} canonical fields, {len(warnings)} warnings")
        return mapped_df, warnings
    
    def get_field_metadata(self, canonical_field: str) -> Optional[Dict]:
        """
        Get transform/validation metadata for a canonical field.
        
        Args:
            canonical_field: Canonical field name
            
        Returns:
            Field configuration dict or None if not found
        """
        mappings = self.config.get("field_mappings", {})
        field_config = mappings.get(canonical_field)
        
        if isinstance(field_config, dict):
            return field_config
        return None
    
    def get_mapping_summary(self) -> Dict:
        """
        Return summary of mapping configuration for diagnostics and audit trail.
        
        Returns:
            Dict with tenant info and mapping statistics
        """
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
    """
    Load tenant mapping configuration by tenant_id.
    
    Args:
        tenant_id: Tenant identifier (e.g., "acme_health")
        config_dir: Directory containing tenant YAML files
    
    Returns:
        TenantMapper instance
        
    Raises:
        FileNotFoundError: If tenant config doesn't exist
        MappingError: If config is invalid
    """
    config_path = Path(config_dir) / f"{tenant_id}.yaml"
    return TenantMapper(str(config_path))