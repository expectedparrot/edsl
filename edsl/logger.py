"""
Logger module for EDSL.

This module provides a centralized logging configuration for the EDSL package.
It configures console and file logging with appropriate formatting.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Create the logger
logger = logging.getLogger("edsl")
logger.setLevel(logging.ERROR)  # Default level

# Avoid adding handlers multiple times when imported in different modules
if not logger.handlers:
    # Console handler removed - logs only go to file now

    # File handler - create logs directory if it doesn't exist
    try:
        log_dir = Path.home() / ".edsl" / "logs"
        os.makedirs(log_dir, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_dir / "edsl.log", maxBytes=5 * 1024 * 1024, backupCount=3  # 5 MB
        )
        file_handler.setLevel(logging.ERROR)
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        # Don't fail if file logging can't be set up
        # No console handler to adjust
        print(f"WARNING: Could not set up file logging: {e}")


def get_logger(name):
    """
    Get a logger for a specific module.

    Args:
        name: Usually __name__ of the module

    Returns:
        A Logger instance configured with the EDSL settings
    """
    return logging.getLogger(f"edsl.{name}")


def set_level(level):
    """
    Set the logging level for the EDSL logger.

    Args:
        level: A logging level (e.g., logging.DEBUG, logging.INFO, etc.)
    """
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)

    # Update child loggers
    for logger_name in logging.root.manager.loggerDict:
        if logger_name.startswith("edsl."):
            logging.getLogger(logger_name).setLevel(level)


# Convenience function to avoid importing logging in every file
def debug(msg, *args, **kwargs):
    logger.debug(msg, *args, **kwargs)


def info(msg, *args, **kwargs):
    logger.info(msg, *args, **kwargs)


def warning(msg, *args, **kwargs):
    logger.warning(msg, *args, **kwargs)


def error(msg, *args, **kwargs):
    logger.error(msg, *args, **kwargs)


def critical(msg, *args, **kwargs):
    logger.critical(msg, *args, **kwargs)


def exception(msg, *args, **kwargs):
    """Log an exception with traceback at the ERROR level"""
    logger.exception(msg, *args, **kwargs)


def configure_from_config():
    """
    Configure logging based on EDSL_LOG_LEVEL environment variable or config.

    This function looks for the EDSL_LOG_LEVEL setting in the config and sets
    the logging level accordingly. Valid values are:
    - DEBUG
    - INFO
    - WARNING
    - ERROR
    - CRITICAL    
    If no configuration is found, the default level (ERROR) is maintained.

    """
    try:
        import os

        # First check environment variable
        log_level = os.environ.get("EDSL_LOG_LEVEL")

        # If not in environment, try to get from config
        if not log_level:
            try:
                from edsl.config import CONFIG

                log_level = CONFIG.EDSL_LOG_LEVEL
            except (ImportError, AttributeError):
                # Config might not be available or doesn't have EDSL_LOG_LEVEL
                pass

        if log_level:
            # Convert to uppercase to match logging constants
            log_level = log_level.upper()

            # Map string to logging level
            level_map = {
                "DEBUG": logging.DEBUG,
                "INFO": logging.INFO,
                "WARNING": logging.WARNING,
                "ERROR": logging.ERROR,
                "CRITICAL": logging.CRITICAL,
            }

            if log_level in level_map:
                set_level(level_map[log_level])
                info(f"Log level set to {log_level} from configuration")
            else:
                warning(f"Invalid log level in configuration: {log_level}")
    except Exception as e:
        # Catch any exceptions to ensure logging configuration doesn't break the application
        warning(f"Error configuring logging from config: {e}")
