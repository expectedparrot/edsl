"""
Unit tests for the Results Selector module.

This module contains test cases for the Selector class in results_selector.py,
which handles column selection and data extraction for Results objects.
"""

import unittest
from unittest.mock import Mock, patch
from collections import defaultdict

from edsl.results.results_selector import Selector
from edsl.results.exceptions import ResultsColumnNotFoundError


class TestSelector(unittest.TestCase):
    """
    Test suite for the Selector class.
    """
    
    def setUp(self):
        """
        Set up test fixtures and common test data.
        """
        self.known_data_types = ["answer", "agent", "model"]
        
        # Create a mock data_type_to_keys dictionary
        self.data_type_to_keys = defaultdict(list)
        self.data_type_to_keys["answer"] = ["question1", "question2"]
        self.data_type_to_keys["agent"] = ["name", "status", "agent_id"]
        self.data_type_to_keys["model"] = ["model_name", "temperature"]
        
        # Create a mock key_to_data_type dictionary
        self.key_to_data_type = {
            "question1": "answer",
            "question2": "answer",
            "name": "agent",
            "status": "agent",
            "agent_id": "agent",
            "model_name": "model",
            "temperature": "model",
        }
        
        # Mock fetch_list_func to return predictable values
        self.fetch_list_func = Mock()
        self.fetch_list_func.side_effect = lambda data_type, key: [
            f"{data_type}-{key}-val1",
            f"{data_type}-{key}-val2",
        ]
        
        # Mock Results instance with cache and data
        self.mock_results_instance = Mock()
        self.mock_results_instance._fetch_list_cache = {}
        
        # Create mock data rows with sub_dicts structure
        mock_row1 = Mock()
        mock_row1.sub_dicts = {
            "answer": {"question1": "answer-question1-val1", "question2": "answer-question2-val1"},
            "agent": {"name": "agent-name-val1", "status": "agent-status-val1", "agent_id": "agent-agent_id-val1"},
            "model": {"model_name": "model-model_name-val1", "temperature": "model-temperature-val1"}
        }
        
        mock_row2 = Mock()
        mock_row2.sub_dicts = {
            "answer": {"question1": "answer-question1-val2", "question2": "answer-question2-val2"},
            "agent": {"name": "agent-name-val2", "status": "agent-status-val2", "agent_id": "agent-agent_id-val2"},
            "model": {"model_name": "model-model_name-val2", "temperature": "model-temperature-val2"}
        }
        
        self.mock_results_instance.data = [mock_row1, mock_row2]
        
        # Set the __self__ attribute of the mock function
        self.fetch_list_func.__self__ = self.mock_results_instance
        
        # Create a list of available columns
        self.columns = [
            "answer.question1",
            "answer.question2",
            "agent.name",
            "agent.status",
            "agent.agent_id",
            "model.model_name",
            "model.temperature",
        ]
        
        # Create a Selector instance for testing
        self.selector = Selector(
            known_data_types=self.known_data_types,
            data_type_to_keys=self.data_type_to_keys,
            key_to_data_type=self.key_to_data_type,
            fetch_list_func=self.fetch_list_func,
            columns=self.columns,
        )

    def test_init(self):
        """Test that the Selector initializes correctly."""
        self.assertEqual(self.selector.known_data_types, self.known_data_types)
        self.assertEqual(self.selector._data_type_to_keys, self.data_type_to_keys)
        self.assertEqual(self.selector._key_to_data_type, self.key_to_data_type)
        self.assertEqual(self.selector._fetch_list, self.fetch_list_func)
        self.assertEqual(self.selector.columns, self.columns)
        self.assertEqual(self.selector.items_in_order, [])

    def test_normalize_columns_empty(self):
        """Test column normalization with empty input."""
        self.assertEqual(self.selector._normalize_columns([]), ("*.*",))
        self.assertEqual(self.selector._normalize_columns(None), ("*.*",))
        self.assertEqual(self.selector._normalize_columns(("*",)), ("*.*",))

    def test_normalize_columns_list(self):
        """Test column normalization with a list."""
        self.assertEqual(
            self.selector._normalize_columns([["question1", "question2"]]),
            ("question1", "question2")
        )

    def test_normalize_columns_tuple(self):
        """Test column normalization with a tuple."""
        self.assertEqual(
            self.selector._normalize_columns(("question1", "question2")),
            ("question1", "question2")
        )

    def test_find_matching_columns_full_name(self):
        """Test finding columns by fully qualified name."""
        # Test with an exact match
        matches = self.selector._find_matching_columns("answer.question1")
        self.assertEqual(matches, ["answer.question1"])
        
        # Test with a partial match
        matches = self.selector._find_matching_columns("answer.question")
        self.assertEqual(sorted(matches), ["answer.question1", "answer.question2"])
        
        # Test with no match
        matches = self.selector._find_matching_columns("answer.nonexistent")
        self.assertEqual(matches, [])

    def test_find_matching_columns_simple_name(self):
        """Test finding columns by simple name (without data type)."""
        # Test with an exact match
        matches = self.selector._find_matching_columns("question1")
        self.assertEqual(matches, ["question1"])
        
        # Test with a partial match
        matches = self.selector._find_matching_columns("question")
        self.assertEqual(sorted(matches), ["question1", "question2"])
        
        # Test with no match
        matches = self.selector._find_matching_columns("nonexistent")
        self.assertEqual(matches, [])

    def test_validate_matches_success(self):
        """Test validating matches with successful cases."""
        # Single match
        self.selector._validate_matches("question1", ["question1"])
        
        # Wildcard pattern
        self.selector._validate_matches("answer.*", [])

    def test_validate_matches_ambiguous(self):
        """Test validating matches with ambiguous columns."""
        with self.assertRaises(ResultsColumnNotFoundError) as context:
            self.selector._validate_matches("q", ["question1", "question2"])
        
        self.assertIn("ambiguous", str(context.exception).lower())
        self.assertIn("question1", str(context.exception))
        self.assertIn("question2", str(context.exception))

    def test_validate_matches_not_found(self):
        """Test validating matches with non-existent columns."""
        with self.assertRaises(ResultsColumnNotFoundError) as context:
            self.selector._validate_matches("nonexistent", [])
        
        self.assertIn("not found", str(context.exception).lower())

    def test_parse_column_with_dot(self):
        """Test parsing a column name containing a dot."""
        data_type, key = self.selector._parse_column("answer.question1")
        self.assertEqual(data_type, "answer")
        self.assertEqual(key, "question1")

    def test_parse_column_without_dot(self):
        """Test parsing a column name without a dot."""
        data_type, key = self.selector._parse_column("question1")
        self.assertEqual(data_type, "answer")
        self.assertEqual(key, "question1")

    def test_parse_column_key_error(self):
        """Test parsing a non-existent column name."""
        with self.assertRaises(ResultsColumnNotFoundError):
            self.selector._parse_column("nonexistent")

    def test_raise_key_error_with_suggestions(self):
        """Test raising a key error with suggestions for similar keys."""
        with self.assertRaises(ResultsColumnNotFoundError) as context:
            self.selector._raise_key_error("questio1")  # typo: missing 'n'
        
        self.assertIn("did you mean", str(context.exception).lower())
        self.assertIn("question1", str(context.exception))

    def test_raise_key_error_without_suggestions(self):
        """Test raising a key error without any similar keys."""
        with self.assertRaises(ResultsColumnNotFoundError) as context:
            self.selector._raise_key_error("completely_different")
        
        self.assertIn("not found", str(context.exception).lower())
        self.assertNotIn("did you mean", str(context.exception).lower())

    def test_process_column_specific_key(self):
        """Test processing a column with a specific key."""
        to_fetch = defaultdict(list)
        self.selector._process_column("answer", "question1", to_fetch)
        
        self.assertEqual(to_fetch["answer"], ["question1"])
        self.assertEqual(self.selector.items_in_order, ["answer.question1"])

    def test_process_column_wildcard_key(self):
        """Test processing a column with a wildcard key."""
        to_fetch = defaultdict(list)
        self.selector._process_column("answer", "*", to_fetch)
        
        self.assertEqual(sorted(to_fetch["answer"]), ["question1", "question2"])
        self.assertEqual(
            sorted(self.selector.items_in_order), 
            ["answer.question1", "answer.question2"]
        )

    def test_process_column_nonexistent_key(self):
        """Test processing a column with a non-existent key."""
        to_fetch = defaultdict(list)
        
        with self.assertRaises(ResultsColumnNotFoundError) as context:
            self.selector._process_column("answer", "nonexistent", to_fetch)
        
        self.assertIn("not found", str(context.exception).lower())

    def test_get_data_types_to_return_wildcard(self):
        """Test getting data types with a wildcard."""
        data_types = self.selector._get_data_types_to_return("*")
        self.assertEqual(sorted(data_types), sorted(self.known_data_types))

    def test_get_data_types_to_return_specific(self):
        """Test getting data types with a specific data type."""
        data_types = self.selector._get_data_types_to_return("answer")
        self.assertEqual(data_types, ["answer"])

    def test_get_data_types_to_return_nonexistent(self):
        """Test getting data types with a non-existent data type."""
        with self.assertRaises(ResultsColumnNotFoundError) as context:
            self.selector._get_data_types_to_return("nonexistent")
        
        self.assertIn("not found", str(context.exception).lower())
        for dtype in self.known_data_types:
            self.assertIn(dtype, str(context.exception))

    def test_fetch_data(self):
        """Test fetching data for specified columns."""
        # Set up the items_in_order list
        self.selector.items_in_order = ["answer.question1", "agent.name"]
        
        # Create a to_fetch dictionary
        to_fetch = {
            "answer": ["question1"],
            "agent": ["name"],
        }
        
        # Fetch the data
        data = self.selector._fetch_data(to_fetch)
        
        # Verify the structure and contents of the fetched data
        self.assertEqual(len(data), 2)
        self.assertEqual(
            data[0]["answer.question1"], 
            ["answer-question1-val1", "answer-question1-val2"]
        )
        self.assertEqual(
            data[1]["agent.name"], 
            ["agent-name-val1", "agent-name-val2"]
        )

    def test_select_calls_correct_methods(self):
        """Test that select calls the expected internal methods."""
        with patch.object(self.selector, '_normalize_columns') as mock_normalize:
            with patch.object(self.selector, '_get_columns_to_fetch') as mock_get_cols:
                with patch.object(self.selector, '_fetch_data') as mock_fetch:
                    with patch('edsl.dataset.Dataset') as mock_dataset:
                        # Set up the mocks to return expected values
                        mock_normalize.return_value = ('question1',)
                        mock_get_cols.return_value = {'answer': ['question1']}
                        mock_fetch.return_value = [{'answer.question1': ['val1', 'val2']}]
                        
                        # Call select
                        self.selector.select('question1')
                        
                        # Verify the methods were called with expected arguments
                        mock_normalize.assert_called_once_with(('question1',))
                        mock_get_cols.assert_called_once_with(('question1',))
                        mock_fetch.assert_called_once_with({'answer': ['question1']})
                        mock_dataset.assert_called_once_with([{'answer.question1': ['val1', 'val2']}])

    def test_select_multiple_columns(self):
        """Test that select handles multiple columns correctly."""
        with patch.object(self.selector, '_normalize_columns') as mock_normalize:
            with patch.object(self.selector, '_get_columns_to_fetch') as mock_get_cols:
                with patch.object(self.selector, '_fetch_data') as mock_fetch:
                    with patch('edsl.dataset.Dataset') as mock_dataset:
                        # Set up the mocks to return expected values
                        mock_normalize.return_value = ('question1', 'name')
                        mock_get_cols.return_value = {'answer': ['question1'], 'agent': ['name']}
                        mock_data = [
                            {'answer.question1': ['val1']},
                            {'agent.name': ['val2']}
                        ]
                        mock_fetch.return_value = mock_data
                        
                        # Call select with multiple columns
                        self.selector.select('question1', 'name')
                        
                        # Verify the methods were called with expected arguments
                        mock_normalize.assert_called_once_with(('question1', 'name'))
                        mock_get_cols.assert_called_once_with(('question1', 'name'))
                        mock_fetch.assert_called_once_with({'answer': ['question1'], 'agent': ['name']})
                        mock_dataset.assert_called_once_with(mock_data)

    def test_select_wildcard(self):
        """Test that select handles wildcards correctly."""
        with patch.object(self.selector, '_normalize_columns') as mock_normalize:
            with patch.object(self.selector, '_get_columns_to_fetch') as mock_get_cols:
                with patch.object(self.selector, '_fetch_data') as mock_fetch:
                    with patch('edsl.dataset.Dataset') as mock_dataset:
                        # Set up the mocks to return expected values
                        mock_normalize.return_value = ('answer.*',)
                        mock_get_cols.return_value = {'answer': ['question1', 'question2']}
                        mock_data = [
                            {'answer.question1': ['val1']},
                            {'answer.question2': ['val2']}
                        ]
                        mock_fetch.return_value = mock_data
                        
                        # Call select with a wildcard
                        self.selector.select('answer.*')
                        
                        # Verify the methods were called with expected arguments
                        mock_normalize.assert_called_once_with(('answer.*',))
                        mock_get_cols.assert_called_once_with(('answer.*',))
                        mock_fetch.assert_called_once_with({'answer': ['question1', 'question2']})
                        mock_dataset.assert_called_once_with(mock_data)

    def test_select_all(self):
        """Test that select handles the 'select all' case correctly."""
        with patch.object(self.selector, '_normalize_columns') as mock_normalize:
            with patch.object(self.selector, '_get_columns_to_fetch') as mock_get_cols:
                with patch.object(self.selector, '_fetch_data') as mock_fetch:
                    with patch('edsl.dataset.Dataset') as mock_dataset:
                        # Set up the mocks to return expected values
                        mock_normalize.return_value = ('*.*',)
                        
                        # Create a to_fetch dict with all known data types
                        to_fetch = {}
                        for data_type in self.known_data_types:
                            to_fetch[data_type] = self.data_type_to_keys[data_type]
                        
                        mock_get_cols.return_value = to_fetch
                        
                        # Create mock data for all columns
                        mock_data = [
                            {column: [f"mock-{column}-val"]} for column in self.columns
                        ]
                        mock_fetch.return_value = mock_data
                        
                        # Call select with no arguments (select all)
                        self.selector.select()
                        
                        # Verify the methods were called with expected arguments
                        mock_normalize.assert_called_once_with(())
                        mock_get_cols.assert_called_once_with(('*.*',))
                        mock_fetch.assert_called_once_with(to_fetch)
                        mock_dataset.assert_called_once_with(mock_data)

    @patch("edsl.utilities.is_notebook")
    @patch("sys.stderr")
    def test_select_error_handling_notebook(self, mock_stderr, mock_is_notebook):
        """Test error handling in notebook environment."""
        mock_is_notebook.return_value = True
        
        # Mock _get_columns_to_fetch to raise an error
        with patch.object(
            self.selector, 
            '_normalize_columns', 
            side_effect=ResultsColumnNotFoundError("Column 'nonexistent' not found")
        ):
            # This should print an error message and return None
            result = self.selector.select("nonexistent")
            
            # Verify that None was returned
            self.assertIsNone(result)

    @patch("edsl.utilities.is_notebook")
    def test_select_error_handling_non_notebook(self, mock_is_notebook):
        """Test error handling in non-notebook environment."""
        mock_is_notebook.return_value = False

        # Mock _get_columns_to_fetch to raise an error
        with patch.object(
            self.selector,
            '_get_columns_to_fetch',
            side_effect=ResultsColumnNotFoundError("Column 'nonexistent' not found")
        ):
            # This should raise an exception
            with self.assertRaises(ResultsColumnNotFoundError) as context:
                self.selector.select("nonexistent")

            # Verify the error message
            self.assertIn("not found", str(context.exception))

    def test_match_wildcard_pattern_suffix(self):
        """Test wildcard pattern matching with suffix patterns."""
        # Test suffix pattern matching
        candidates = ["question1_cost", "question2_cost", "question1_tokens", "agent_name"]
        matches = self.selector._match_wildcard_pattern("*_cost", candidates)
        expected = ["question1_cost", "question2_cost"]
        self.assertEqual(sorted(matches), sorted(expected))

    def test_match_wildcard_pattern_prefix(self):
        """Test wildcard pattern matching with prefix patterns."""
        # Test prefix pattern matching
        candidates = ["question1_cost", "question1_tokens", "question2_cost", "agent_name"]
        matches = self.selector._match_wildcard_pattern("question1*", candidates)
        expected = ["question1_cost", "question1_tokens"]
        self.assertEqual(sorted(matches), sorted(expected))

    def test_match_wildcard_pattern_prefix_and_suffix(self):
        """Test wildcard pattern matching with both prefix and suffix."""
        # Test prefix and suffix pattern matching
        candidates = ["raw_model.q1_cost", "raw_model.q2_cost", "raw_model.q1_tokens", "other.q1_cost"]
        matches = self.selector._match_wildcard_pattern("raw_model.*_cost", candidates)
        expected = ["raw_model.q1_cost", "raw_model.q2_cost"]
        self.assertEqual(sorted(matches), sorted(expected))

    def test_match_wildcard_pattern_multiple_wildcards(self):
        """Test wildcard pattern matching with multiple wildcards."""
        # Test multiple wildcards
        candidates = ["prefix_middle_suffix", "prefix_other_suffix", "other_middle_suffix", "nomatch"]
        matches = self.selector._match_wildcard_pattern("prefix*suffix", candidates)
        expected = ["prefix_middle_suffix", "prefix_other_suffix"]
        self.assertEqual(sorted(matches), sorted(expected))

    def test_find_matching_columns_wildcard_suffix(self):
        """Test find matching columns with wildcard suffix patterns."""
        # Add some mock columns with cost suffix to test realistic scenario
        self.selector.columns.extend([
            "raw_response_model.question1_cost",
            "raw_response_model.question2_cost",
            "raw_response_model.question1_tokens"
        ])

        # Test suffix wildcard pattern
        matches = self.selector._find_matching_columns("raw_response_model.*_cost")
        expected = ["raw_response_model.question1_cost", "raw_response_model.question2_cost"]
        self.assertEqual(sorted(matches), sorted(expected))

    def test_find_matching_columns_simple_suffix(self):
        """Test find matching columns with simple suffix patterns."""
        # Update the data structures to include cost columns
        self.data_type_to_keys["answer"].extend(["question1_cost", "question2_cost"])
        self.key_to_data_type.update({
            "question1_cost": "answer",
            "question2_cost": "answer"
        })
        # Also need to update the columns list for matching to work
        self.selector.columns.extend([
            "answer.question1_cost",
            "answer.question2_cost"
        ])

        # Test simple suffix pattern
        matches = self.selector._find_matching_columns("*_cost")
        expected = ["question1_cost", "question2_cost"]
        self.assertEqual(sorted(matches), sorted(expected))


if __name__ == "__main__":
    unittest.main()