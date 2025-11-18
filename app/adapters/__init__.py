"""
Adapters - Orchestration Layer

This module coordinates the entire compliance reporting pipeline,
managing the flow from data extraction through validation to final output.
"""

from app.adapters.report_adapter import ReportAdapter

__all__ = ["ReportAdapter"]
