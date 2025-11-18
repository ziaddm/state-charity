# dashboard/utils.py
"""
Utility functions for the dashboard.
"""
from pathlib import Path
from typing import List, Dict, Any
import json


def get_tenant_runs(tenant_id: str, output_dir: str = "output") -> List[Dict[str, Any]]:
    """
    Get list of all runs for a tenant.

    Args:
        tenant_id: Tenant identifier
        output_dir: Output directory path

    Returns:
        List of run metadata dictionaries
    """
    tenant_dir = Path(output_dir) / tenant_id

    if not tenant_dir.exists():
        return []

    runs = []
    for run_dir in tenant_dir.iterdir():
        if not run_dir.is_dir():
            continue

        # Try to load manifest
        manifest_file = run_dir / f"{run_dir.name}_manifest.json"
        if manifest_file.exists():
            try:
                with open(manifest_file, 'r') as f:
                    manifest = json.load(f)
                    runs.append({
                        'run_id': run_dir.name,
                        'timestamp': manifest.get('generation_timestamp'),
                        'state_code': manifest.get('state_code'),
                        'record_count': manifest.get('record_count'),
                        'status': manifest.get('status', 'unknown'),
                        'path': str(run_dir)
                    })
            except Exception:
                pass

    # Sort by timestamp descending
    runs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    return runs


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: File size in bytes

    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def get_tenant_list(config_dir: str = "config/tenants") -> List[Dict[str, str]]:
    """
    Get list of available tenants from config directory.

    Args:
        config_dir: Configuration directory path

    Returns:
        List of tenant options for dropdown
    """
    tenant_dir = Path(config_dir)

    if not tenant_dir.exists():
        return []

    tenants = []
    for config_file in tenant_dir.glob("*.yaml"):
        tenant_id = config_file.stem
        # Try to parse the config to get the tenant name
        try:
            import yaml
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
                tenant_name = config.get('tenant_name', tenant_id)
        except Exception:
            tenant_name = tenant_id

        tenants.append({
            'label': f'🏥 {tenant_name}',
            'value': tenant_id
        })

    return sorted(tenants, key=lambda x: x['label'])


def validate_file_extension(filename: str) -> bool:
    """
    Check if uploaded file has valid extension.

    Args:
        filename: Name of the uploaded file

    Returns:
        True if valid, False otherwise
    """
    valid_extensions = ['.csv', '.xlsx', '.xls']
    return any(filename.lower().endswith(ext) for ext in valid_extensions)
