import pytest
from unittest.mock import patch, MagicMock
import requests
import os

#from edsl.coop.PriceFetcher import PriceFetcher
from edsl.coop.price_fetcher import PriceFetcher

class TestPriceFetcher:
    @pytest.fixture
    def mock_response(self):
        """Fixture providing sample price data for testing"""
        return [
            {
                "service": "anthropic",
                "model": "claude-2",
                "token_type": "input",
                "price_per_unit": 0.008,
                "unit": "1K tokens",
            },
            {
                "service": "anthropic",
                "model": "claude-2",
                "token_type": "output",
                "price_per_unit": 0.024,
                "unit": "1K tokens",
            },
        ]

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset the singleton instance before each test"""
        PriceFetcher._instance = None
        yield

    def test_singleton_pattern(self):
        """Test that PriceFetcher maintains singleton behavior"""
        first_instance = PriceFetcher()
        second_instance = PriceFetcher()

        assert first_instance is second_instance

        first_instance._cached_prices = {"test": "data"}
        assert second_instance._cached_prices == {"test": "data"}

    @patch("requests.get")
    def test_successful_price_fetch(self, mock_get, mock_response):
        """Test successful API response and price data processing"""
        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = mock_response
        mock_get.return_value = mock_response_obj

        fetcher = PriceFetcher()
        prices = fetcher.fetch_prices()

        assert ("anthropic", "claude-2") in prices
        assert "input" in prices[("anthropic", "claude-2")]
        assert "output" in prices[("anthropic", "claude-2")]
        assert fetcher._cached_prices is not None
        assert fetcher._cached_prices == prices

    @patch("requests.get")
    def test_error_handling(self, mock_get):
        """Test handling of request exceptions"""
        mock_get.side_effect = requests.RequestException("Connection failed")

        fetcher = PriceFetcher()
        prices = fetcher.fetch_prices()

        assert prices == {}
        assert fetcher._cached_prices is None  # Cache remains None on error

    @patch("requests.get")
    def test_cached_response(self, mock_get, mock_response):
        """Test that cached prices are returned without making new requests"""
        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = mock_response
        mock_get.return_value = mock_response_obj

        fetcher = PriceFetcher()
        first_response = fetcher.fetch_prices()

        mock_get.reset_mock()
        second_response = fetcher.fetch_prices()

        assert mock_get.call_count == 0
        assert first_response == second_response

    @patch("requests.get")
    def test_api_key_handling_with_key(self, mock_get):
        """Test API key header handling with API key present"""
        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = []
        mock_get.return_value = mock_response_obj

        with patch.dict(
            os.environ, {"EXPECTED_PARROT_API_KEY": "test_key"}, clear=True
        ):
            fetcher = PriceFetcher()
            fetcher.fetch_prices()
            actual_headers = mock_get.call_args[1]["headers"]
            assert actual_headers["Authorization"] == "Bearer test_key"

    @patch("requests.get")
    def test_api_key_handling_without_key(self, mock_get):
        """Test API key header handling without API key present"""
        mock_response_obj = MagicMock()
        mock_response_obj.json.return_value = []
        mock_get.return_value = mock_response_obj

        with patch.dict(os.environ, {}, clear=True):  # Ensure environment is empty
            fetcher = PriceFetcher()
            fetcher.fetch_prices()
            actual_headers = mock_get.call_args[1]["headers"]
            assert actual_headers["Authorization"] == "Bearer None"

    def test_invalid_price_data(self, mock_response):
        """Test handling of malformed API response data"""
        invalid_response = [
            {"service": "anthropic"},  # Missing model
            {"model": "claude-2"},  # Missing service
            {},  # Empty entry
        ]

        with patch("requests.get") as mock_get:
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = invalid_response
            mock_get.return_value = mock_response_obj

            fetcher = PriceFetcher()
            prices = fetcher.fetch_prices()

            assert prices == {}
