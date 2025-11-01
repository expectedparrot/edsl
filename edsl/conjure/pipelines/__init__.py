"""
Survey normalization pipeline utilities.

This package detects incoming survey data formats, normalizes them into a
canonical representation, and provides helpers to serialize the normalized
survey to YAML plus an agent response table.
"""

from .pipeline import (
    normalize_survey_file,
    NormalizedSurvey,
)

__all__ = [
    "normalize_survey_file",
    "NormalizedSurvey",
]
