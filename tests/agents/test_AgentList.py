import unittest
import tempfile
import os
import csv
from edsl.agents import Agent
from edsl.agents import AgentList
from edsl.agents.exceptions import AgentListError

class TestAgentList(unittest.TestCase):
    def setUp(self):
        self.example_agents = [Agent.example(), Agent.example()]
        self.example_codebook = {"age": "Age in years", "hair": "Hair color"}
        
        # Set up a diverse list of agents for more complex tests
        self.agent1 = Agent(traits={'age': 25, 'hair': 'black', 'height': 6.0})
        self.agent2 = Agent(traits={'age': 30, 'hair': 'blonde', 'height': 5.5})
        self.agent3 = Agent(traits={'age': 35, 'hair': 'red', 'weight': 150})
        self.diverse_agents = AgentList([self.agent1, self.agent2, self.agent3])

    def test_initialization_with_data(self):
        agent_list = AgentList(self.example_agents)
        self.assertEqual(len(agent_list), 2)

    def test_initialization_without_data(self):
        agent_list = AgentList()
        self.assertEqual(len(agent_list), 0)

    def test_initialization_with_codebook(self):
        agent_list = AgentList(self.example_agents, codebook=self.example_codebook)
        self.assertEqual(len(agent_list), 2)
        for agent in agent_list:
            self.assertEqual(agent.codebook, self.example_codebook)

    def test_to_dict(self):
        agent_list = AgentList(self.example_agents)
        result = agent_list.to_dict()
        self.assertIsInstance(result, dict)
        self.assertIn("agent_list", result)
        
    def test_to_dict_with_codebook(self):
        agent_list = AgentList(self.example_agents, codebook=self.example_codebook)
        result = agent_list.to_dict()
        self.assertIsInstance(result, dict)
        self.assertIn("agent_list", result)
        self.assertIn("codebook", result)
        self.assertEqual(result["codebook"], self.example_codebook)

    def test_from_dict(self):
        dict_representation = {
            "agent_list": [agent.to_dict() for agent in self.example_agents]
        }
        agent_list = AgentList.from_dict(dict_representation)
        self.assertEqual(len(agent_list), 2)

    def test_from_dict_with_codebook(self):
        dict_representation = {
            "agent_list": [agent.to_dict() for agent in self.example_agents],
            "codebook": self.example_codebook
        }
        agent_list = AgentList.from_dict(dict_representation)
        self.assertEqual(len(agent_list), 2)
        for agent in agent_list:
            self.assertEqual(agent.codebook, self.example_codebook)

    def test_example_method(self):
        example = AgentList.example()
        self.assertIsInstance(example, AgentList)
        
    def test_example_method_with_codebook(self):
        example = AgentList.example(codebook=self.example_codebook)
        self.assertIsInstance(example, AgentList)
        for agent in example:
            self.assertEqual(agent.codebook, self.example_codebook)

    def test_from_list_method_with_codebook(self):
        agent_list = AgentList.from_list("age", [22, 23], codebook=self.example_codebook)
        self.assertEqual(len(agent_list), 2)
        for agent in agent_list:
            self.assertEqual(agent.codebook, self.example_codebook)

    def test_code_method(self):
        agent_list = AgentList(self.example_agents)
        code_lines = agent_list.code(string=False)
        self.assertIsInstance(code_lines, list)
        self.assertEqual(len(code_lines), 3)
        self.assertTrue(code_lines[0].startswith("from edsl import Agent"))
        self.assertTrue(code_lines[1].startswith("from edsl import AgentList"))
        
        # Test string version
        code_str = agent_list.code()
        self.assertIsInstance(code_str, str)
        self.assertTrue("from edsl import Agent" in code_str)
        self.assertTrue("from edsl import AgentList" in code_str)
    
    def test_shuffle(self):
        """Test the shuffle method"""
        # Since shuffle is random, hard to test directly
        # Just verify it returns an AgentList and has the same length
        original = self.diverse_agents.duplicate()
        shuffled = self.diverse_agents.shuffle(seed="fixed_seed")
        
        # Should return same object (shuffle in place)
        self.assertIs(self.diverse_agents, shuffled)
        self.assertEqual(len(original), len(shuffled))
        
        # Test with a fixed seed to ensure reproducibility
        list1 = AgentList([self.agent1, self.agent2, self.agent3]).shuffle(seed="test_seed")
        list2 = AgentList([self.agent1, self.agent2, self.agent3]).shuffle(seed="test_seed")
        
        # Both lists should be shuffled the same way with the same seed
        for i in range(len(list1)):
            self.assertEqual(list1[i], list2[i])
    
    def test_sample(self):
        """Test the sample method"""
        # Sample 2 agents
        sampled = self.diverse_agents.sample(n=2, seed="fixed_seed")
        
        # Check return type and length
        self.assertIsInstance(sampled, AgentList)
        self.assertEqual(len(sampled), 2)
        
        # Test with fixed seed for reproducibility
        sample1 = self.diverse_agents.sample(n=2, seed="test_seed")
        sample2 = self.diverse_agents.sample(n=2, seed="test_seed")
        
        # Both samples should be the same with the same seed
        for i in range(len(sample1)):
            self.assertEqual(sample1[i], sample2[i])
    
    def test_duplicate(self):
        """Test the duplicate method"""
        duplicate = self.diverse_agents.duplicate()
        
        # Check it's a different object but equal content
        self.assertIsNot(duplicate, self.diverse_agents)
        self.assertEqual(duplicate, self.diverse_agents)
        
        # Verify it's a deep copy
        duplicate_agent = duplicate[0]
        original_agent = self.diverse_agents[0]
        
        # Agents should be equal but not the same object
        self.assertEqual(duplicate_agent, original_agent)
        self.assertIsNot(duplicate_agent, original_agent)
    
    def test_rename(self):
        """Test the rename method"""
        renamed = self.diverse_agents.rename('age', 'years')
        
        # Check original is unchanged
        self.assertIn('age', self.diverse_agents[0].traits)
        
        # Check renamed has the new trait name
        self.assertNotIn('age', renamed[0].traits)
        self.assertIn('years', renamed[0].traits)
        
        # Check values were preserved
        self.assertEqual(renamed[0].traits['years'], self.diverse_agents[0].traits['age'])
    
    def test_remove_trait(self):
        """Test the remove_trait method"""
        removed = self.diverse_agents.remove_trait('age')
        
        # Check original is unchanged
        self.assertIn('age', self.diverse_agents[0].traits)
        
        # Check trait was removed
        self.assertNotIn('age', removed[0].traits)
        
        # Check other traits remain
        self.assertIn('hair', removed[0].traits)
    
    def test_filter(self):
        """Test the filter method"""
        # Filter agents with age > 25
        filtered = self.diverse_agents.filter("age > 25")
        
        # Should have 2 agents
        self.assertEqual(len(filtered), 2)
        
        # Check filtered values
        ages = [agent.traits['age'] for agent in filtered]
        self.assertTrue(all(age > 25 for age in ages))
        
        # Test filtering with a non-existent trait
        with self.assertRaises(AgentListError):
            self.diverse_agents.filter("non_existent_trait == 1")
    
    def test_add_trait_single_value(self):
        """Test adding a trait with a single value"""
        # The method treats non-iterables differently than iterables
        # For non-iterables, it applies the same value to all agents
        added = self.diverse_agents.add_trait('new_trait', 42)
        
        # Check new trait was added to all agents
        for agent in added:
            self.assertIn('new_trait', agent.traits)
            self.assertEqual(agent.traits['new_trait'], 42)
    
    def test_add_trait_multiple_values(self):
        """Test adding a trait with multiple values"""
        values = ['value1', 'value2', 'value3']
        added = self.diverse_agents.add_trait('new_trait', values)
        
        # Check new traits were added with correct values
        for i, agent in enumerate(added):
            self.assertIn('new_trait', agent.traits)
            self.assertEqual(agent.traits['new_trait'], values[i])
    
    def test_add_trait_with_incorrect_length(self):
        """Test adding a trait with incorrect number of values"""
        values = ['value1', 'value2']  # Only 2 values for 3 agents
        
        # Should raise an error
        with self.assertRaises(AgentListError):
            self.diverse_agents.add_trait('new_trait', values)
    
    def test_from_csv(self):
        """Test creating AgentList from CSV"""
        # Create a temporary CSV file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            writer = csv.writer(f)
            writer.writerow(['age', 'hair', 'height'])
            writer.writerow([25, 'black', 6.0])
            writer.writerow([30, 'blonde', 5.5])
            csv_file = f.name
        
        try:
            # Test basic loading
            agents = AgentList.from_csv(csv_file)
            self.assertEqual(len(agents), 2)
            self.assertEqual(agents[0].traits['age'], '25')
            
            # Test with name field
            agents = AgentList.from_csv(csv_file, name_field='hair')
            self.assertEqual(len(agents), 2)
            self.assertEqual(agents[0].name, 'black')
            self.assertNotIn('hair', agents[0].traits)
            
            # Test with codebook
            agents = AgentList.from_csv(csv_file, codebook=self.example_codebook)
            self.assertEqual(len(agents), 2)
            self.assertEqual(agents[0].codebook, self.example_codebook)
        finally:
            # Clean up
            os.unlink(csv_file)
    
    def test_translate_traits(self):
        """Test translating traits based on a codebook"""
        translation = {'hair': {'black': 'dark', 'blonde': 'light', 'red': 'ginger'}}
        translated = self.diverse_agents.translate_traits(translation)
        
        # Check original is unchanged
        self.assertEqual(self.diverse_agents[0].traits['hair'], 'black')
        
        # Check translation was applied
        self.assertEqual(translated[0].traits['hair'], 'dark')
        self.assertEqual(translated[1].traits['hair'], 'light')
        self.assertEqual(translated[2].traits['hair'], 'ginger')
    
    def test_cross_product(self):
        """Test the cross product (__mul__) method"""
        list1 = AgentList([Agent(traits={'a': 1}), Agent(traits={'a': 2})])
        list2 = AgentList([Agent(traits={'b': 3}), Agent(traits={'b': 4})])
        
        result = list1 * list2
        
        # Should have 4 agents (2x2)
        self.assertEqual(len(result), 4)
        
        # Check combination of traits
        expected_traits = [
            {'a': 1, 'b': 3},
            {'a': 1, 'b': 4},
            {'a': 2, 'b': 3},
            {'a': 2, 'b': 4}
        ]
        
        for agent, expected in zip(result, expected_traits):
            for key, value in expected.items():
                self.assertEqual(agent.traits[key], value)
    
    def test_all_traits_property(self):
        """Test the all_traits property"""
        # Our list has agents with traits: age, hair, height, weight
        all_traits = self.diverse_agents.all_traits
        
        # Check that we get all unique traits
        self.assertIn('age', all_traits)
        self.assertIn('hair', all_traits)
        self.assertIn('height', all_traits)
        self.assertIn('weight', all_traits)
        
        # List should be unique
        self.assertEqual(len(all_traits), 4)
    
    def test_to_dataset(self):
        """Test the to_dataset method"""
        # Test with traits_only=True (default)
        dataset = self.diverse_agents.to_dataset()
        
        # Dataset should contain all traits
        # Check that the dataset contains the expected traits
        for trait in ['age', 'hair', 'height', 'weight']:
            self.assertTrue(any(trait in d for d in dataset))
            
        # Convert Dataset to pandas to check values
        df = dataset.to_pandas()
        self.assertEqual(list(df['age']), [25, 30, 35])
        self.assertEqual(list(df['hair']), ['black', 'blonde', 'red'])
        
        # Test with traits_only=False
        dataset = self.diverse_agents.to_dataset(traits_only=False)
        
        # Should also contain agent_parameters
        self.assertTrue(any('agent_parameters' in d for d in dataset))
    
    def test_set_codebook(self):
        """Test the set_codebook method"""
        # Set codebook on the agent list
        agent_list = self.diverse_agents.duplicate()
        agent_list.set_codebook(self.example_codebook)
        
        # Check all agents have the codebook
        for agent in agent_list:
            self.assertEqual(agent.codebook, self.example_codebook)
        
        # Should return self for chaining
        result = agent_list.set_codebook(self.example_codebook)
        self.assertIs(result, agent_list)
    
    def test_select(self):
        """Test the select method to keep only specified traits"""
        # Select only 'age' and 'hair' traits
        selected = self.diverse_agents.select('age', 'hair')
        
        # Check original is unchanged
        self.assertIn('height', self.diverse_agents[0].traits)
        
        # Check selected has only the requested traits
        for agent in selected:
            self.assertIn('age', agent.traits)
            self.assertIn('hair', agent.traits)
            self.assertNotIn('height', agent.traits)
            self.assertNotIn('weight', agent.traits)
        
        # Test selecting a single trait
        selected = self.diverse_agents.select('age')
        for agent in selected:
            self.assertIn('age', agent.traits)
            self.assertNotIn('hair', agent.traits)
    
    def test_table(self):
        """Test the table method"""
        # This is somewhat hard to test directly since it depends on rich table formatting
        # Let's just make sure it doesn't throw an exception
        table = self.diverse_agents.table('age', 'hair')
        self.assertIsNotNone(table)
        
        # Test with empty AgentList (should raise an exception)
        empty_list = AgentList([])
        with self.assertRaises(AgentListError):
            empty_list.table('age')
    
    def test_hash(self):
        """Test the __hash__ method"""
        # Create two AgentLists with different content
        list1 = AgentList([
            Agent(traits={'age': 25, 'hair': 'black'}),
            Agent(traits={'age': 30, 'hair': 'blonde'})
        ])
        
        list2 = AgentList([
            Agent(traits={'age': 99, 'hair': 'purple'}),
            Agent(traits={'age': 45, 'hair': 'green'})
        ])
        
        # Hashes should be different for different objects
        self.assertNotEqual(hash(list1), hash(list2))
        
        # Create copies of the same list - they should have the same hash
        list3 = AgentList([
            Agent(traits={'age': 25, 'hair': 'black'}),
            Agent(traits={'age': 30, 'hair': 'blonde'})
        ])
        
        self.assertEqual(hash(list1), hash(list3))


if __name__ == "__main__":
    unittest.main()
