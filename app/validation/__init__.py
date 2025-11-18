"""
Validation - Data Quality Layer

This module validates data against schema rules and business logic,
ensuring compliance with state submission requirements.
"""

from app.validation.validator import validate_canonical
from app.validation.coercions import apply_coercions

__all__ = ["validate_canonical", "apply_coercions"]
