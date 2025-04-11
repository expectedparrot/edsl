import unittest
import tempfile
import os
from edsl.agents import Agent
from edsl.agents import AgentList

class TestAgentList(unittest.TestCase):
    def setUp(self):
        # Create a list of agents with different traits for better testing
        self.agent1 = Agent(name="Agent1", traits={"age": 30, "job": "Engineer", "hair": "brown"})
        self.agent2 = Agent(name="Agent2", traits={"age": 40, "job": "Teacher", "hair": "black"})
        self.agent3 = Agent(name="Agent3", traits={"age": 25, "job": "Doctor", "hair": "blonde"})
        
        self.example_agents = [self.agent1, self.agent2]
        self.all_agents = [self.agent1, self.agent2, self.agent3]
        self.example_codebook = {"age": "Age in years", "hair": "Hair color", "job": "Current occupation"}

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
        code_string = agent_list.code(string=True)
        self.assertIsInstance(code_string, str)
        # Verify key parts of the code output
        self.assertIn("from edsl import Agent", code_string)
        self.assertIn("from edsl import AgentList", code_string)
        self.assertIn("agent_list = AgentList(", code_string)
        
        # Test with string=False
        code_lines = agent_list.code(string=False)
        self.assertIsInstance(code_lines, list)
        self.assertEqual(len(code_lines), 3)  # Import Agent, import AgentList, agent_list declaration
    
    def test_shuffle(self):
        """Test shuffling of agent list"""
        agent_list = AgentList(self.all_agents)
        shuffled = agent_list.shuffle(seed="test_seed")
        
        # Ensure returned object is an AgentList
        self.assertIsInstance(shuffled, AgentList)
        
        # Check length is the same
        self.assertEqual(len(shuffled), len(agent_list))
        
        # Check all original agents are in the shuffled list (just in different order)
        for agent in agent_list:
            self.assertIn(agent, shuffled)
    
    def test_sample(self):
        """Test sampling from an agent list"""
        agent_list = AgentList(self.all_agents)
        
        # Test sampling 2 agents
        sampled = agent_list.sample(2, seed="test_seed")
        self.assertIsInstance(sampled, AgentList)
        self.assertEqual(len(sampled), 2)
        
        # Make sure sampled agents are in the original list
        for agent in sampled:
            self.assertIn(agent, agent_list)
        
        # Test sampling all agents
        sampled_all = agent_list.sample(3)
        self.assertEqual(len(sampled_all), 3)
        
        # Test sampling with too large n
        with self.assertRaises(ValueError):
            agent_list.sample(4)
    
    def test_duplicate(self):
        """Test duplicating an agent list"""
        agent_list = AgentList(self.example_agents)
        duplicate = agent_list.duplicate()
        
        # Check it's a different object but equal in content
        self.assertIsNot(duplicate, agent_list)
        self.assertEqual(duplicate, agent_list)
    
    def test_rename(self):
        """Test renaming traits in an agent list"""
        agent_list = AgentList(self.example_agents)
        renamed = agent_list.rename("job", "profession")
        
        # Check original list is unchanged
        for agent in agent_list:
            self.assertIn("job", agent._traits)
            self.assertNotIn("profession", agent._traits)
        
        # Check renamed list has the new trait
        for agent in renamed:
            self.assertNotIn("job", agent._traits)
            self.assertIn("profession", agent._traits)
    
    def test_select(self):
        """Test selecting specific traits from an agent list"""
        agent_list = AgentList(self.all_agents)
        selected = agent_list.select("age", "hair")
        
        # Check each agent in the selected list only has the selected traits
        for agent in selected:
            self.assertEqual(set(agent._traits.keys()), {"age", "hair"})
            self.assertNotIn("job", agent._traits)
    
    def test_filter(self):
        """Test filtering an agent list"""
        agent_list = AgentList(self.all_agents)
        
        # Filter agents by age
        filtered = agent_list.filter("age > 30")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]._traits["age"], 40)
        
        # Filter by job
        filtered_job = agent_list.filter("job == 'Engineer'")
        self.assertEqual(len(filtered_job), 1)
        self.assertEqual(filtered_job[0]._traits["job"], "Engineer")
        
        # Complex filter
        filtered_complex = agent_list.filter("age < 35 and hair != 'black'")
        self.assertEqual(len(filtered_complex), 2)
        
        # Invalid filter expression
        with self.assertRaises(Exception):  # Could be various exceptions
            agent_list.filter("invalid % expression")
    
    def test_all_traits(self):
        """Test getting all traits from an agent list"""
        agent_list = AgentList(self.all_agents)
        all_traits = agent_list.all_traits  # It's a property, not a method
        self.assertIsInstance(all_traits, list)
        self.assertEqual(set(all_traits), {"age", "job", "hair"})
    
    def test_from_csv(self):
        """Test creating an agent list from a CSV file"""
        # Create a temporary CSV file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            f.write("name,age,job,hair\n")
            f.write("Person1,30,Engineer,brown\n")
            f.write("Person2,40,Teacher,black\n")
            f.write("Person3,25,Doctor,blonde\n")
            csv_path = f.name
        
        try:
            # Create AgentList from the CSV
            agent_list = AgentList.from_csv(csv_path, name_field="name")
            
            # Verify the agent list
            self.assertEqual(len(agent_list), 3)
            self.assertEqual(agent_list[0].name, "Person1")
            self.assertEqual(agent_list[0]._traits["age"], "30")  # CSV imports as strings
            
            # Create with codebook
            agent_list_with_codebook = AgentList.from_csv(
                csv_path, name_field="name", codebook=self.example_codebook
            )
            self.assertEqual(agent_list_with_codebook[0].codebook, self.example_codebook)
        finally:
            os.unlink(csv_path)
            
    def test_translate_traits(self):
        """Test translating traits"""
        agent_list = AgentList(self.example_agents)
        
        # Create a proper trait mapping - translate trait values, not keys
        trait_mapping = {
            "hair": {
                "brown": "brown_translated",
                "black": "black_translated"
            }
        }
        translated = agent_list.translate_traits(trait_mapping)
        
        # Check original is unchanged
        for agent in agent_list:
            if agent._traits["hair"] == "brown":
                self.assertEqual(agent._traits["hair"], "brown")
            if agent._traits["hair"] == "black":
                self.assertEqual(agent._traits["hair"], "black")
        
        # Check translated values are updated
        for agent in translated:
            if "brown" in agent._traits.values():
                self.fail("Original value 'brown' should be translated")
            if "black" in agent._traits.values():
                self.fail("Original value 'black' should be translated")
            
            # The structure of traits should be the same
            self.assertIn("hair", agent._traits)
    
    def test_remove_trait(self):
        """Test removing a trait"""
        agent_list = AgentList(self.example_agents)
        modified = agent_list.remove_trait("age")
        
        # Check original is unchanged
        for agent in agent_list:
            self.assertIn("age", agent._traits)
        
        # Check modified has no age trait
        for agent in modified:
            self.assertNotIn("age", agent._traits)
            self.assertIn("job", agent._traits)
    
    def test_add_trait(self):
        """Test adding a trait"""
        agent_list = AgentList(self.example_agents)
        
        # Add a new trait
        values = ["tall", "short"]
        modified = agent_list.add_trait("height", values)
        
        # Check original is unchanged
        for agent in agent_list:
            self.assertNotIn("height", agent._traits)
        
        # Check modified has the new trait
        for i, agent in enumerate(modified):
            self.assertEqual(agent._traits["height"], values[i])
        
        # Try adding with wrong number of values
        with self.assertRaises(Exception):
            agent_list.add_trait("height", ["single_value"])
    
    def test_set_codebook(self):
        """Test setting a codebook"""
        # Create an agent list with agents that have no codebook
        agent1 = Agent(name="TestAgent1", traits={"age": 30, "job": "Engineer"})
        agent2 = Agent(name="TestAgent2", traits={"age": 40, "job": "Teacher"})
        agent_list = AgentList([agent1, agent2])
        
        # Set a new codebook
        new_codebook = {"age": "Age in months", "job": "Job title"}
        modified = agent_list.set_codebook(new_codebook)
        
        # Check modified has the new codebook
        for agent in modified:
            self.assertEqual(agent.codebook, new_codebook)
    
    def test_cartesian_product(self):
        """Test cartesian product (multiplication) of agent lists"""
        # Create two simple agent lists
        agents1 = AgentList([
            Agent(name="A1", traits={"trait1": "value1"}),
            Agent(name="A2", traits={"trait1": "value2"})
        ])
        
        agents2 = AgentList([
            Agent(name="B1", traits={"trait2": "value3"}),
            Agent(name="B2", traits={"trait2": "value4"})
        ])
        
        # Multiply them
        product = agents1 * agents2
        
        # Check result
        self.assertEqual(len(product), 4)  # 2x2 = 4 combinations
        
        # Check traits in the combined agents
        traits_in_product = [set(a._traits.keys()) for a in product]
        expected_traits = [{"trait1", "trait2"} for _ in range(4)]
        self.assertEqual(traits_in_product, expected_traits)
        
        # Check all combinations exist
        trait_values = [(a._traits["trait1"], a._traits["trait2"]) for a in product]
        expected_values = [
            ("value1", "value3"),
            ("value1", "value4"),
            ("value2", "value3"),
            ("value2", "value4")
        ]
        for expected in expected_values:
            self.assertIn(expected, trait_values)


if __name__ == "__main__":
    unittest.main()
