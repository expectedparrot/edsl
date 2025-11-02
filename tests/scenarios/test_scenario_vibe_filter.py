"""
Tests for the ScenarioList vibe_filter functionality.

These tests verify that natural language filtering works correctly
for scenario lists across different data types and filtering criteria.
"""

import pytest
from unittest.mock import patch, Mock
from edsl.scenarios import Scenario, ScenarioList


def mock_openai_response(filter_expression):
    """Create a mock OpenAI API response with the given filter expression."""
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = f'{{"filter_expression": "{filter_expression}"}}'
    return mock_response


class TestScenarioListVibeFilterBasic:
    """Test cases for the vibe_filter method on ScenarioList - basic functionality."""

    @patch('edsl.scenarios.vibes.vibe_filter.OpenAI')
    def test_vibe_filter_numeric_greater_than(self, mock_openai_client):
        """Test filtering ScenarioList with numeric greater-than criteria."""
        # Mock the OpenAI API response
        mock_client = Mock()
        mock_openai_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_openai_response("age > 30")

        scenario_list = ScenarioList([
            Scenario({'age': 25, 'occupation': 'student'}),
            Scenario({'age': 35, 'occupation': 'engineer'}),
            Scenario({'age': 28, 'occupation': 'teacher'}),
            Scenario({'age': 42, 'occupation': 'engineer'}),
        ])

        filtered = scenario_list.vibe_filter('Keep only people over 30')

        assert len(filtered) == 2
        ages = [s['age'] for s in filtered]
        assert all(age > 30 for age in ages)
        assert 35 in ages
        assert 42 in ages

    @patch('edsl.scenarios.vibes.vibe_filter.OpenAI')
    def test_vibe_filter_empty_result(self, mock_openai_client):
        """Test filtering that returns no results."""
        # Mock the OpenAI API response
        mock_client = Mock()
        mock_openai_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_openai_response("age > 50")

        scenario_list = ScenarioList([
            Scenario({'age': 25, 'name': 'Alice'}),
            Scenario({'age': 28, 'name': 'Bob'}),
        ])

        filtered = scenario_list.vibe_filter('Keep only people over 50')

        assert len(filtered) == 0

    @patch('edsl.scenarios.vibes.vibe_filter.OpenAI')
    def test_vibe_filter_compound_criteria(self, mock_openai_client):
        """Test filtering with compound AND criteria on ScenarioList."""
        # Mock the OpenAI API response
        mock_client = Mock()
        mock_openai_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_openai_response(
            "occupation == 'engineer' and city == 'Boston'"
        )

        scenario_list = ScenarioList([
            Scenario({'age': 25, 'occupation': 'student', 'city': 'Boston'}),
            Scenario({'age': 35, 'occupation': 'engineer', 'city': 'SF'}),
            Scenario({'age': 28, 'occupation': 'teacher', 'city': 'Boston'}),
            Scenario({'age': 42, 'occupation': 'engineer', 'city': 'Boston'}),
        ])

        filtered = scenario_list.vibe_filter('Engineers in Boston')

        assert len(filtered) == 1
        assert filtered[0]['occupation'] == 'engineer'
        assert filtered[0]['city'] == 'Boston'
        assert filtered[0]['age'] == 42

    @patch('edsl.scenarios.vibes.vibe_filter.OpenAI')
    def test_vibe_filter_show_expression(self, mock_openai_client, capsys):
        """Test that show_expression parameter prints the filter expression."""
        # Mock the OpenAI API response
        mock_client = Mock()
        mock_openai_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_openai_response("age > 30")

        scenario_list = ScenarioList([
            Scenario({'age': 25, 'name': 'Alice'}),
        ])

        scenario_list.vibe_filter('Keep only people over 30', show_expression=True)

        captured = capsys.readouterr()
        assert 'Generated filter expression:' in captured.out
        assert 'age' in captured.out

    @patch('edsl.scenarios.vibes.vibe_filter.OpenAI')
    def test_vibe_filter_preserves_all_keys(self, mock_openai_client):
        """Test that filtering preserves all keys from original scenarios."""
        # Mock the OpenAI API response
        mock_client = Mock()
        mock_openai_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_openai_response("age > 30")

        scenario_list = ScenarioList([
            Scenario({'age': 25, 'city': 'Boston', 'score': 85}),
            Scenario({'age': 35, 'city': 'NYC', 'score': 92}),
        ])

        filtered = scenario_list.vibe_filter('Keep only people over 30')

        # Should have all original keys
        assert len(filtered) == 1
        assert 'age' in filtered[0]
        assert 'city' in filtered[0]
        assert 'score' in filtered[0]

    @patch('edsl.scenarios.vibes.vibe_filter.OpenAI')
    def test_vibe_filter_string_criteria(self, mock_openai_client):
        """Test filtering with string matching on ScenarioList."""
        # Mock the OpenAI API response
        mock_client = Mock()
        mock_openai_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_openai_response(
            "occupation == 'engineer'"
        )

        scenario_list = ScenarioList([
            Scenario({'occupation': 'engineer', 'experience': 5}),
            Scenario({'occupation': 'teacher', 'experience': 10}),
            Scenario({'occupation': 'engineer', 'experience': 3}),
            Scenario({'occupation': 'doctor', 'experience': 8}),
        ])

        filtered = scenario_list.vibe_filter('Only engineers')

        assert len(filtered) == 2
        occupations = [s['occupation'] for s in filtered]
        assert all(occ == 'engineer' for occ in occupations)

    @patch('edsl.scenarios.vibes.vibe_filter.OpenAI')
    def test_vibe_filter_or_criteria(self, mock_openai_client):
        """Test filtering with OR criteria on ScenarioList."""
        # Mock the OpenAI API response
        mock_client = Mock()
        mock_openai_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_openai_response(
            "occupation == 'engineer' or occupation == 'teacher'"
        )

        scenario_list = ScenarioList([
            Scenario({'occupation': 'engineer', 'experience': 5}),
            Scenario({'occupation': 'teacher', 'experience': 10}),
            Scenario({'occupation': 'doctor', 'experience': 3}),
            Scenario({'occupation': 'engineer', 'experience': 2}),
        ])

        filtered = scenario_list.vibe_filter('Engineers or teachers')

        assert len(filtered) == 3
        occupations = [s['occupation'] for s in filtered]
        assert 'engineer' in occupations
        assert 'teacher' in occupations
        assert 'doctor' not in occupations

    @patch('edsl.scenarios.vibes.vibe_filter.OpenAI')
    def test_vibe_filter_negation(self, mock_openai_client):
        """Test filtering with negation criteria on ScenarioList."""
        # Mock the OpenAI API response
        mock_client = Mock()
        mock_openai_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_openai_response(
            "occupation != 'engineer'"
        )

        scenario_list = ScenarioList([
            Scenario({'occupation': 'engineer'}),
            Scenario({'occupation': 'teacher'}),
            Scenario({'occupation': 'engineer'}),
            Scenario({'occupation': 'doctor'}),
        ])

        filtered = scenario_list.vibe_filter('Remove engineers')

        assert len(filtered) == 2
        occupations = [s['occupation'] for s in filtered]
        assert 'engineer' not in occupations
        assert 'teacher' in occupations
        assert 'doctor' in occupations


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
