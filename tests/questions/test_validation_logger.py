"""Tests for the validation logger and analysis tools."""

import json
import os
import pytest
from unittest.mock import patch

from edsl.questions.validation_logger import (
    log_validation_failure,
    get_validation_failure_logs,
    clear_validation_logs,
    VALIDATION_LOG_FILE
)
from edsl.questions.validation_analysis import (
    get_validation_failure_stats,
    suggest_fix_improvements,
    export_improvements_report
)


@pytest.fixture
def clean_log_file():
    """Ensure log file is clean for tests."""
    # Make sure the log directory exists
    log_dir = os.path.dirname(VALIDATION_LOG_FILE)
    os.makedirs(log_dir, exist_ok=True)
    
    # Clean up existing log file
    if os.path.exists(VALIDATION_LOG_FILE):
        os.remove(VALIDATION_LOG_FILE)
    
    # Create an empty log file to ensure it exists
    with open(VALIDATION_LOG_FILE, 'w') as f:
        pass
    
    yield
    
    # Clean up after test
    if os.path.exists(VALIDATION_LOG_FILE):
        os.remove(VALIDATION_LOG_FILE)


def test_log_validation_failure(clean_log_file):
    """Test that logging validation failures works."""
    # Log a sample validation failure
    log_validation_failure(
        question_type="QuestionMultipleChoice",
        question_name="test_question",
        error_message="Value is not a valid integer",
        invalid_data={"answer": "not_an_integer"},
        model_schema={"type": "object", "properties": {"answer": {"type": "integer"}}},
        question_dict={"question_name": "test_question", "question_type": "multiple_choice"}
    )
    
    # Check that the log file exists
    assert os.path.exists(VALIDATION_LOG_FILE)
    
    # Read the log file and check content
    with open(VALIDATION_LOG_FILE, "r") as f:
        log_content = f.read()
    
    assert "QuestionMultipleChoice" in log_content
    assert "test_question" in log_content
    assert "Value is not a valid integer" in log_content
    assert "not_an_integer" in log_content


def test_get_validation_failure_logs(clean_log_file):
    """Test retrieving validation failure logs."""
    # Log multiple sample validation failures
    for i in range(3):
        log_validation_failure(
            question_type=f"Question{i}",
            question_name=f"test_question_{i}",
            error_message=f"Error {i}",
            invalid_data={"answer": f"data_{i}"},
            model_schema={"type": "object"},
            question_dict={"question_name": f"test_question_{i}"}
        )
    
    # Get logs and verify
    logs = get_validation_failure_logs()
    assert len(logs) == 3
    
    # Verify log content (newest first)
    assert logs[0]["question_type"] == "Question2"
    assert logs[1]["question_type"] == "Question1"
    assert logs[2]["question_type"] == "Question0"
    
    # Test limiting the number of logs
    limited_logs = get_validation_failure_logs(n=2)
    assert len(limited_logs) == 2
    assert limited_logs[0]["question_type"] == "Question2"
    assert limited_logs[1]["question_type"] == "Question1"


def test_clear_validation_logs(clean_log_file):
    """Test clearing validation logs."""
    # Log a sample validation failure
    log_validation_failure(
        question_type="TestQuestion",
        question_name="test_question",
        error_message="Test error",
        invalid_data={"answer": "test_data"},
        model_schema={"type": "object"},
        question_dict=None
    )
    
    # Verify log exists
    assert os.path.exists(VALIDATION_LOG_FILE)
    logs = get_validation_failure_logs()
    assert len(logs) > 0
    
    # Clear logs and verify
    clear_validation_logs()
    logs_after_clear = get_validation_failure_logs()
    assert len(logs_after_clear) == 0


def test_get_validation_failure_stats(clean_log_file):
    """Test getting validation failure statistics."""
    # Log sample validation failures with patterns
    for _ in range(3):
        log_validation_failure(
            question_type="QuestionMultipleChoice",
            question_name="test_mc",
            error_message="Value is not a valid integer",
            invalid_data={"answer": "not_an_integer"},
            model_schema={"type": "object"},
            question_dict=None
        )
    
    for _ in range(2):
        log_validation_failure(
            question_type="QuestionMultipleChoice",
            question_name="test_mc",
            error_message="Value is not in valid options",
            invalid_data={"answer": "invalid_option"},
            model_schema={"type": "object"},
            question_dict=None
        )
    
    for _ in range(1):
        log_validation_failure(
            question_type="QuestionNumerical",
            question_name="test_num",
            error_message="Value is not a valid number",
            invalid_data={"answer": "not_a_number"},
            model_schema={"type": "object"},
            question_dict=None
        )
    
    # Get statistics and verify
    stats = get_validation_failure_stats()
    
    # Check counts by question type
    assert stats["by_question_type"]["QuestionMultipleChoice"] == 5
    assert stats["by_question_type"]["QuestionNumerical"] == 1
    
    # Check counts by error message
    assert stats["by_error_message"]["QuestionMultipleChoice"]["Value is not a valid integer"] == 3
    assert stats["by_error_message"]["QuestionMultipleChoice"]["Value is not in valid options"] == 2
    assert stats["by_error_message"]["QuestionNumerical"]["Value is not a valid number"] == 1


def test_suggest_fix_improvements(clean_log_file):
    """Test suggesting fix method improvements."""
    # Log sample validation failures
    log_validation_failure(
        question_type="QuestionMultipleChoice",
        question_name="test_mc",
        error_message="Value is not a valid integer",
        invalid_data={"answer": "not_an_integer"},
        model_schema={"type": "object"},
        question_dict=None
    )
    
    log_validation_failure(
        question_type="QuestionNumerical",
        question_name="test_num",
        error_message="Value is greater than maximum",
        invalid_data={"answer": 100},
        model_schema={"type": "object"},
        question_dict=None
    )
    
    # Get suggestions and verify
    suggestions = suggest_fix_improvements()
    
    # Check suggestions for QuestionMultipleChoice
    assert "QuestionMultipleChoice" in suggestions
    mc_suggestion = suggestions["QuestionMultipleChoice"][0]
    assert "error_message" in mc_suggestion
    assert "suggestion" in mc_suggestion
    assert "occurrence_count" in mc_suggestion
    
    # Check suggestions for QuestionNumerical
    assert "QuestionNumerical" in suggestions
    num_suggestion = suggestions["QuestionNumerical"][0]
    assert "greater than" in num_suggestion["error_message"]
    assert "value range constraints" in num_suggestion["suggestion"]
    
    # Check filtering by question type
    filtered_suggestions = suggest_fix_improvements(question_type="QuestionNumerical")
    assert "QuestionMultipleChoice" not in filtered_suggestions
    assert "QuestionNumerical" in filtered_suggestions


def test_export_improvements_report(clean_log_file, tmpdir):
    """Test exporting improvements report."""
    # Log sample validation failures
    log_validation_failure(
        question_type="QuestionMultipleChoice",
        question_name="test_mc",
        error_message="Value is not a valid integer",
        invalid_data={"answer": "not_an_integer"},
        model_schema={"type": "object"},
        question_dict=None
    )
    
    # Create a temporary output file
    output_path = tmpdir.join("test_report.json")
    
    # Export report
    report_path = export_improvements_report(output_path=output_path)
    
    # Verify report exists
    assert os.path.exists(report_path)
    
    # Check report content
    with open(report_path, "r") as f:
        report = json.load(f)
    
    assert "validation_failure_stats" in report
    assert "fix_method_improvement_suggestions" in report
    assert "QuestionMultipleChoice" in report["fix_method_improvement_suggestions"]