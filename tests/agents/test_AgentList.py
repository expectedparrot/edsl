import unittest
from edsl.agents import Agent
from edsl.agents import AgentList

class TestAgentList(unittest.TestCase):
    def setUp(self):
        self.example_agents = [Agent.example(), Agent.example()]
        self.example_codebook = {"age": "Age in years", "hair": "Hair color"}

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
        # Create a regular example and manually set the codebook
        example = AgentList.example()
        example.set_codebook(self.example_codebook)
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
        # Test if the code lines are as expected
        # ...


if __name__ == "__main__":
    unittest.main()
