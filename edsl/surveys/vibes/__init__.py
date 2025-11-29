"""Vibes module for natural language survey generation and editing.

This module provides functionality for creating and modifying surveys using
natural language descriptions, powered by LLMs. It supports both local and
remote survey generation modes.
"""

from .survey_generator import SurveyGenerator
from .vibe_editor import VibeEdit
from .vibe_add_helper import VibeAdd
from .vibe_describer import VibeDescribe
from .from_vibes import generate_survey_from_vibes
from .vibe_edit_handler import edit_survey_with_vibes
from .vibe_add_handler import add_questions_with_vibes
from .vibe_describe_handler import describe_survey_with_vibes

# Remote survey generation components
from .remote_survey_generator import RemoteSurveyGenerator, should_use_remote

# Exceptions
from .exceptions import (
    VibesError,
    RemoteSurveyGenerationError,
    SurveyGenerationError,
)

__all__ = [
    # Core functionality
    "SurveyGenerator",
    "VibeEdit",
    "VibeAdd",
    "VibeDescribe",
    "generate_survey_from_vibes",
    "edit_survey_with_vibes",
    "add_questions_with_vibes",
    "describe_survey_with_vibes",

    # Remote generation
    "RemoteSurveyGenerator",
    "should_use_remote",

    # Exceptions
    "VibesError",
    "RemoteSurveyGenerationError",
    "SurveyGenerationError",
]
