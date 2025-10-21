"""Assistants module for EDSL.

This module provides AI assistants for creating and managing EDSL objects.
Currently includes:
- SurveyAssistant: For creating EDSL surveys from documents
"""

from .survey_assistant import SurveyAssistant

__all__ = ["SurveyAssistant"]
