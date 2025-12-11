"""
Tests for the ScenarioList vibe_filter functionality.

These tests verify that natural language filtering works correctly
for scenario lists across different data types and filtering criteria.
"""

import pytest
from unittest.mock import patch, Mock, MagicMock
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

    @patch('edsl.dataset.vibes.vibe_filter.create_openai_client')
    def test_vibe_filter_numeric_greater_than(self, mock_create_client):
        """Test filtering ScenarioList with numeric greater-than criteria."""
        # Create a fresh mock for this test
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_openai_response("age > 30")

        scenario_list = ScenarioList([
            Scenario({'age': 25, 'occupation': 'student'}),
            Scenario({'age': 35, 'occupation': 'engineer'}),
            Scenario({'age': 28, 'occupation': 'teacher'}),
            Scenario({'age': 42, 'occupation': 'engineer'}),
        ])

        filtered = scenario_list.vibe_filter('Keep only people over 30')

        # Convert Dataset back to list of dicts
        filtered_dicts = filtered.to_dicts()

        assert len(filtered_dicts) == 2
        ages = [s['age'] for s in filtered_dicts]
        assert all(age > 30 for age in ages)
        assert 35 in ages
        assert 42 in ages

    @patch('edsl.dataset.vibes.vibe_filter.create_openai_client')
    def test_vibe_filter_empty_result(self, mock_create_client):
        """Test filtering that returns no results."""
        # Create a fresh mock for this test
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_openai_response("age > 50")

        scenario_list = ScenarioList([
            Scenario({'age': 25, 'name': 'Alice'}),
            Scenario({'age': 28, 'name': 'Bob'}),
        ])

        filtered = scenario_list.vibe_filter('Keep only people over 50')

        # Convert Dataset back to list of dicts
        filtered_dicts = filtered.to_dicts()
        assert len(filtered_dicts) == 0

    @patch('edsl.dataset.vibes.vibe_filter.create_openai_client')
    def test_vibe_filter_compound_criteria(self, mock_create_client):
        """Test filtering with compound AND criteria on ScenarioList."""
        # Create a fresh mock for this test
        mock_client = Mock()
        mock_create_client.return_value = mock_client
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

        # Convert Dataset back to list of dicts
        filtered_dicts = filtered.to_dicts()
        assert len(filtered_dicts) == 1
        assert filtered_dicts[0]['occupation'] == 'engineer'
        assert filtered_dicts[0]['city'] == 'Boston'
        assert filtered_dicts[0]['age'] == 42

    @patch('edsl.dataset.vibes.vibe_filter.create_openai_client')
    def test_vibe_filter_show_expression(self, mock_create_client, capsys):
        """Test that show_expression parameter prints the filter expression."""
        # Create a fresh mock for this test
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_openai_response("age > 30")

        scenario_list = ScenarioList([
            Scenario({'age': 25, 'name': 'Alice'}),
        ])

        scenario_list.vibe_filter('Keep only people over 30', show_expression=True)

        captured = capsys.readouterr()
        assert 'Generated filter expression:' in captured.out
        assert 'age' in captured.out

    @patch('edsl.dataset.vibes.vibe_filter.create_openai_client')
    def test_vibe_filter_preserves_all_keys(self, mock_create_client):
        """Test that filtering preserves all keys from original scenarios."""
        # Create a fresh mock for this test
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_openai_response("age > 30")

        scenario_list = ScenarioList([
            Scenario({'age': 25, 'city': 'Boston', 'score': 85}),
            Scenario({'age': 35, 'city': 'NYC', 'score': 92}),
        ])

        filtered = scenario_list.vibe_filter('Keep only people over 30')

        # Convert Dataset back to list of dicts and check all original keys
        filtered_dicts = filtered.to_dicts()
        assert len(filtered_dicts) == 1
        assert 'age' in filtered_dicts[0]
        assert 'city' in filtered_dicts[0]
        assert 'score' in filtered_dicts[0]

    @patch('edsl.dataset.vibes.vibe_filter.create_openai_client')
    def test_vibe_filter_string_criteria(self, mock_create_client):
        """Test filtering with string matching on ScenarioList."""
        # Create a fresh mock for this test
        mock_client = Mock()
        mock_create_client.return_value = mock_client

        # Mock the specific response for this test
        mock_response = mock_openai_response("occupation == 'engineer'")
        mock_client.chat.completions.create.return_value = mock_response

        scenario_list = ScenarioList([
            Scenario({'occupation': 'engineer', 'experience': 5}),
            Scenario({'occupation': 'teacher', 'experience': 10}),
            Scenario({'occupation': 'engineer', 'experience': 3}),
            Scenario({'occupation': 'doctor', 'experience': 8}),
        ])

        filtered = scenario_list.vibe_filter('Only engineers')

        # Convert Dataset back to list of dicts
        filtered_dicts = filtered.to_dicts()
        assert len(filtered_dicts) == 2
        occupations = [s['occupation'] for s in filtered_dicts]
        assert all(occ == 'engineer' for occ in occupations)

    @patch('edsl.dataset.vibes.vibe_filter.create_openai_client')
    def test_vibe_filter_or_criteria(self, mock_create_client):
        """Test filtering with OR criteria on ScenarioList."""
        # Create a fresh mock for this test
        mock_client = Mock()
        mock_create_client.return_value = mock_client
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

        # Convert Dataset back to list of dicts
        filtered_dicts = filtered.to_dicts()
        assert len(filtered_dicts) == 3
        occupations = [s['occupation'] for s in filtered_dicts]
        assert 'engineer' in occupations
        assert 'teacher' in occupations
        assert 'doctor' not in occupations

    @patch('edsl.dataset.vibes.vibe_filter.create_openai_client')
    def test_vibe_filter_negation(self, mock_create_client):
        """Test filtering with negation criteria on ScenarioList."""
        # Create a fresh mock for this test
        mock_client = Mock()
        mock_create_client.return_value = mock_client
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

        # Convert Dataset back to list of dicts
        filtered_dicts = filtered.to_dicts()
        assert len(filtered_dicts) == 2
        occupations = [s['occupation'] for s in filtered_dicts]
        assert 'engineer' not in occupations
        assert 'teacher' in occupations
        assert 'doctor' in occupations


if __name__ == '__main__':
    pytest.main([__file__, '-v'])