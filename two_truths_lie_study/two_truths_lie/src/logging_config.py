"""Logging configuration for Two Truths and a Lie game."""

import logging
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields if present
        if hasattr(record, "round_id"):
            log_entry["round_id"] = record.round_id
        if hasattr(record, "phase"):
            log_entry["phase"] = record.phase
        if hasattr(record, "storyteller_id"):
            log_entry["storyteller_id"] = record.storyteller_id

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


class ConsoleFormatter(logging.Formatter):
    """Human-readable console formatter."""

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[41m",  # Red background
        "RESET": "\033[0m"
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        reset = self.COLORS["RESET"]

        # Add context if present
        context = ""
        if hasattr(record, "round_id"):
            context += f"[Round:{record.round_id}] "
        if hasattr(record, "phase"):
            context += f"[{record.phase}] "

        return f"{color}[{record.levelname}]{reset} {context}{record.getMessage()}"


def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    json_format: bool = True
) -> logging.Logger:
    """Set up logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file
        json_format: If True, use JSON format for file logging

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("two_truths_lie")
    logger.setLevel(getattr(logging, level.upper()))

    # Clear existing handlers
    logger.handlers = []

    # Console handler with human-readable format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ConsoleFormatter())
    logger.addHandler(console_handler)

    # File handler with JSON format (if specified)
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        if json_format:
            file_handler.setFormatter(JSONFormatter())
        else:
            file_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            )
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "two_truths_lie") -> logging.Logger:
    """Get a logger instance.

    Args:
        name: Logger name (will be prefixed with 'two_truths_lie.')

    Returns:
        Logger instance
    """
    if not name.startswith("two_truths_lie"):
        name = f"two_truths_lie.{name}"
    return logging.getLogger(name)


class RoundLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that includes round context."""

    def __init__(self, logger: logging.Logger, round_id: str):
        super().__init__(logger, {"round_id": round_id})

    def process(self, msg, kwargs):
        extra = kwargs.get("extra", {})
        extra["round_id"] = self.extra["round_id"]
        kwargs["extra"] = extra
        return msg, kwargs

    def set_phase(self, phase: str):
        """Set the current phase for logging context."""
        self.extra["phase"] = phase


# Default logger instance
logger = get_logger()
