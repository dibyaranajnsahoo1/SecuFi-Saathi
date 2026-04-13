from __future__ import annotations

from typing import Any

try:
    from analyzer import analyze_household
except ImportError:
    from src.analyzer import analyze_household


def run_gap_analysis(household_data: dict[str, Any]) -> dict[str, Any]:
    """Wrapper around Round 1 analyzer for tool use."""
    report = analyze_household(household_data)
    return report.model_dump()
