"""Tests for parameter validation in language models."""

import pytest
import warnings
from unittest.mock import patch
from edsl import Model
from edsl.language_models.parameter_validator import (
    validate_parameters,
    get_valid_parameters,
    COMMON_TYPOS
)


class TestParameterValidation:
    """Test parameter validation functionality."""
    
    def test_valid_parameters_accepted(self):
        """Test that valid parameters are accepted without warnings."""
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # Turn warnings into errors
            # Should not raise any warnings
            validate_parameters(
                {"temperature": 0.5, "max_tokens": 100},
                service_name="openai"
            )
    
    def test_unknown_parameter_warning(self):
        """Test that unknown parameters generate warnings."""
        with pytest.warns(UserWarning, match="Unknown parameters.*unicorn_mode"):
            validate_parameters(
                {"unicorn_mode": True},
                service_name="openai"
            )
    
    def test_typo_detection(self):
        """Test that common typos are detected and suggested."""
        with pytest.warns(UserWarning, match="'temprature' might be a typo.*'temperature'"):
            validate_parameters(
                {"temprature": 0.7},
                service_name="openai"
            )
    
    def test_case_insensitive_suggestion(self):
        """Test that case differences are detected."""
        with pytest.warns(UserWarning, match="'Temperature' might be a typo.*'temperature'"):
            validate_parameters(
                {"Temperature": 0.7},
                service_name="openai"
            )
    
    def test_n_parameter_for_openai(self):
        """Test that n parameter is valid for OpenAI."""
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            # Should not raise any warnings
            validate_parameters(
                {"n": 5, "temperature": 0.5},
                service_name="openai"
            )
    
    def test_service_specific_parameters(self):
        """Test that service-specific parameters are handled correctly."""
        # top_k is valid for Anthropic but not OpenAI
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            validate_parameters(
                {"top_k": 10},
                service_name="anthropic"
            )
        
        with pytest.warns(UserWarning, match="Unknown parameters.*top_k"):
            validate_parameters(
                {"top_k": 10},
                service_name="openai"
            )
    
    def test_internal_parameters_allowed(self):
        """Test that internal EDSL parameters are allowed."""
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            validate_parameters(
                {"canned_response": "test", "skip_api_key_check": True},
                service_name="openai"
            )
    
    def test_strict_mode(self):
        """Test that strict mode raises errors instead of warnings."""
        with pytest.raises(ValueError, match="Unknown parameters.*fake_param"):
            validate_parameters(
                {"fake_param": "value"},
                service_name="openai",
                strict=True
            )
    
    def test_get_valid_parameters(self):
        """Test getting valid parameters for a service."""
        openai_params = get_valid_parameters("openai")
        assert "temperature" in openai_params
        assert "n" in openai_params
        assert "max_tokens" in openai_params
        
        # Internal parameters should also be included
        assert "canned_response" in openai_params
    
    def test_model_integration(self):
        """Test that Model class uses parameter validation."""
        # This should generate a warning about unknown parameter
        with pytest.warns(UserWarning, match="Unknown parameters.*unicorn_mode"):
            m = Model("gpt-4o-mini", service_name="openai", unicorn_mode=True)
        
        # The parameter should still be set (for backward compatibility)
        assert hasattr(m, "unicorn_mode")
        assert m.unicorn_mode == True
    
    def test_typo_in_model(self):
        """Test that Model class detects typos."""
        with pytest.warns(UserWarning, match="'temprature' might be a typo.*'temperature'"):
            m = Model("gpt-4o-mini", service_name="openai", temprature=0.8)
        
        # The typo should still be set as an attribute
        assert hasattr(m, "temprature")
        assert m.temprature == 0.8
    
    def test_temp_abbreviation(self):
        """Test that 'temp' is recognized as abbreviation for temperature."""
        with pytest.warns(UserWarning, match="'temp' might be a typo.*'temperature'"):
            m = Model("gpt-4o-mini", service_name="openai", temp=0.7)
        
        # The abbreviation should still be set as an attribute
        assert hasattr(m, "temp")
        assert m.temp == 0.7


class TestCommonTypos:
    """Test the common typos dictionary."""
    
    def test_temperature_typos(self):
        """Test various temperature typos are in the dictionary."""
        assert "temp" in COMMON_TYPOS
        assert "temprature" in COMMON_TYPOS
        assert "temperture" in COMMON_TYPOS
        assert COMMON_TYPOS["temp"] == "temperature"
        assert COMMON_TYPOS["temprature"] == "temperature"
    
    def test_max_tokens_typos(self):
        """Test various max_tokens typos are in the dictionary."""
        assert "max_token" in COMMON_TYPOS
        assert "maxtoken" in COMMON_TYPOS
        assert "maxtokens" in COMMON_TYPOS
        assert COMMON_TYPOS["max_token"] == "max_tokens"