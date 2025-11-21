"""
Extraction - Data Ingestion Layer

This module handles loading and normalizing raw data files from various formats
(CSV, TSV, Excel) into standardized DataFrames.
"""

from app.extraction.extractor import load_source, normalize_headers

__all__ = ["load_source", "normalize_headers"]
