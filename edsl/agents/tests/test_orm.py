"""
Tests for the Agent and AgentList ORM implementation.

This module tests the ORM functionality for persisting Agent and AgentList objects
to a database, including serialization, deserialization, and CRUD operations.
"""

import os
import unittest
import tempfile
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from edsl.agents.agent import Agent
from edsl.agents.agent_list import AgentList
from edsl.agents.orm import (
    Base,
    SQLAgent,
    SQLAgentTrait,
    SQLAgentCodebook,
    SQLAgentList,
    save_agent,
    save_agent_list,
    load_agent,
    load_agent_list,
    delete_agent,
    delete_agent_list,
    list_agents,
    list_agent_lists
)


class TestAgentOrm(unittest.TestCase):
    """Test the Agent ORM implementation."""

    def setUp(self):
        """Set up a new database for each test."""
        # Create a new in-memory SQLite database for each test
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

    def tearDown(self):
        """Clean up resources after each test."""
        self.session.close()
        Base.metadata.drop_all(self.engine)

    def test_save_and_load_agent(self):
        """Test saving and loading an Agent with different trait types."""
        # Create an Agent with various trait types
        agent = Agent(
            name="Test Agent",
            traits={
                "string_value": "test string",
                "int_value": 42,
                "float_value": 3.14,
                "bool_value": True,
                "none_value": None,
                "list_value": [1, 2, 3],
                "dict_value": {"key": "value"}
            },
            codebook={"string_value": "A test string", "int_value": "An integer value"},
            instruction="This is a test instruction"
        )

        # Save the agent
        agent_orm = save_agent(self.session, agent)
        self.session.commit()
        agent_id = agent_orm.id
        
        # Verify the agent has an ORM ID
        self.assertTrue(hasattr(agent, '_orm_id'))
        self.assertEqual(agent._orm_id, agent_id)

        # Load the agent
        loaded_agent = load_agent(self.session, agent_id)
        
        # Verify that all values were loaded correctly
        self.assertEqual(loaded_agent.name, "Test Agent")
        self.assertEqual(loaded_agent.instruction, "This is a test instruction")
        self.assertEqual(loaded_agent["string_value"], "test string")
        self.assertEqual(loaded_agent["int_value"], 42)
        self.assertEqual(loaded_agent["float_value"], 3.14)
        self.assertEqual(loaded_agent["bool_value"], True)
        self.assertEqual(loaded_agent["list_value"], [1, 2, 3])
        self.assertEqual(loaded_agent["dict_value"], {"key": "value"})
        
        # Verify codebook was loaded
        self.assertEqual(loaded_agent.codebook, {"string_value": "A test string", "int_value": "An integer value"})

    def test_agent_with_custom_functions(self):
        """Test saving and loading an Agent with custom functions."""
        # Create an Agent with a dynamic traits function
        def dynamic_traits_func(question=None):
            return {"dynamic_trait": "dynamic value"}
        
        def direct_answer_func(self, question, scenario):
            return "This is a direct answer"
        
        agent = Agent(
            traits={"trait": "value"},
            dynamic_traits_function=dynamic_traits_func
        )
        agent.add_direct_question_answering_method(direct_answer_func)
        
        # Save the agent
        agent_orm = save_agent(self.session, agent)
        self.session.commit()
        agent_id = agent_orm.id
        
        # Verify fields were saved
        self.assertEqual(agent_orm.has_dynamic_traits_function, "1")
        self.assertEqual(agent_orm.dynamic_traits_function_name, "dynamic_traits_func")
        self.assertTrue(agent_orm.dynamic_traits_function_source_code is not None)
        self.assertEqual(agent_orm.answer_question_directly_function_name, "direct_answer_func")
        self.assertTrue(agent_orm.answer_question_directly_source_code is not None)
        
        # Load the agent
        loaded_agent = load_agent(self.session, agent_id)
        
        # Verify functions
        self.assertTrue(hasattr(loaded_agent, "dynamic_traits_function"))
        self.assertTrue(hasattr(loaded_agent, "answer_question_directly"))
        
        # Test the functions
        self.assertEqual(loaded_agent.dynamic_traits_function(), {"dynamic_trait": "dynamic value"})
        
        # Note: We use None for question and scenario as we're just testing the method is preserved
        self.assertEqual(loaded_agent.answer_question_directly(None, None), "This is a direct answer")

    def test_update_agent(self):
        """Test updating an existing Agent."""
        # Create and save an initial agent
        agent = Agent(traits={"key1": "value1"}, name="Original Name")
        agent_orm = save_agent(self.session, agent)
        self.session.commit()
        agent_id = agent_orm.id
        
        # Create a new agent with updated values (Agent is immutable, so create a new one)
        updated_traits = agent.traits.copy()
        updated_traits["key1"] = "updated value"
        updated_traits["key2"] = "new value"
        updated_agent = Agent(
            traits=updated_traits,
            name="Updated Name",
            instruction="New instruction"
        )
        
        # Keep the ORM ID to maintain reference
        updated_agent._orm_id = agent._orm_id
        
        # Save the updated agent
        save_agent(self.session, updated_agent)
        self.session.commit()
        
        # Load the agent again
        loaded_agent = load_agent(self.session, agent_id)
        
        # Verify the updates
        self.assertEqual(loaded_agent.name, "Updated Name")
        self.assertEqual(loaded_agent.instruction, "New instruction")
        self.assertEqual(loaded_agent.traits["key1"], "updated value")
        self.assertEqual(loaded_agent.traits["key2"], "new value")

    def test_delete_agent(self):
        """Test deleting an Agent."""
        # Create and save an agent
        agent = Agent(traits={"key": "value"})
        agent_orm = save_agent(self.session, agent)
        self.session.commit()
        agent_id = agent_orm.id
        
        # Delete the agent
        success = delete_agent(self.session, agent_id)
        self.session.commit()
        
        # Verify deletion was successful
        self.assertTrue(success)
        self.assertIsNone(load_agent(self.session, agent_id))

    def test_list_agents(self):
        """Test listing Agents with pagination."""
        # Create and save multiple agents
        for i in range(10):
            agent = Agent(traits={"index": i}, name=f"Agent {i}")
            save_agent(self.session, agent)
        self.session.commit()
        
        # List agents with pagination
        agents_page1 = list_agents(self.session, limit=5, offset=0)
        agents_page2 = list_agents(self.session, limit=5, offset=5)
        
        # Verify pagination works correctly
        self.assertEqual(len(agents_page1), 5)
        self.assertEqual(len(agents_page2), 5)
        # Verify the correct fields are returned
        self.assertIn('id', agents_page1[0])
        self.assertIn('name', agents_page1[0])
        self.assertIn('created_at', agents_page1[0])


class TestAgentListOrm(unittest.TestCase):
    """Test the AgentList ORM implementation."""

    def setUp(self):
        """Set up a new database for each test."""
        # Create a new in-memory SQLite database for each test
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

    def tearDown(self):
        """Clean up resources after each test."""
        self.session.close()
        Base.metadata.drop_all(self.engine)

    def test_save_and_load_agent_list(self):
        """Test saving and loading an AgentList."""
        # Create an AgentList with multiple Agents
        agents = [
            Agent(traits={"index": i, "value": f"value {i}"}, name=f"Agent {i}")
            for i in range(5)
        ]
        codebook = {"index": "Index number", "value": "Value string"}
        # Set codebook for all agents
        agent_list = AgentList(agents).set_codebook(codebook)
        
        # Save the agent list
        agent_list_orm = save_agent_list(self.session, agent_list)
        self.session.commit()
        agent_list_id = agent_list_orm.id
        
        # Verify the agent list has an ORM ID
        self.assertTrue(hasattr(agent_list, '_orm_id'))
        self.assertEqual(agent_list._orm_id, agent_list_id)
        
        # Load the agent list
        loaded_agent_list = load_agent_list(self.session, agent_list_id)
        
        # Verify the loaded agent list
        self.assertEqual(len(loaded_agent_list), 5)
        self.assertEqual(loaded_agent_list[0].codebook, codebook)
        
        # Verify the agents were loaded correctly
        for i, agent in enumerate(loaded_agent_list):
            self.assertEqual(agent["index"], i)
            self.assertEqual(agent["value"], f"value {i}")
            self.assertEqual(agent.name, f"Agent {i}")
            # Verify each agent has an ORM ID
            self.assertTrue(hasattr(agent, '_orm_id'))

    def test_update_agent_list(self):
        """Test updating an existing AgentList."""
        # Create and save an initial agent list
        agents = [
            Agent(traits={"index": i}, name=f"Agent {i}")
            for i in range(3)
        ]
        agent_list = AgentList(agents)
        
        # Save the agent list
        agent_list_orm = save_agent_list(self.session, agent_list)
        self.session.commit()
        agent_list_id = agent_list_orm.id
        
        # Create a modified agent list
        # 1. Add a new agent
        updated_agents = agent_list.copy()
        updated_agents.append(Agent(traits={"index": 3}, name="Agent 3"))
        
        # 2. Update the first agent with new traits
        first_agent_traits = updated_agents[0].traits.copy()
        first_agent_traits["new_key"] = "new value"
        updated_first_agent = Agent(
            traits=first_agent_traits,
            name=updated_agents[0].name,
            instruction=updated_agents[0].instruction
        )
        updated_agents[0] = updated_first_agent
        
        # 3. Set codebook for all agents
        updated_agents.set_codebook({"index": "Index number"})
        
        # Keep the ORM ID reference
        updated_agents._orm_id = agent_list._orm_id
        
        # Save the updated agent list
        save_agent_list(self.session, updated_agents)
        self.session.commit()
        
        # Load the agent list again
        loaded_agent_list = load_agent_list(self.session, agent_list_id)
        
        # Verify the updates
        self.assertEqual(len(loaded_agent_list), 4)
        self.assertEqual(loaded_agent_list[0].codebook, {"index": "Index number"})
        self.assertEqual(loaded_agent_list[0].traits["new_key"], "new value")
        self.assertEqual(loaded_agent_list[3].traits["index"], 3)

    def test_delete_agent_list(self):
        """Test deleting an AgentList."""
        # Create and save an agent list
        agents = [Agent(traits={"key": "value"})]
        agent_list = AgentList(agents)
        agent_list_orm = save_agent_list(self.session, agent_list)
        self.session.commit()
        agent_list_id = agent_list_orm.id
        
        # Delete the agent list
        success = delete_agent_list(self.session, agent_list_id)
        self.session.commit()
        
        # Verify deletion was successful
        self.assertTrue(success)
        self.assertIsNone(load_agent_list(self.session, agent_list_id))

    def test_list_agent_lists(self):
        """Test listing AgentLists with pagination."""
        # Create and save multiple agent lists
        for i in range(10):
            agents = [Agent(traits={"group": i, "index": j}) for j in range(i+1)]
            agent_list = AgentList(agents)
            save_agent_list(self.session, agent_list)
        self.session.commit()
        
        # List agent lists with pagination
        lists_page1 = list_agent_lists(self.session, limit=5, offset=0)
        lists_page2 = list_agent_lists(self.session, limit=5, offset=5)
        
        # Verify pagination works correctly
        self.assertEqual(len(lists_page1), 5)
        self.assertEqual(len(lists_page2), 5)
        # Verify the correct fields are returned
        self.assertIn('id', lists_page1[0])
        self.assertIn('created_at', lists_page1[0])
        self.assertIn('agent_count', lists_page1[0])


if __name__ == '__main__':
    unittest.main()