"""Configuration module for EDSL.

This module provides a Config class that loads environment variables from a .env file and sets them as class attributes.
"""

from edsl.config.config_class import Config, CONFIG, CONFIG_MAP, EDSL_RUN_MODES, cache_dir

__all__ = ["Config", "CONFIG", "CONFIG_MAP", "EDSL_RUN_MODES", "cache_dir"]