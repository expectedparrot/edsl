"""
Tests for the BaseException traceback environment variable feature.
"""
import os
import sys
import pytest
from unittest.mock import patch
from edsl.base.base_exception import BaseException

class TestExampleException(BaseException):
    """An example exception for testing purposes."""
    pass

def test_should_show_full_traceback_env_var():
    """Test that _should_show_full_traceback respects environment variable."""
    # Test with env var set to True
    with patch.dict(os.environ, {"EDSL_SHOW_FULL_TRACEBACK": "True"}):
        assert TestExampleException._should_show_full_traceback() is True
    
    # Test with env var set to False
    with patch.dict(os.environ, {"EDSL_SHOW_FULL_TRACEBACK": "False"}):
        assert TestExampleException._should_show_full_traceback() is False
    
    # Test with env var set to other values that should be True
    for true_value in ["true", "1", "yes", "y"]:
        with patch.dict(os.environ, {"EDSL_SHOW_FULL_TRACEBACK": true_value}):
            assert TestExampleException._should_show_full_traceback() is True

def test_should_show_full_traceback_env_from_config():
    """Test that _should_show_full_traceback respects environment variable values that would come from config."""
    # Remove env var to ensure we're testing with a clean environment
    with patch.dict(os.environ, clear=True):
        # Test with env var set to True (as if populated from config)
        with patch.dict(os.environ, {"EDSL_SHOW_FULL_TRACEBACK": "True"}):
            assert TestExampleException._should_show_full_traceback() is True
        
        # Test with env var set to False (as if populated from config)
        with patch.dict(os.environ, {"EDSL_SHOW_FULL_TRACEBACK": "False"}):
            assert TestExampleException._should_show_full_traceback() is False

def test_should_show_full_traceback_default():
    """Test that _should_show_full_traceback falls back to class attribute."""
    # Remove env var to ensure we're testing the class attribute path
    with patch.dict(os.environ, clear=True):
        # Test with suppress_traceback=True (default)
        assert TestExampleException._should_show_full_traceback() is False
        
        # Test with suppress_traceback=False
        original_value = TestExampleException.suppress_traceback
        TestExampleException.suppress_traceback = False
        try:
            assert TestExampleException._should_show_full_traceback() is True
        finally:
            # Restore original value
            TestExampleException.suppress_traceback = original_value

if __name__ == "__main__":
    pytest.main(["-xvs", __file__])