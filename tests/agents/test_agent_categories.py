"""Tests for Agent and AgentList trait categories functionality."""

import unittest
from edsl.agents import Agent, AgentList
from edsl.agents.exceptions import AgentErrors


class TestAgentCategories(unittest.TestCase):
    """Test Agent.with_categories() method."""

    def setUp(self):
        """Set up test fixtures."""
        # Create an agent with multiple traits and categories
        self.agent = Agent(traits={
            'age': 30,
            'hometown': 'Boston',
            'food': 'beans',
            'height': 5.9,
            'occupation': 'Engineer'
        })
        self.agent.add_category('demographics', ['age', 'hometown'])
        self.agent.add_category('preferences', ['food'])
        self.agent.add_category('physical', ['height'])

    def test_agent_with_single_category(self):
        """Test filtering agent to a single category."""
        demographics_agent = self.agent.with_categories('demographics')

        # Should only have traits in the demographics category
        self.assertEqual(set(demographics_agent.traits.keys()), {'age', 'hometown'})
        self.assertEqual(demographics_agent.traits['age'], 30)
        self.assertEqual(demographics_agent.traits['hometown'], 'Boston')

    def test_agent_with_multiple_categories(self):
        """Test filtering agent to multiple categories."""
        filtered_agent = self.agent.with_categories('demographics', 'preferences')

        # Should have traits from both categories
        self.assertEqual(
            set(filtered_agent.traits.keys()),
            {'age', 'hometown', 'food'}
        )
        self.assertEqual(filtered_agent.traits['age'], 30)
        self.assertEqual(filtered_agent.traits['hometown'], 'Boston')
        self.assertEqual(filtered_agent.traits['food'], 'beans')

    def test_agent_with_all_categories(self):
        """Test filtering agent with all categories."""
        all_categories = self.agent.with_categories('demographics', 'preferences', 'physical')

        # Should have all traits that are categorized
        self.assertEqual(
            set(all_categories.traits.keys()),
            {'age', 'hometown', 'food', 'height'}
        )

    def test_agent_with_nonexistent_category(self):
        """Test that requesting a non-existent category raises an error."""
        with self.assertRaises(AgentErrors) as context:
            self.agent.with_categories('nonexistent')

        self.assertIn('nonexistent', str(context.exception))
        self.assertIn('not found', str(context.exception).lower())

    def test_agent_with_categories_preserves_original(self):
        """Test that with_categories doesn't modify the original agent."""
        original_traits = set(self.agent.traits.keys())

        # Create a filtered agent
        filtered_agent = self.agent.with_categories('demographics')

        # Original should be unchanged
        self.assertEqual(set(self.agent.traits.keys()), original_traits)
        self.assertIn('food', self.agent.traits)
        self.assertNotIn('food', filtered_agent.traits)

    def test_agent_add_category(self):
        """Test adding a category to an agent."""
        agent = Agent(traits={'x': 1, 'y': 2, 'z': 3})

        # Add a category
        agent.add_category('coords', ['x', 'y'])

        # Check category was added
        self.assertIn('coords', agent.trait_categories)
        self.assertEqual(set(agent.trait_categories['coords']), {'x', 'y'})

        # Use the category
        coords_only = agent.with_categories('coords')
        self.assertEqual(set(coords_only.traits.keys()), {'x', 'y'})

    def test_agent_add_category_with_invalid_trait(self):
        """Test that adding a category with an invalid trait raises an error."""
        agent = Agent(traits={'x': 1, 'y': 2})

        with self.assertRaises(AgentErrors) as context:
            agent.add_category('test', ['x', 'invalid_trait'])

        self.assertIn('invalid_trait', str(context.exception))
        self.assertIn('not found', str(context.exception).lower())

    def test_agent_empty_category(self):
        """Test creating an empty category."""
        agent = Agent(traits={'x': 1, 'y': 2})
        agent.add_category('empty')

        # Should work but return an agent with no traits
        empty_agent = agent.with_categories('empty')
        self.assertEqual(empty_agent.traits, {})


class TestAgentListCategories(unittest.TestCase):
    """Test AgentList.with_categories() method."""

    def setUp(self):
        """Set up test fixtures."""
        # Create multiple agents with categories
        self.agent1 = Agent(
            name='Alice',
            traits={'age': 30, 'hometown': 'Boston', 'food': 'beans', 'height': 5.5}
        )
        self.agent1.add_category('demographics', ['age', 'hometown'])
        self.agent1.add_category('preferences', ['food'])
        self.agent1.add_category('physical', ['height'])

        self.agent2 = Agent(
            name='Bob',
            traits={'age': 25, 'hometown': 'SF', 'food': 'sushi', 'height': 6.0}
        )
        self.agent2.add_category('demographics', ['age', 'hometown'])
        self.agent2.add_category('preferences', ['food'])
        self.agent2.add_category('physical', ['height'])

        self.agent3 = Agent(
            name='Charlie',
            traits={'age': 35, 'hometown': 'NYC', 'food': 'pizza', 'height': 5.8}
        )
        self.agent3.add_category('demographics', ['age', 'hometown'])
        self.agent3.add_category('preferences', ['food'])
        self.agent3.add_category('physical', ['height'])

        self.agent_list = AgentList([self.agent1, self.agent2, self.agent3])

    def test_agent_list_with_single_category(self):
        """Test filtering agent list to a single category."""
        demographics_list = self.agent_list.with_categories('demographics')

        # Check that we get an AgentList back
        self.assertIsInstance(demographics_list, AgentList)

        # Check that we have the same number of agents
        self.assertEqual(len(demographics_list), 3)

        # Check that each agent has only demographics traits
        for agent in demographics_list:
            self.assertEqual(set(agent.traits.keys()), {'age', 'hometown'})

        # Check specific values
        self.assertEqual(demographics_list[0].traits['age'], 30)
        self.assertEqual(demographics_list[0].traits['hometown'], 'Boston')
        self.assertEqual(demographics_list[1].traits['age'], 25)
        self.assertEqual(demographics_list[1].traits['hometown'], 'SF')

    def test_agent_list_with_multiple_categories(self):
        """Test filtering agent list to multiple categories."""
        filtered_list = self.agent_list.with_categories('demographics', 'preferences')

        # Check that we get an AgentList back
        self.assertIsInstance(filtered_list, AgentList)

        # Check that each agent has traits from both categories
        for agent in filtered_list:
            self.assertEqual(
                set(agent.traits.keys()),
                {'age', 'hometown', 'food'}
            )

        # Check specific values for first agent
        self.assertEqual(filtered_list[0].traits['age'], 30)
        self.assertEqual(filtered_list[0].traits['hometown'], 'Boston')
        self.assertEqual(filtered_list[0].traits['food'], 'beans')

        # Check that height is not included
        for agent in filtered_list:
            self.assertNotIn('height', agent.traits)

    def test_agent_list_with_categories_preserves_original(self):
        """Test that with_categories doesn't modify the original agent list."""
        # Get original trait counts
        original_trait_counts = [len(agent.traits) for agent in self.agent_list]

        # Create filtered list
        filtered_list = self.agent_list.with_categories('demographics')

        # Original should be unchanged
        current_trait_counts = [len(agent.traits) for agent in self.agent_list]
        self.assertEqual(original_trait_counts, current_trait_counts)

        # Filtered list should have fewer traits
        filtered_trait_counts = [len(agent.traits) for agent in filtered_list]
        for filtered_count, original_count in zip(filtered_trait_counts, original_trait_counts):
            self.assertLess(filtered_count, original_count)

    def test_agent_list_with_nonexistent_category(self):
        """Test that requesting a non-existent category raises an error."""
        with self.assertRaises(AgentErrors):
            self.agent_list.with_categories('nonexistent')

    def test_agent_list_with_categories_preserves_names(self):
        """Test that agent names are preserved when filtering categories."""
        filtered_list = self.agent_list.with_categories('preferences')

        # Check that names are preserved
        self.assertEqual(filtered_list[0].name, 'Alice')
        self.assertEqual(filtered_list[1].name, 'Bob')
        self.assertEqual(filtered_list[2].name, 'Charlie')

    def test_agent_list_empty(self):
        """Test with_categories on an empty AgentList."""
        empty_list = AgentList([])
        result = empty_list.with_categories('any_category')

        self.assertIsInstance(result, AgentList)
        self.assertEqual(len(result), 0)

    def test_agent_list_with_all_categories(self):
        """Test filtering with all available categories."""
        all_categories = self.agent_list.with_categories('demographics', 'preferences', 'physical')

        # Should have all original traits (that are categorized)
        for i, agent in enumerate(all_categories):
            self.assertEqual(
                set(agent.traits.keys()),
                {'age', 'hometown', 'food', 'height'}
            )

    def test_agent_list_with_categories_integration(self):
        """Test integration with other AgentList methods."""
        # Filter by category, then use other methods
        demographics = self.agent_list.with_categories('demographics')

        # Test select works on filtered list
        age_only = demographics.select('age')
        for agent in age_only:
            self.assertEqual(set(agent.traits.keys()), {'age'})

        # Test filter works on filtered list
        young = demographics.filter('age < 30')
        self.assertEqual(len(young), 1)
        self.assertEqual(young[0].traits['age'], 25)

    def test_agent_list_inconsistent_categories(self):
        """Test handling agents with different category structures."""
        # Create agents with different categories
        agent_a = Agent(traits={'x': 1, 'y': 2, 'z': 3})
        agent_a.add_category('group1', ['x', 'y'])

        agent_b = Agent(traits={'x': 4, 'y': 5, 'z': 6})
        agent_b.add_category('group1', ['x'])  # Different traits in same category

        agent_list = AgentList([agent_a, agent_b])

        # This should work - each agent uses its own categories
        result = agent_list.with_categories('group1')

        # First agent should have x and y
        self.assertEqual(set(result[0].traits.keys()), {'x', 'y'})

        # Second agent should only have x
        self.assertEqual(set(result[1].traits.keys()), {'x'})


class TestAgentListCategoriesEdgeCases(unittest.TestCase):
    """Test edge cases for AgentList.with_categories()."""

    def test_single_agent_in_list(self):
        """Test with_categories on a single-agent list."""
        agent = Agent(traits={'a': 1, 'b': 2})
        agent.add_category('test', ['a'])

        agent_list = AgentList([agent])
        filtered = agent_list.with_categories('test')

        self.assertEqual(len(filtered), 1)
        self.assertEqual(set(filtered[0].traits.keys()), {'a'})

    def test_chaining_with_categories(self):
        """Test chaining multiple with_categories calls."""
        agent = Agent(traits={'a': 1, 'b': 2, 'c': 3, 'd': 4})
        agent.add_category('cat1', ['a', 'b', 'c', 'd'])
        agent.add_category('cat2', ['b', 'c'])

        agent_list = AgentList([agent])

        # First filter to cat1 (should have a, b, c, d)
        filtered1 = agent_list.with_categories('cat1')
        self.assertEqual(set(filtered1[0].traits.keys()), {'a', 'b', 'c', 'd'})

        # Categories are preserved through duplicate(), so we can chain
        # Now filter to cat2 (should have b, c)
        filtered2 = filtered1.with_categories('cat2')
        self.assertEqual(set(filtered2[0].traits.keys()), {'b', 'c'})
        self.assertEqual(filtered2[0].traits['b'], 2)
        self.assertEqual(filtered2[0].traits['c'], 3)


if __name__ == '__main__':
    unittest.main()
