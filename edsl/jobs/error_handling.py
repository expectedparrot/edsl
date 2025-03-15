"""
Error handling for EDSL jobs.

This module provides utilities for handling errors during job execution,
with support for different error policies and reporting modes.
"""
from typing import Optional, TYPE_CHECKING, Any, Dict, List, Union
import sys
import traceback

if TYPE_CHECKING:
    from ..results import Results
    from .data_structures import RunParameters


class ErrorHandler:
    """
    Central handler for errors during job execution.
    
    This class manages error detection, reporting, and recovery during
    job execution, with configurable policies for different error types.
    """
    
    def __init__(self, results: "Results", parameters: "RunParameters"):
        """
        Initialize an error handler.
        
        Parameters:
            results: The results being collected during execution
            parameters: Configuration parameters that control error handling
        """
        self.results = results
        self.parameters = parameters
        
    def handle_exceptions(self) -> None:
        """
        Process any exceptions that occurred during job execution.
        
        This method checks for exceptions in the task history, reports them
        if configured to do so, and raises them if stop_on_exception is enabled.
        """
        from .results_exceptions_handler import ResultsExceptionsHandler
        
        # Use the existing exception handler for now
        # In a future refactoring, this logic could be moved into this class
        results_exceptions_handler = ResultsExceptionsHandler(
            self.results, self.parameters
        )
        results_exceptions_handler.handle_exceptions()
    
    @staticmethod
    def format_exception(exc: Exception) -> str:
        """
        Format an exception for display.
        
        Parameters:
            exc: The exception to format
            
        Returns:
            str: Formatted exception message with traceback
        """
        exc_type, exc_value, exc_traceback = sys.exc_info()
        if exc_traceback is None:
            return str(exc)
            
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        return ''.join(tb_lines)
    
    @staticmethod
    def handle_keyboard_interrupt() -> None:
        """
        Handle a KeyboardInterrupt gracefully.
        
        This method prints a message and sets up for graceful shutdown.
        """
        print("Keyboard interrupt received. Stopping gracefully...")


class ValidationErrorHandler:
    """
    Specialized handler for validation errors.
    
    This class manages the detection and handling of validation errors,
    which occur when responses don't meet the expected format or constraints.
    """
    
    def __init__(self, raise_errors: bool = False):
        """
        Initialize a validation error handler.
        
        Parameters:
            raise_errors: Whether to raise validation errors (True) or just log them (False)
        """
        self.raise_errors = raise_errors
        
    def handle_validation_error(self, error: Exception, context: Dict[str, Any]) -> None:
        """
        Handle a validation error.
        
        Parameters:
            error: The validation error that occurred
            context: Additional context about when/where the error occurred
            
        Raises:
            Exception: The original error if raise_errors is True
        """
        if self.raise_errors:
            raise error
            
        # Log the error with context
        self._log_validation_error(error, context)
    
    def _log_validation_error(self, error: Exception, context: Dict[str, Any]) -> None:
        """
        Log a validation error with context.
        
        Parameters:
            error: The validation error that occurred
            context: Additional context about when/where the error occurred
        """
        # In a future implementation, this could log to a file or reporting system
        print(f"Validation error: {error}")
        print(f"Context: {context}")