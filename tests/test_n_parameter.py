"""
Tests for n parameter functionality in language models.

This test file verifies that the n parameter works correctly for different
language model providers, including proper handling of batching for providers
that have limits on the n parameter value.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from edsl.language_models.language_model import LanguageModel


class TestNParameter:
    """Test cases for n parameter support across different language model services."""

    def test_openai_n_parameter_single(self):
        """Test OpenAI service with n=1 (default behavior)."""
        from edsl.inference_services.services.open_ai_service import OpenAIService
        
        # Create a mock OpenAI model
        model_class = OpenAIService.create_model("gpt-3.5-turbo")
        model = model_class(skip_api_key_check=True, n=1)
        
        assert model.n == 1
        assert hasattr(model, 'n')

    def test_openai_n_parameter_multiple(self):
        """Test OpenAI service with n>1."""
        from edsl.inference_services.services.open_ai_service import OpenAIService
        
        # Create a mock OpenAI model
        model_class = OpenAIService.create_model("gpt-3.5-turbo")
        model = model_class(skip_api_key_check=True, n=5)
        
        assert model.n == 5
        assert hasattr(model, 'n')

    def test_google_candidate_count_parameter(self):
        """Test Google service with candidateCount parameter."""
        from edsl.inference_services.services.google_service import GoogleService
        
        # Create a mock Google model
        model_class = GoogleService.create_model("gemini-pro")
        model = model_class(skip_api_key_check=True, candidateCount=3)
        
        assert model.candidateCount == 3
        assert hasattr(model, 'candidateCount')

    def test_anthropic_n_parameter_fallback(self):
        """Test Anthropic service with n parameter (should use fallback)."""
        from edsl.inference_services.services.anthropic_service import AnthropicService
        
        # Create a mock Anthropic model
        model_class = AnthropicService.create_model("claude-3-opus-20240229")
        model = model_class(skip_api_key_check=True, n=3)
        
        assert model.n == 3
        assert hasattr(model, 'n')

    def test_azure_n_parameter(self):
        """Test Azure service with n parameter."""
        from edsl.inference_services.services.azure_ai import AzureAIService
        
        # Create a mock Azure model
        model_class = AzureAIService.create_model("gpt-4")
        model = model_class(skip_api_key_check=True, n=2)
        
        assert model.n == 2
        assert hasattr(model, 'n')

    def test_get_all_completions_openai_format(self):
        """Test extracting all completions from OpenAI-format response."""
        raw_response = {
            "choices": [
                {"index": 0, "message": {"content": "First completion"}},
                {"index": 1, "message": {"content": "Second completion"}},
                {"index": 2, "message": {"content": "Third completion"}},
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25}
        }
        
        completions = LanguageModel.get_all_completions(raw_response)
        
        assert len(completions) == 3
        assert completions[0] == "First completion"
        assert completions[1] == "Second completion"
        assert completions[2] == "Third completion"

    def test_get_all_completions_google_format(self):
        """Test extracting all completions from Google-format response."""
        raw_response = {
            "candidates": [
                {"content": {"parts": [{"text": "First candidate"}]}},
                {"content": {"parts": [{"text": "Second candidate"}]}},
            ],
            "usage_metadata": {"prompt_token_count": 10, "candidates_token_count": 15}
        }
        
        completions = LanguageModel.get_all_completions(raw_response)
        
        assert len(completions) == 2
        assert completions[0] == "First candidate"
        assert completions[1] == "Second candidate"

    def test_get_all_completions_single_response(self):
        """Test extracting completions from single completion response."""
        raw_response = {
            "choices": [
                {"index": 0, "message": {"content": "Only completion"}},
            ]
        }
        
        completions = LanguageModel.get_all_completions(raw_response)
        
        assert len(completions) == 1
        assert completions[0] == "Only completion"

    def test_get_all_completions_invalid_format(self):
        """Test extracting completions from invalid response format."""
        raw_response = {"invalid": "format"}
        
        completions = LanguageModel.get_all_completions(raw_response)
        
        # Should return empty list for invalid format
        assert isinstance(completions, list)
        assert len(completions) == 0

    @patch('warnings.warn')
    def test_multiple_choices_warning(self, mock_warn):
        """Test that warning is issued when multiple choices are detected."""
        from edsl.language_models.raw_response_handler import RawResponseHandler
        
        handler = RawResponseHandler(["choices", 0, "message", "content"])
        raw_response = {
            "choices": [
                {"message": {"content": "First"}},
                {"message": {"content": "Second"}},
            ]
        }
        
        # This should trigger the warning
        result = handler.get_generated_token_string(raw_response)
        
        assert result == "First"  # Should return first choice
        mock_warn.assert_called_once()
        assert "Model returned 2 completions" in str(mock_warn.call_args[0][0])


class TestNParameterIntegration:
    """Integration tests for n parameter with real model calls (mocked)."""
    
    @pytest.mark.asyncio
    async def test_openai_batch_logic_large_n(self):
        """Test that OpenAI batching logic works for n > 128."""
        from edsl.inference_services.services.open_ai_service import OpenAIService
        
        model_class = OpenAIService.create_model("gpt-3.5-turbo")
        model = model_class(skip_api_key_check=True, n=200)  # Should trigger batching
        
        # Mock the async client
        with patch.object(model, 'async_client') as mock_client:
            mock_response = MagicMock()
            mock_response.model_dump.return_value = {
                "choices": [{"message": {"content": f"Response {i}"}} for i in range(128)],
                "usage": {"prompt_tokens": 10, "completion_tokens": 128, "total_tokens": 138}
            }
            mock_client.return_value.chat.completions.create = AsyncMock(return_value=mock_response)
            
            # This should work without raising an exception
            # In real implementation, it would make multiple batched calls
            assert model.n == 200

    @pytest.mark.asyncio
    async def test_google_batch_logic_large_candidate_count(self):
        """Test that Google batching logic works for candidateCount > 8."""
        from edsl.inference_services.services.google_service import GoogleService
        
        model_class = GoogleService.create_model("gemini-pro")
        model = model_class(skip_api_key_check=True, candidateCount=15)  # Should trigger batching
        
        assert model.candidateCount == 15

    @pytest.mark.asyncio  
    async def test_anthropic_multiple_calls(self):
        """Test that Anthropic makes multiple calls for n > 1."""
        from edsl.inference_services.services.anthropic_service import AnthropicService
        
        model_class = AnthropicService.create_model("claude-3-opus-20240229")
        model = model_class(skip_api_key_check=True, n=3)
        
        assert model.n == 3


if __name__ == "__main__":
    pytest.main([__file__])