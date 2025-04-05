"""Logger for validation failures in questions.

This module provides functionality to log validation failures that occur when
question answers don't meet the expected format or constraints. The logs can be
used to improve the "fix" methods for questions.
"""

import datetime
import json
import logging
import os
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

from ..config import CONFIG

# Set up logging
logger = logging.getLogger("validation_failures")
logger.setLevel(logging.INFO)

# Determine log directory path
LOG_DIR = Path(CONFIG.get("EDSL_LOG_DIR", Path.home() / ".edsl" / "logs"))
VALIDATION_LOG_FILE = LOG_DIR / "validation_failures.log"

# Create log directory if it doesn't exist
os.makedirs(LOG_DIR, exist_ok=True)

# Create file handler
file_handler = logging.FileHandler(VALIDATION_LOG_FILE)
file_handler.setLevel(logging.INFO)

# Create formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Add handler to logger
logger.addHandler(file_handler)


def log_validation_failure(
    question_type: str,
    question_name: str,
    error_message: str,
    invalid_data: Dict[str, Any],
    model_schema: Dict[str, Any],
    question_dict: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log a validation failure to the validation failures log file.
    
    Args:
        question_type: The type of question that had a validation failure
        question_name: The name of the question
        error_message: The validation error message
        invalid_data: The data that failed validation
        model_schema: The schema of the model used for validation
        question_dict: Optional dictionary representation of the question
    """
    log_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "question_type": question_type,
        "question_name": question_name,
        "error_message": error_message,
        "invalid_data": invalid_data,
        "model_schema": model_schema,
        "question_dict": question_dict,
        "traceback": traceback.format_exc(),
    }
    
    # Log as JSON for easier parsing
    logger.info(json.dumps(log_entry))


def get_validation_failure_logs(n: int = 10) -> list:
    """
    Get the latest n validation failure logs.
    
    Args:
        n: Number of logs to return (default: 10)
        
    Returns:
        List of validation failure log entries as dictionaries
    """
    logs = []
    
    # Check if log file exists
    if not os.path.exists(VALIDATION_LOG_FILE):
        return logs
        
    with open(VALIDATION_LOG_FILE, "r") as f:
        for line in f:
            try:
                # Skip non-JSON lines (like logger initialization)
                if not line.strip().startswith("{"):
                    continue
                log_entry = json.loads(line.split(" - ")[-1])
                logs.append(log_entry)
            except (json.JSONDecodeError, IndexError):
                # Skip malformed lines
                continue
    
    # Return most recent logs first
    return sorted(logs, key=lambda x: x.get("timestamp", ""), reverse=True)[:n]


def clear_validation_logs() -> None:
    """Clear all validation failure logs."""
    if os.path.exists(VALIDATION_LOG_FILE):
        with open(VALIDATION_LOG_FILE, "w") as f:
            f.write("")