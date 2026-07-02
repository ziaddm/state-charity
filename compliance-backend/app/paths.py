"""
Filesystem anchors for the backend.

All config/output paths are resolved relative to the backend package root so
behavior does not depend on the process working directory (uvicorn launched
from the repo root, from compliance-backend/, or inside the Docker image all
resolve to the same directories).
"""
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent

CONFIG_DIR = BACKEND_ROOT / "config"
TENANT_CONFIG_DIR = CONFIG_DIR / "tenants"
OUTPUT_DIR = BACKEND_ROOT / "output"
