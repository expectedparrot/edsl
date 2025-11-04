"""
Tests for the vibe_filter functionality.

These tests verify that natural language filtering works correctly
across different data types and filtering criteria.
"""

import pytest
from unittest.mock import patch, Mock
from edsl.dataset import Dataset


def mock_openai_response(filter_expression):
    """Create a mock OpenAI API response with the given filter expression."""
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = f'{{"filter_expression": "{filter_expression}"}}'
    return mock_response


class TestVibeFilterBasic:
    """Test cases for the vibe_filter method - basic functionality."""

    @patch('edsl.dataset.vibes.vibe_filter.OpenAI')
    def test_vibe_filter_numeric_greater_than_with_dataset(self, mock_openai_client):
        """Test filtering Dataset with numeric greater-than criteria."""
        # Mock the OpenAI API response
        mock_client = Mock()
        mock_openai_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_openai_response("age > 30")

        dataset = Dataset([
            {'age': [25, 35, 28, 42]},
            {'occupation': ['student', 'engineer', 'teacher', 'engineer']},
        ])

        filtered = dataset.vibe_filter('Keep only people over 30')

        assert filtered.num_observations() == 2
        ages = filtered.select('age').to_list()
        assert all(age > 30 for age in ages)
        assert 35 in ages
        assert 42 in ages

    @patch('edsl.dataset.vibes.vibe_filter.OpenAI')
    def test_vibe_filter_empty_result(self, mock_openai_client):
        """Test filtering that returns no results."""
        # Mock the OpenAI API response
        mock_client = Mock()
        mock_openai_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_openai_response("age > 50")

        dataset = Dataset([
            {'age': [25, 28]},
            {'name': ['Alice', 'Bob']},
        ])

        filtered = dataset.vibe_filter('Keep only people over 50')

        assert filtered.num_observations() == 0

    @patch('edsl.dataset.vibes.vibe_filter.OpenAI')
    def test_vibe_filter_compound_criteria_with_dataset(self, mock_openai_client):
        """Test filtering with compound AND criteria on Dataset."""
        # Mock the OpenAI API response
        mock_client = Mock()
        mock_openai_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_openai_response(
            "occupation == 'engineer' and city == 'Boston'"
        )

        dataset = Dataset([
            {'age': [25, 35, 28, 42]},
            {'occupation': ['student', 'engineer', 'teacher', 'engineer']},
            {'city': ['Boston', 'SF', 'Boston', 'Boston']},
        ])

        filtered = dataset.vibe_filter('Engineers in Boston')

        assert filtered.num_observations() == 1
        result_dicts = filtered.to_dicts()
        assert result_dicts[0]['occupation'] == 'engineer'
        assert result_dicts[0]['city'] == 'Boston'
        assert result_dicts[0]['age'] == 42

    @patch('edsl.dataset.vibes.vibe_filter.OpenAI')
    def test_vibe_filter_show_expression(self, mock_openai_client, capsys):
        """Test that show_expression parameter prints the filter expression."""
        # Mock the OpenAI API response
        mock_client = Mock()
        mock_openai_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_openai_response("age > 30")

        dataset = Dataset([
            {'age': [25]},
            {'name': ['Alice']},
        ])

        dataset.vibe_filter('Keep only people over 30', show_expression=True)

        captured = capsys.readouterr()
        assert 'Generated filter expression:' in captured.out
        assert 'age' in captured.out

    @patch('edsl.dataset.vibes.vibe_filter.OpenAI')
    def test_vibe_filter_preserves_all_columns(self, mock_openai_client):
        """Test that filtering preserves all columns from original dataset."""
        # Mock the OpenAI API response
        mock_client = Mock()
        mock_openai_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_openai_response("age > 30")

        dataset = Dataset([
            {'age': [25, 35]},
            {'city': ['Boston', 'NYC']},
            {'score': [85, 92]},
        ])

        filtered = dataset.vibe_filter('Keep only people over 30')

        # Should have all original columns
        columns = filtered.relevant_columns()
        assert 'age' in columns
        assert 'city' in columns
        assert 'score' in columns

    @patch('edsl.dataset.vibes.vibe_filter.OpenAI')
    def test_vibe_filter_string_criteria(self, mock_openai_client):
        """Test filtering with string matching on Dataset."""
        # Mock the OpenAI API response
        mock_client = Mock()
        mock_openai_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_openai_response(
            "occupation == 'engineer'"
        )

        dataset = Dataset([
            {'occupation': ['engineer', 'teacher', 'engineer', 'doctor']},
            {'experience': [5, 10, 3, 8]},
        ])

        filtered = dataset.vibe_filter('Only engineers')

        assert filtered.num_observations() == 2
        occupations = filtered.select('occupation').to_list()
        assert all(occ == 'engineer' for occ in occupations)

    @patch('edsl.dataset.vibes.vibe_filter.OpenAI')
    def test_vibe_filter_or_criteria(self, mock_openai_client):
        """Test filtering with OR criteria on Dataset."""
        # Mock the OpenAI API response
        mock_client = Mock()
        mock_openai_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_openai_response(
            "occupation == 'engineer' or occupation == 'teacher'"
        )

        dataset = Dataset([
            {'occupation': ['engineer', 'teacher', 'doctor', 'engineer']},
            {'experience': [5, 10, 3, 2]},
        ])

        filtered = dataset.vibe_filter('Engineers or teachers')

        assert filtered.num_observations() == 3
        occupations = filtered.select('occupation').to_list()
        assert 'engineer' in occupations
        assert 'teacher' in occupations
        assert 'doctor' not in occupations

    @patch('edsl.dataset.vibes.vibe_filter.OpenAI')
    def test_vibe_filter_negation(self, mock_openai_client):
        """Test filtering with negation criteria on Dataset."""
        # Mock the OpenAI API response
        mock_client = Mock()
        mock_openai_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_openai_response(
            "occupation != 'engineer'"
        )

        dataset = Dataset([
            {'occupation': ['engineer', 'teacher', 'engineer', 'doctor']},
        ])

        filtered = dataset.vibe_filter('Remove engineers')

        assert filtered.num_observations() == 2
        occupations = filtered.select('occupation').to_list()
        assert 'engineer' not in occupations
        assert 'teacher' in occupations
        assert 'doctor' in occupations


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
