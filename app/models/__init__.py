"""
Models - Data Structures

This module defines the core data models and artifacts used throughout
the compliance reporting pipeline.
"""

from app.models.artifacts import ValidationResult, ControlTotals, ReportArtifact

__all__ = ["ValidationResult", "ControlTotals", "ReportArtifact"]
