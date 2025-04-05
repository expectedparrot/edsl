"""Analyze validation failures to improve fix methods.

This module provides tools to analyze validation failures that have been logged
and suggest improvements to the fix methods for various question types.
"""

import collections
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..config import CONFIG
from .validation_logger import get_validation_failure_logs


def get_validation_failure_stats() -> Dict[str, Dict[str, int]]:
    """
    Get statistics about validation failures by question type and error message.
    
    Returns:
        Dictionary with stats about validation failures by question type and error message
    """
    logs = get_validation_failure_logs(n=1000)  # Get up to 1000 recent logs
    
    # Count by question type
    type_counts = collections.Counter()
    
    # Count by question type and error message
    error_counts = collections.defaultdict(collections.Counter)
    
    for log in logs:
        question_type = log.get("question_type", "unknown")
        error_message = log.get("error_message", "unknown")
        
        type_counts[question_type] += 1
        error_counts[question_type][error_message] += 1
    
    # Convert to dict for cleaner output
    result = {
        "by_question_type": dict(type_counts),
        "by_error_message": {k: dict(v) for k, v in error_counts.items()}
    }
    
    return result


def suggest_fix_improvements(question_type: Optional[str] = None) -> Dict[str, List[Dict]]:
    """
    Analyze validation failures and suggest improvements for fix methods.
    
    Args:
        question_type: Optional filter for a specific question type
        
    Returns:
        Dictionary with improvement suggestions for fix methods
    """
    logs = get_validation_failure_logs(n=1000)  # Get up to 1000 recent logs
    
    # Filter by question_type if provided
    if question_type:
        logs = [log for log in logs if log.get("question_type") == question_type]
    
    # Group by question type
    grouped_logs = collections.defaultdict(list)
    for log in logs:
        grouped_logs[log.get("question_type", "unknown")].append(log)
    
    suggestions = {}
    
    # Analyze patterns for each question type
    for qt, logs in grouped_logs.items():
        qt_suggestions = []
        
        # Get common error patterns
        error_counter = collections.Counter([log.get("error_message", "") for log in logs])
        common_errors = error_counter.most_common(5)  # Top 5 errors
        
        # Create suggestions based on error patterns
        for error_msg, count in common_errors:
            if not error_msg:
                continue
                
            # Get example data for this error
            example_logs = [log for log in logs if log.get("error_message") == error_msg]
            example = example_logs[0] if example_logs else None
            
            suggestion = {
                "error_message": error_msg,
                "occurrence_count": count,
                "suggestion": _generate_suggestion(qt, error_msg, example),
                "example_data": example.get("invalid_data") if example else None
            }
            
            qt_suggestions.append(suggestion)
            
        if qt_suggestions:
            suggestions[qt] = qt_suggestions
    
    return suggestions


def _generate_suggestion(question_type: str, error_msg: str, example: Optional[Dict]) -> str:
    """
    Generate a suggestion for improving fix methods based on the error pattern.
    
    Args:
        question_type: The question type
        error_msg: The error message
        example: An example log entry containing the error
        
    Returns:
        A suggestion string for improving the fix method
    """
    # Common validation error patterns and suggestions
    if "missing" in error_msg.lower() and "key" in error_msg.lower():
        return (
            f"The fix method for {question_type} should check for missing keys "
            f"in the answer and add them with default values."
        )
    
    if "not a valid" in error_msg.lower() and any(t in error_msg.lower() for t in ["integer", "number", "float"]):
        return (
            f"The fix method for {question_type} should convert string values to the expected "
            f"numeric type (int/float) and handle non-numeric strings."
        )
    
    if "must be" in error_msg.lower() and "length" in error_msg.lower():
        return (
            f"The fix method for {question_type} should ensure the answer has the correct length "
            f"requirements, potentially truncating or padding as needed."
        )
    
    if "not a valid" in error_msg.lower() and "list" in error_msg.lower():
        return (
            f"The fix method for {question_type} should ensure the answer is a valid list, "
            f"potentially converting single items to lists when needed."
        )
    
    if "greater than" in error_msg.lower() or "less than" in error_msg.lower():
        return (
            f"The fix method for {question_type} should enforce value range constraints "
            f"by clamping values to the allowed min/max range."
        )
    
    # Default suggestion
    return (
        f"Review the validation failures for {question_type} and update the fix method "
        f"to handle common error patterns more effectively."
    )


def export_improvements_report(output_path: Optional[Path] = None) -> Path:
    """
    Generate a report with improvement suggestions for fix methods.
    
    Args:
        output_path: Optional custom path for the report
        
    Returns:
        Path to the generated report
    """
    if output_path is None:
        default_log_dir = Path.home() / ".edsl" / "logs"
        report_dir = Path(CONFIG.get("EDSL_LOG_DIR", default=str(default_log_dir)))
        output_path = report_dir / "fix_methods_improvements.json"
    
    # Get stats and suggestions
    stats = get_validation_failure_stats()
    suggestions = suggest_fix_improvements()
    
    # Create report
    report = {
        "validation_failure_stats": stats,
        "fix_method_improvement_suggestions": suggestions
    }
    
    # Write report to file
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
    
    return output_path