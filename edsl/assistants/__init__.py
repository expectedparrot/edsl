"""Assistants module for EDSL.

This module provides AI assistants for creating and managing EDSL objects.
Currently includes:
- SurveyAssistant: For creating EDSL surveys from documents

SurveyAssistant is lazily imported to avoid loading typer/rich at import time.
"""

__all__ = ["SurveyAssistant"]


def __getattr__(name):
    if name == "SurveyAssistant":
        from .survey_assistant import SurveyAssistant
        return SurveyAssistant
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
