"""Configuration module for EDSL.

This module provides a Config class that loads environment variables from a .env file and sets them as class attributes.
"""

from .config_class import Config, CONFIG, CONFIG_MAP, EDSL_RUN_MODES, cache_dir
from .styles import RICH_STYLES, get_style, get_style_safe

__all__ = [
    "Config",
    "CONFIG",
    "CONFIG_MAP",
    "EDSL_RUN_MODES",
    "cache_dir",
    "RICH_STYLES",
    "get_style",
    "get_style_safe",
]
