"""
Refactored vibe system for AI-powered Qualtrics question cleanup.

This is the new, refactored version of the vibe system with improved
modularity, maintainability, and following Python best practices.

Architecture Overview:
- config/: Configuration management with external prompts
- converters/: Pluggable converter system using Strategy pattern
- logging/: Centralized logging system
- core/: Core processing components with single responsibilities
- exceptions/: Custom exception hierarchy
- analysis/: Question analysis components

Usage:
    from edsl.conjure.qualtrics.vibe import VibeProcessor, VibeConfig

    # Basic usage
    processor = VibeProcessor()
    improved_survey = processor.process_survey_sync(survey)

    # Custom configuration
    config = VibeConfig(
        enable_logging=True,
        max_concurrent=10,
        verbose_logging=True
    )
    processor = VibeProcessor(config)
    improved_survey = processor.process_survey_sync(survey)

    # Access change tracking
    changes = processor.get_change_log()
    summary = processor.get_change_summary()
"""

# Public API - using multi-step processor as default
from .config import VibeChange
from .converters import get_default_registry, register_converter
from .exceptions import VibeException

# Use the multi-step processor as the main VibeProcessor
from .vibe_processor import (
    VibeProcessor,  # Our updated multi-step processor
    VibeConfig,
)

# Keep the new processor available as alternative
from .core import VibeProcessor as NewVibeProcessor
from .question_analyzer import QuestionAnalyzer

__version__ = "2.0.0"

__all__ = [
    # Multi-step API (default)
    "VibeConfig",
    "VibeChange",
    "VibeProcessor",
    "get_default_registry",
    "register_converter",
    "VibeException",
    # Alternative implementations
    "NewVibeProcessor",
    "QuestionAnalyzer",
]
