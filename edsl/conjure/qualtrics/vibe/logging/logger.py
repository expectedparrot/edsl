"""
Centralized logging system for the vibe processor.
"""

from typing import Any, Dict
from abc import ABC, abstractmethod
from .formatters import VibeLogFormatter


class VibeLogger(ABC):
    """Abstract base class for vibe logging."""

    @abstractmethod
    def log_processing_start(self, total_questions: int, batch_size: int) -> None:
        """Log the start of processing."""
        pass

    @abstractmethod
    def log_batch_start(
        self, batch_idx: int, batch_start: int, batch_end: int, total_batches: int
    ) -> None:
        """Log the start of a batch."""
        pass

    @abstractmethod
    def log_conversion_start(self, question_name: str, target_type: str) -> None:
        """Log the start of a conversion attempt."""
        pass

    @abstractmethod
    def log_conversion_params(self, target_type: str, params: Dict[str, Any]) -> None:
        """Log conversion parameters."""
        pass

    @abstractmethod
    def log_conversion_success(self, target_type: str) -> None:
        """Log successful conversion."""
        pass

    @abstractmethod
    def log_conversion_error(self, target_type: str, error_msg: str) -> None:
        """Log conversion error."""
        pass

    @abstractmethod
    def log_question_result(self, question_name: str, had_changes: bool) -> None:
        """Log final result for a question."""
        pass

    @abstractmethod
    def log_processing_complete(
        self, processed_count: int, total_questions: int
    ) -> None:
        """Log completion of processing."""
        pass


class ConsoleVibeLogger(VibeLogger):
    """Console-based vibe logger with rich formatting."""

    def __init__(self, enable_logging: bool = True, verbose: bool = False):
        self.enable_logging = enable_logging
        self.verbose = verbose
        self.formatter = VibeLogFormatter()

    def log_processing_start(self, total_questions: int, batch_size: int) -> None:
        if self.enable_logging:
            print(f"🔍 Analyzing {total_questions} questions for conversion issues...")
            print(f"📊 Processing in batches of {batch_size}")

    def log_batch_start(
        self, batch_idx: int, batch_start: int, batch_end: int, total_batches: int
    ) -> None:
        if self.enable_logging:
            print(
                f"\n📦 Batch {batch_idx}/{total_batches}: Processing questions {batch_start}-{batch_end}..."
            )

    def log_conversion_start(self, question_name: str, target_type: str) -> None:
        if self.enable_logging:
            print(f"    🔄 Converting {self._get_current_type()} → {target_type}")
            print(f"      Question: {question_name}")

    def log_conversion_params(self, target_type: str, params: Dict[str, Any]) -> None:
        if self.enable_logging and self.verbose:
            formatted_params = self.formatter.format_conversion_params(
                target_type, params
            )
            for line in formatted_params:
                print(f"      {line}")

    def log_conversion_success(self, target_type: str) -> None:
        if self.enable_logging:
            print(f"      ✅ {target_type} conversion successful")

    def log_conversion_error(self, target_type: str, error_msg: str) -> None:
        if self.enable_logging:
            print(f"      ❌ {target_type} conversion failed: {error_msg}")

    def log_question_result(self, question_name: str, had_changes: bool) -> None:
        if self.enable_logging:
            if had_changes:
                print(f"✨ {question_name}: Fixed conversion issues")
            else:
                print(f"✅ {question_name}: No issues found")

    def log_processing_complete(
        self, processed_count: int, total_questions: int
    ) -> None:
        if self.enable_logging:
            print(
                f"\n🎯 Analysis complete: {processed_count}/{total_questions} questions processed"
            )

    def _get_current_type(self) -> str:
        """Get current question type. This would be passed in real implementation."""
        return "QuestionMultipleChoice"  # Placeholder


class SilentVibeLogger(VibeLogger):
    """Silent logger that does nothing."""

    def log_processing_start(self, total_questions: int, batch_size: int) -> None:
        pass

    def log_batch_start(
        self, batch_idx: int, batch_start: int, batch_end: int, total_batches: int
    ) -> None:
        pass

    def log_conversion_start(self, question_name: str, target_type: str) -> None:
        pass

    def log_conversion_params(self, target_type: str, params: Dict[str, Any]) -> None:
        pass

    def log_conversion_success(self, target_type: str) -> None:
        pass

    def log_conversion_error(self, target_type: str, error_msg: str) -> None:
        pass

    def log_question_result(self, question_name: str, had_changes: bool) -> None:
        pass

    def log_processing_complete(
        self, processed_count: int, total_questions: int
    ) -> None:
        pass


def create_logger(enable_logging: bool = True, verbose: bool = False) -> VibeLogger:
    """Factory function to create appropriate logger."""
    if enable_logging:
        return ConsoleVibeLogger(enable_logging=True, verbose=verbose)
    else:
        return SilentVibeLogger()
