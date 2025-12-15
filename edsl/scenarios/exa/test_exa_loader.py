"""
Tests for EXA API integration with EDSL ScenarioLists.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from edsl.scenarios.exa import from_exa, from_exa_webset


class TestExaLoader:
    """Test cases for EXA loader functions."""

    def test_import_error_handling(self):
        """Test that appropriate error is raised when exa-py is not available."""
        with patch.dict('sys.modules', {'exa_py': None}):
            with pytest.raises(ImportError, match="The 'exa-py' library is required"):
                from_exa("test query")

    def test_missing_api_key_error(self):
        """Test that appropriate error is raised when API key is missing."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('edsl.scenarios.exa.loader.Exa'):
                with pytest.raises(ValueError, match="EXA API key is required"):
                    from_exa("test query")

    def test_api_key_from_environment(self):
        """Test that API key is correctly loaded from environment."""
        mock_exa_class = MagicMock()
        mock_exa_instance = MagicMock()
        mock_exa_class.return_value = mock_exa_instance

        # Mock webset creation
        mock_webset = MagicMock()
        mock_webset.results = [{"test": "result1"}, {"test": "result2"}]
        mock_exa_instance.websets.create.return_value = mock_webset

        with patch.dict(os.environ, {'EXA_API_KEY': 'test-key'}):
            with patch('edsl.scenarios.exa.loader.Exa', mock_exa_class):
                with patch('edsl.scenarios.exa.loader.CreateWebsetParameters'):
                    scenarios = from_exa("test query", count=10)

                    # Verify EXA was initialized with correct API key
                    mock_exa_class.assert_called_once_with('test-key')

                    # Verify ScenarioList was created
                    assert len(scenarios) == 2

    def test_api_key_from_parameter(self):
        """Test that API key can be passed as parameter."""
        mock_exa_class = MagicMock()
        mock_exa_instance = MagicMock()
        mock_exa_class.return_value = mock_exa_instance

        mock_webset = MagicMock()
        mock_webset.results = [{"test": "result"}]
        mock_exa_instance.websets.create.return_value = mock_webset

        with patch('edsl.scenarios.exa.loader.Exa', mock_exa_class):
            with patch('edsl.scenarios.exa.loader.CreateWebsetParameters'):
                scenarios = from_exa("test query", api_key="param-key")

                # Verify EXA was initialized with parameter key
                mock_exa_class.assert_called_once_with('param-key')

    def test_enrichment_validation(self):
        """Test that enrichments are properly validated."""
        with patch.dict(os.environ, {'EXA_API_KEY': 'test-key'}):
            with patch('edsl.scenarios.exa.loader.Exa'):
                # Test invalid enrichment format
                with pytest.raises(ValueError, match="Each enrichment must be a dictionary"):
                    from_exa("test query", enrichments=["invalid_enrichment"])

                # Test missing required keys
                with pytest.raises(ValueError, match="Each enrichment must have a 'description' key"):
                    from_exa("test query", enrichments=[{"format": "text"}])

                with pytest.raises(ValueError, match="Each enrichment must have a 'format' key"):
                    from_exa("test query", enrichments=[{"description": "test"}])

    def test_webset_parameters_construction(self):
        """Test that webset parameters are correctly constructed."""
        mock_exa_class = MagicMock()
        mock_exa_instance = MagicMock()
        mock_exa_class.return_value = mock_exa_instance

        mock_webset = MagicMock()
        mock_webset.results = [{"test": "result"}]
        mock_exa_instance.websets.create.return_value = mock_webset

        mock_params_class = MagicMock()

        with patch.dict(os.environ, {'EXA_API_KEY': 'test-key'}):
            with patch('edsl.scenarios.exa.loader.Exa', mock_exa_class):
                with patch('edsl.scenarios.exa.loader.CreateWebsetParameters', mock_params_class):
                    from_exa(
                        query="test query",
                        criteria=["criteria1", "criteria2"],
                        count=50,
                        enrichments=[
                            {"description": "experience", "format": "number"},
                            {"description": "university", "format": "text"}
                        ]
                    )

                    # Verify CreateWebsetParameters was called with correct structure
                    mock_params_class.assert_called_once()
                    call_args = mock_params_class.call_args[1]

                    assert call_args['search']['query'] == "test query"
                    assert call_args['search']['count'] == 50
                    assert call_args['search']['criteria'] == ["criteria1", "criteria2"]
                    assert len(call_args['enrichments']) == 2

    def test_empty_results_handling(self):
        """Test handling when EXA returns no results."""
        mock_exa_class = MagicMock()
        mock_exa_instance = MagicMock()
        mock_exa_class.return_value = mock_exa_instance

        # Mock empty webset
        mock_webset = MagicMock()
        mock_webset.results = []
        mock_exa_instance.websets.create.return_value = mock_webset

        with patch.dict(os.environ, {'EXA_API_KEY': 'test-key'}):
            with patch('edsl.scenarios.exa.loader.Exa', mock_exa_class):
                with patch('edsl.scenarios.exa.loader.CreateWebsetParameters'):
                    scenarios = from_exa("test query")

                    # Should create ScenarioList with metadata even if no results
                    assert len(scenarios) == 1
                    assert scenarios[0]['exa_query'] == "test query"
                    assert scenarios[0]['exa_results_count'] == 0

    def test_from_exa_webset_function(self):
        """Test the from_exa_webset function."""
        mock_exa_class = MagicMock()
        mock_exa_instance = MagicMock()
        mock_exa_class.return_value = mock_exa_instance

        mock_webset = MagicMock()
        mock_webset.results = [{"webset_result": "data"}]
        mock_exa_instance.websets.get.return_value = mock_webset

        with patch.dict(os.environ, {'EXA_API_KEY': 'test-key'}):
            with patch('edsl.scenarios.exa.loader.Exa', mock_exa_class):
                scenarios = from_exa_webset("test_webset_id")

                # Verify get method was called with correct ID
                mock_exa_instance.websets.get.assert_called_once_with("test_webset_id")

                # Verify ScenarioList was created with webset ID
                assert len(scenarios) == 1
                assert scenarios[0]['exa_webset_id'] == "test_webset_id"

    def test_runtime_error_on_api_failure(self):
        """Test that RuntimeError is raised when EXA API call fails."""
        mock_exa_class = MagicMock()
        mock_exa_instance = MagicMock()
        mock_exa_class.return_value = mock_exa_instance

        # Mock API failure
        mock_exa_instance.websets.create.side_effect = Exception("API Error")

        with patch.dict(os.environ, {'EXA_API_KEY': 'test-key'}):
            with patch('edsl.scenarios.exa.loader.Exa', mock_exa_class):
                with patch('edsl.scenarios.exa.loader.CreateWebsetParameters'):
                    with pytest.raises(RuntimeError, match="Failed to create EXA webset: API Error"):
                        from_exa("test query")


class TestScenarioListIntegration:
    """Test integration with ScenarioList class methods."""

    def test_scenario_list_from_exa_method(self):
        """Test that ScenarioList.from_exa method works."""
        from edsl.scenarios.scenario_list import ScenarioList

        mock_exa_class = MagicMock()
        mock_exa_instance = MagicMock()
        mock_exa_class.return_value = mock_exa_instance

        mock_webset = MagicMock()
        mock_webset.results = [{"test": "scenario"}]
        mock_exa_instance.websets.create.return_value = mock_webset

        with patch.dict(os.environ, {'EXA_API_KEY': 'test-key'}):
            with patch('edsl.scenarios.exa.loader.Exa', mock_exa_class):
                with patch('edsl.scenarios.exa.loader.CreateWebsetParameters'):
                    scenarios = ScenarioList.from_exa("test query")

                    # Should return ScenarioList instance
                    assert isinstance(scenarios, ScenarioList)
                    assert len(scenarios) == 1

    def test_scenario_list_from_exa_webset_method(self):
        """Test that ScenarioList.from_exa_webset method works."""
        from edsl.scenarios.scenario_list import ScenarioList

        mock_exa_class = MagicMock()
        mock_exa_instance = MagicMock()
        mock_exa_class.return_value = mock_exa_instance

        mock_webset = MagicMock()
        mock_webset.results = [{"webset": "data"}]
        mock_exa_instance.websets.get.return_value = mock_webset

        with patch.dict(os.environ, {'EXA_API_KEY': 'test-key'}):
            with patch('edsl.scenarios.exa.loader.Exa', mock_exa_class):
                scenarios = ScenarioList.from_exa_webset("test_id")

                assert isinstance(scenarios, ScenarioList)
                assert len(scenarios) == 1


if __name__ == "__main__":
    # Run basic tests if pytest is not available
    print("Running basic EXA loader tests...")

    try:
        # Test import
        from edsl.scenarios.exa import from_exa, from_exa_webset
        print("✓ Import successful")

        # Test error handling without dependencies
        try:
            with patch.dict('sys.modules', {'exa_py': None}):
                from_exa("test")
        except ImportError as e:
            if "exa-py" in str(e):
                print("✓ Import error handling works")

        # Test missing API key error
        try:
            with patch.dict(os.environ, {}, clear=True):
                from_exa("test")
        except ValueError as e:
            if "API key" in str(e):
                print("✓ API key validation works")

        print("Basic tests passed!")

    except Exception as e:
        print(f"Test failed: {e}")
        raise