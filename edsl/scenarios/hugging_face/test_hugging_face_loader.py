"""Tests for Hugging Face dataset loader."""

import pytest
from unittest.mock import patch, MagicMock
from ..scenario_list import ScenarioList
from .loader import from_hugging_face


class TestHuggingFaceLoader:
    """Test cases for Hugging Face dataset loading functionality."""

    def test_missing_datasets_library(self):
        """Test that ImportError is raised when datasets library is not available."""
        with patch("edsl.scenarios.hugging_face.loader.load_dataset", side_effect=ImportError()):
            with pytest.raises(ImportError, match="The 'datasets' library is required"):
                from_hugging_face("test/dataset")

    def test_single_config_dataset(self):
        """Test loading a dataset with a single configuration."""
        # Mock the dataset structure
        mock_dataset = {
            'train': MagicMock()
        }
        mock_df = MagicMock()
        mock_df.to_dict.return_value = [
            {'question': 'What is AI?', 'answer': 'Artificial Intelligence'},
            {'question': 'What is ML?', 'answer': 'Machine Learning'}
        ]
        mock_dataset['train'].to_pandas.return_value = mock_df

        with patch("edsl.scenarios.hugging_face.loader.load_dataset", return_value=mock_dataset):
            with patch("edsl.scenarios.hugging_face.loader.get_dataset_config_names", return_value=['default']):
                result = from_hugging_face("test/single-config")

                assert isinstance(result, ScenarioList)
                assert len(result) == 2
                assert result[0]['question'] == 'What is AI?'
                assert result[1]['question'] == 'What is ML?'

    def test_multiple_configs_no_specification(self):
        """Test that ValueError is raised when dataset has multiple configs but none is specified."""
        with patch("edsl.scenarios.hugging_face.loader.get_dataset_config_names", return_value=['cola', 'sst2', 'mrpc']):
            with pytest.raises(ValueError, match="has multiple configurations"):
                from_hugging_face("glue")

    def test_multiple_configs_with_specification(self):
        """Test loading a dataset with multiple configs when one is specified."""
        # Mock the dataset structure
        mock_dataset = {
            'train': MagicMock()
        }
        mock_df = MagicMock()
        mock_df.to_dict.return_value = [
            {'sentence': 'This is good.', 'label': 1},
        ]
        mock_dataset['train'].to_pandas.return_value = mock_df

        with patch("edsl.scenarios.hugging_face.loader.load_dataset", return_value=mock_dataset):
            with patch("edsl.scenarios.hugging_face.loader.get_dataset_config_names", return_value=['cola', 'sst2']):
                result = from_hugging_face("glue", config_name="cola")

                assert isinstance(result, ScenarioList)
                assert len(result) == 1
                assert result[0]['sentence'] == 'This is good.'

    def test_invalid_config_name(self):
        """Test that ValueError is raised for invalid config name."""
        with patch("edsl.scenarios.hugging_face.loader.get_dataset_config_names", return_value=['cola', 'sst2']):
            with pytest.raises(ValueError, match="Configuration 'invalid' not found"):
                from_hugging_face("glue", config_name="invalid")

    def test_multiple_splits_with_train(self):
        """Test handling of datasets with multiple splits, preferring train split."""
        # Mock the dataset structure
        mock_dataset = {
            'train': MagicMock(),
            'validation': MagicMock(),
            'test': MagicMock()
        }
        mock_df = MagicMock()
        mock_df.to_dict.return_value = [
            {'text': 'Training data', 'label': 0},
        ]
        mock_dataset['train'].to_pandas.return_value = mock_df

        with patch("edsl.scenarios.hugging_face.loader.load_dataset", return_value=mock_dataset):
            with patch("edsl.scenarios.hugging_face.loader.get_dataset_config_names", return_value=['default']):
                result = from_hugging_face("test/multi-split")

                assert isinstance(result, ScenarioList)
                assert result[0]['text'] == 'Training data'

    def test_multiple_splits_without_train(self):
        """Test handling of datasets with multiple splits but no train split."""
        # Mock the dataset structure
        mock_dataset = {
            'validation': MagicMock(),
            'test': MagicMock()
        }
        mock_df = MagicMock()
        mock_df.to_dict.return_value = [
            {'text': 'Validation data', 'label': 0},
        ]
        mock_dataset['validation'].to_pandas.return_value = mock_df

        with patch("edsl.scenarios.hugging_face.loader.load_dataset", return_value=mock_dataset):
            with patch("edsl.scenarios.hugging_face.loader.get_dataset_config_names", return_value=['default']):
                with patch("warnings.warn") as mock_warn:
                    result = from_hugging_face("test/multi-split-no-train")

                    assert isinstance(result, ScenarioList)
                    assert result[0]['text'] == 'Validation data'
                    # Check that warning was issued
                    mock_warn.assert_called_once()

    def test_scenariolist_from_hugging_face_method(self):
        """Test that ScenarioList.from_hugging_face() works correctly."""
        # Mock the dataset structure
        mock_dataset = {
            'train': MagicMock()
        }
        mock_df = MagicMock()
        mock_df.to_dict.return_value = [
            {'question': 'Test question', 'answer': 'Test answer'},
        ]
        mock_dataset['train'].to_pandas.return_value = mock_df

        with patch("edsl.scenarios.hugging_face.loader.load_dataset", return_value=mock_dataset):
            with patch("edsl.scenarios.hugging_face.loader.get_dataset_config_names", return_value=['default']):
                result = ScenarioList.from_hugging_face("test/dataset")

                assert isinstance(result, ScenarioList)
                assert len(result) == 1
                assert result[0]['question'] == 'Test question'