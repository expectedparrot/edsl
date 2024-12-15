import unittest
from edsl.agents.Agent import Agent
from edsl.agents.AgentList import AgentList


class TestAgentList(unittest.TestCase):
    def setUp(self):
        self.example_agents = [Agent.example(), Agent.example()]

    def test_initialization_with_data(self):
        agent_list = AgentList(self.example_agents)
        self.assertEqual(len(agent_list), 2)

    def test_initialization_without_data(self):
        agent_list = AgentList()
        self.assertEqual(len(agent_list), 0)

    # def test_to_method(self):
    #     agent_list = AgentList(self.example_agents)
    #     # Assuming you have a mock for Question or Survey
    #     mock_question = MockQuestion()
    #     result = agent_list.to(mock_question)
    #     # Test the expected behavior
    #     # ...

    # def test_update_traits(self):
    #     agent_list = AgentList(self.example_agents)
    #     new_attributes = {"new_attribute": "value"}
    #     agent_list.update_traits(new_attributes)
    #     for agent in agent_list:
    #         self.assertIn("new_attribute", agent.traits)

    def test_to_dict(self):
        agent_list = AgentList(self.example_agents)
        result = agent_list.to_dict()
        self.assertIsInstance(result, dict)
        self.assertIn("agent_list", result)

    def test_from_dict(self):
        dict_representation = {
            "agent_list": [agent.to_dict() for agent in self.example_agents]
        }
        agent_list = AgentList.from_dict(dict_representation)
        self.assertEqual(len(agent_list), 2)

    def test_example_method(self):
        example = AgentList.example()
        self.assertIsInstance(example, AgentList)

    def test_code_method(self):
        agent_list = AgentList(self.example_agents)
        code_lines = agent_list.code(string=False)
        self.assertIsInstance(code_lines, list)
        # Test if the code lines are as expected
        # ...


if __name__ == "__main__":
    unittest.main()
