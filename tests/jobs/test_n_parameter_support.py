"""
Tests for n parameter support in Jobs.run() method.

This implements John Horton's approach: intercepting run(n=...) 
and using native API support for multiple completions.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from edsl.jobs.n_parameter_handler import (
    NParameterHandler, 
    MODEL_N_SUPPORT, 
    ModelNSupport
)
from edsl.jobs.async_interview_runner_n import AsyncInterviewRunnerWithN


class TestNParameterHandler:
    """Test the n parameter handler logic."""
    
    def test_should_use_native_n_openai(self):
        """Test OpenAI model detection for n parameter."""
        mock_model = Mock()
        mock_model._inference_service_ = "openai"
        
        handler = NParameterHandler()
        
        # Should not use for n=1
        assert not handler.should_use_native_n(mock_model, 1)
        
        # Should use for n>1
        assert handler.should_use_native_n(mock_model, 5)
        assert handler.should_use_native_n(mock_model, 128)
    
    def test_should_use_native_n_google(self):
        """Test Google model detection for n parameter."""
        mock_model = Mock()
        mock_model._inference_service_ = "google"
        
        handler = NParameterHandler()
        
        # Should use for n>1 up to 8
        assert handler.should_use_native_n(mock_model, 4)
        assert handler.should_use_native_n(mock_model, 8)
    
    def test_should_not_use_native_n_unsupported(self):
        """Test unsupported models don't use native n."""
        mock_model = Mock()
        mock_model._inference_service_ = "anthropic"
        
        handler = NParameterHandler()
        
        # Should never use native n for Anthropic
        assert not handler.should_use_native_n(mock_model, 5)
        assert not handler.should_use_native_n(mock_model, 100)
    
    def test_get_batching_strategy_openai(self):
        """Test batching strategy for OpenAI."""
        mock_model = Mock()
        mock_model._inference_service_ = "openai"
        
        handler = NParameterHandler()
        
        # n=50 should be single batch
        batches = handler.get_batching_strategy(mock_model, 50)
        assert len(batches) == 1
        assert batches[0] == ("n", 50)
        
        # n=200 should be two batches: 128 + 72
        batches = handler.get_batching_strategy(mock_model, 200)
        assert len(batches) == 2
        assert batches[0] == ("n", 128)
        assert batches[1] == ("n", 72)
    
    def test_get_batching_strategy_google(self):
        """Test batching strategy for Google."""
        mock_model = Mock()
        mock_model._inference_service_ = "google"
        
        handler = NParameterHandler()
        
        # n=4 should be single batch
        batches = handler.get_batching_strategy(mock_model, 4)
        assert len(batches) == 1
        assert batches[0] == ("candidateCount", 4)
        
        # n=20 should be three batches: 8 + 8 + 4
        batches = handler.get_batching_strategy(mock_model, 20)
        assert len(batches) == 3
        assert batches[0] == ("candidateCount", 8)
        assert batches[1] == ("candidateCount", 8)
        assert batches[2] == ("candidateCount", 4)
    
    def test_extract_multiple_completions_openai_style(self):
        """Test extracting completions from OpenAI-style response."""
        handler = NParameterHandler()
        
        # Mock OpenAI-style response
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content=f"Response {i}")) for i in range(5)
        ]
        
        completions = handler.extract_multiple_completions(mock_response, 5)
        assert len(completions) == 5
        assert completions[0] == "Response 0"
        assert completions[4] == "Response 4"
    
    def test_extract_multiple_completions_google_style(self):
        """Test extracting completions from Google-style response."""
        handler = NParameterHandler()
        
        # Mock Google-style response
        mock_response = Mock()
        mock_response.choices = None  # Google doesn't have choices
        mock_response.candidates = [
            Mock(content=Mock(parts=[Mock(text=f"Response {i}")])) 
            for i in range(4)
        ]
        
        completions = handler.extract_multiple_completions(mock_response, 4)
        assert len(completions) == 4
        assert completions[0] == "Response 0"
        assert completions[3] == "Response 3"
    
    def test_extract_multiple_completions_padding(self):
        """Test that missing completions are padded with empty strings."""
        handler = NParameterHandler()
        
        # Mock response with fewer completions than requested
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content="Only one"))
        ]
        
        completions = handler.extract_multiple_completions(mock_response, 5)
        assert len(completions) == 5
        assert completions[0] == "Only one"
        assert all(c == "" for c in completions[1:])


class TestAsyncInterviewRunnerWithN:
    """Test the modified interview runner with n parameter support."""
    
    @pytest.fixture
    def mock_jobs(self):
        """Create mock Jobs object."""
        mock = MagicMock()
        mock.models = []
        mock.generate_interviews = Mock(return_value=[])
        return mock
    
    @pytest.fixture
    def mock_run_config(self):
        """Create mock RunConfig."""
        mock = MagicMock()
        mock.parameters.n = 5
        mock.environment.cache = None
        return mock
    
    def test_runner_initialization(self, mock_jobs, mock_run_config):
        """Test runner initializes with n handler."""
        runner = AsyncInterviewRunnerWithN(mock_jobs, mock_run_config)
        
        assert runner.n_handler is not None
        assert isinstance(runner.n_handler, NParameterHandler)
        assert runner._model_n_support == {}
    
    def test_analyze_model_support(self, mock_run_config):
        """Test model support analysis."""
        # Create mock jobs with mixed models
        mock_jobs = MagicMock()
        
        mock_openai = Mock()
        mock_openai._inference_service_ = "openai"
        
        mock_anthropic = Mock()
        mock_anthropic._inference_service_ = "anthropic"
        
        mock_jobs.models = [mock_openai, mock_anthropic]
        mock_jobs.generate_interviews = Mock(return_value=[])
        
        runner = AsyncInterviewRunnerWithN(mock_jobs, mock_run_config)
        
        # Check support map
        assert mock_openai in runner._model_n_support
        assert mock_anthropic in runner._model_n_support
        
        # OpenAI should have support
        assert runner._model_n_support[mock_openai].supports_n
        assert runner._model_n_support[mock_openai].max_value == 128
        
        # Anthropic should not have support
        assert not runner._model_n_support[mock_anthropic].supports_n
    
    def test_interview_generator_with_n_support(self, mock_run_config):
        """Test interview generation with n parameter optimization."""
        mock_jobs = MagicMock()
        
        # Create mock model with n support
        mock_model = Mock()
        mock_model._inference_service_ = "openai"
        mock_jobs.models = [mock_model]
        
        # Create mock interview
        mock_interview = MagicMock()
        mock_interview.model = mock_model
        mock_interview.duplicate = Mock(return_value=mock_interview)
        mock_interview.cache = None
        
        mock_jobs.generate_interviews = Mock(return_value=[mock_interview])
        
        # Set n=5
        mock_run_config.parameters.n = 5
        
        runner = AsyncInterviewRunnerWithN(mock_jobs, mock_run_config)
        
        # Generate interviews
        interviews = list(runner._create_interview_generator())
        
        # Should only generate 1 interview with n metadata
        assert len(interviews) == 1
        assert interviews[0]._use_native_n is True
        assert interviews[0]._n_value == 5
        assert interviews[0]._n_parameter_name == "n"
    
    def test_interview_generator_without_n_support(self, mock_run_config):
        """Test interview generation falls back to iteration for unsupported models."""
        mock_jobs = MagicMock()
        
        # Create mock model without n support
        mock_model = Mock()
        mock_model._inference_service_ = "anthropic"
        mock_jobs.models = [mock_model]
        
        # Create mock interview
        mock_interview = MagicMock()
        mock_interview.model = mock_model
        mock_interview.duplicate = Mock(return_value=mock_interview)
        mock_interview.cache = None
        
        mock_jobs.generate_interviews = Mock(return_value=[mock_interview])
        
        # Set n=3
        mock_run_config.parameters.n = 3
        
        runner = AsyncInterviewRunnerWithN(mock_jobs, mock_run_config)
        
        # Generate interviews
        interviews = list(runner._create_interview_generator())
        
        # Should generate 3 interviews (traditional iteration)
        assert len(interviews) == 3
        assert all(not hasattr(i, "_use_native_n") or not i._use_native_n 
                  for i in interviews)
    
    def test_interview_generator_batching_large_n(self, mock_run_config):
        """Test interview generation with batching for large n."""
        mock_jobs = MagicMock()
        
        # Create mock model with n support
        mock_model = Mock()
        mock_model._inference_service_ = "openai"
        mock_jobs.models = [mock_model]
        
        # Create mock interview
        mock_interview = MagicMock()
        mock_interview.model = mock_model
        
        # Track duplicate calls
        duplicate_calls = []
        def track_duplicate(iteration=0, cache=None):
            dup = MagicMock()
            dup.model = mock_model
            duplicate_calls.append((iteration, cache))
            return dup
        
        mock_interview.duplicate = Mock(side_effect=track_duplicate)
        mock_interview.cache = None
        
        mock_jobs.generate_interviews = Mock(return_value=[mock_interview])
        
        # Set n=200 (exceeds OpenAI limit of 128)
        mock_run_config.parameters.n = 200
        
        runner = AsyncInterviewRunnerWithN(mock_jobs, mock_run_config)
        
        # Generate interviews
        interviews = list(runner._create_interview_generator())
        
        # Should generate 2 batched interviews (128 + 72)
        assert len(interviews) == 2
        
        # First batch should be 128
        assert interviews[0]._use_native_n is True
        assert interviews[0]._n_value == 128
        
        # Second batch should be 72
        assert interviews[1]._use_native_n is True
        assert interviews[1]._n_value == 72


class TestModelNSupport:
    """Test ModelNSupport dataclass."""
    
    def test_model_n_support_creation(self):
        """Test creating ModelNSupport instances."""
        support = ModelNSupport(
            supports_n=True,
            parameter_name="n",
            max_value=128
        )
        
        assert support.supports_n is True
        assert support.parameter_name == "n"
        assert support.max_value == 128
    
    def test_model_n_support_registry(self):
        """Test the MODEL_N_SUPPORT registry."""
        # Check OpenAI
        assert "openai" in MODEL_N_SUPPORT
        assert MODEL_N_SUPPORT["openai"].supports_n is True
        assert MODEL_N_SUPPORT["openai"].parameter_name == "n"
        assert MODEL_N_SUPPORT["openai"].max_value == 128
        
        # Check Google
        assert "google" in MODEL_N_SUPPORT
        assert MODEL_N_SUPPORT["google"].supports_n is True
        assert MODEL_N_SUPPORT["google"].parameter_name == "candidateCount"
        assert MODEL_N_SUPPORT["google"].max_value == 8
        
        # Check Anthropic (no support)
        assert "anthropic" in MODEL_N_SUPPORT
        assert MODEL_N_SUPPORT["anthropic"].supports_n is False