"""Vibes module for natural language question generation.

This module provides functionality for creating questions using
natural language descriptions, powered by LLMs.
"""

from .question_generator import QuestionGenerator
from .from_vibes import generate_question_from_vibes

__all__ = [
    "QuestionGenerator",
    "generate_question_from_vibes",
]
