"""Tests for Results.long_view() method."""

import unittest
from edsl.results import Results


class TestResultsLongView(unittest.TestCase):
    """Test suite for the long_view method of Results class."""

    def setUp(self):
        """Set up test fixtures."""
        self.results = Results.example()

    def test_long_view_default_behavior(self):
        """Test long_view with default parameters returns indices."""
        lv = self.results.long_view()

        # Check that we get a ScenarioList with rows
        self.assertGreater(len(lv), 0)

        # Check that default columns include indices
        first_row = dict(lv[0])
        self.assertIn('scenario_index', first_row)
        self.assertIn('agent_index', first_row)
        self.assertIn('question_name', first_row)
        self.assertIn('question_text', first_row)
        self.assertIn('answer', first_row)

    def test_long_view_with_scenario_fields(self):
        """Test long_view with scenario_fields parameter."""
        lv = self.results.long_view(scenario_fields=['period'])

        first_row = dict(lv[0])

        # Check that scenario.period is present instead of scenario_index
        self.assertIn('scenario.period', first_row)
        self.assertNotIn('scenario_index', first_row)

        # Check that agent_index is still present (not replaced)
        self.assertIn('agent_index', first_row)

        # Check that the value is populated
        self.assertIsNotNone(first_row['scenario.period'])

    def test_long_view_with_agent_fields(self):
        """Test long_view with agent_fields parameter."""
        lv = self.results.long_view(agent_fields=['traits'])

        first_row = dict(lv[0])

        # Check that agent.traits is present instead of agent_index
        self.assertIn('agent.traits', first_row)
        self.assertNotIn('agent_index', first_row)

        # Check that scenario_index is still present (not replaced)
        self.assertIn('scenario_index', first_row)

        # Check that the value is populated
        self.assertIsNotNone(first_row['agent.traits'])

    def test_long_view_with_multiple_fields(self):
        """Test long_view with both scenario and agent fields."""
        lv = self.results.long_view(
            scenario_fields=['period'],
            agent_fields=['traits']
        )

        first_row = dict(lv[0])

        # Check that both field types are present
        self.assertIn('scenario.period', first_row)
        self.assertIn('agent.traits', first_row)

        # Check that indices are not present
        self.assertNotIn('scenario_index', first_row)
        self.assertNotIn('agent_index', first_row)

        # Standard columns should still be present
        self.assertIn('question_name', first_row)
        self.assertIn('question_text', first_row)
        self.assertIn('answer', first_row)

    def test_long_view_multiple_rows(self):
        """Test that long_view creates multiple rows for multiple questions."""
        lv = self.results.long_view()

        # Results.example() should have multiple questions
        self.assertGreater(len(lv), len(self.results))

        # Check that different rows have different question names
        question_names = set(dict(row)['question_name'] for row in lv)
        self.assertGreater(len(question_names), 1)

    def test_long_view_preserves_values(self):
        """Test that long_view preserves the actual values correctly."""
        lv_default = self.results.long_view()
        lv_fields = self.results.long_view(scenario_fields=['period'])

        # Both should have the same number of rows
        self.assertEqual(len(lv_default), len(lv_fields))

        # Answers should be the same
        answers_default = [dict(row)['answer'] for row in lv_default]
        answers_fields = [dict(row)['answer'] for row in lv_fields]
        self.assertEqual(answers_default, answers_fields)


if __name__ == '__main__':
    unittest.main()
