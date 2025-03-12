"""Tests for the Field-based filtering."""

import pytest
from edsl import Agent, AgentList, Scenario, ScenarioList, Dataset, Field
from edsl.utilities.query_utils import QueryExpression


def test_agent_list_field_filtering():
    """Test filtering AgentList with Field expressions."""
    # Create test data
    agent_list = AgentList([
        Agent(traits={"age": 25, "name": "Alice", "active": True}),
        Agent(traits={"age": 30, "name": "Bob", "active": False}),
        Agent(traits={"age": 20, "name": "Charlie", "active": True}),
        Agent(traits={"age": 35, "name": "David", "active": False}),
    ])
    
    # Test simple Field expression
    filtered = agent_list.filter(Field("age") > 25)
    assert len(filtered) == 2
    assert filtered[0].traits["name"] == "Bob"
    assert filtered[1].traits["name"] == "David"
    
    # Test compound Field expression with &
    filtered = agent_list.filter((Field("age") > 20) & (Field("active") == True))
    assert len(filtered) == 1
    assert filtered[0].traits["name"] == "Alice"
    
    # Test compound Field expression with |
    filtered = agent_list.filter((Field("age") >= 30) | (Field("name") == "Alice"))
    assert len(filtered) == 3
    assert {agent.traits["name"] for agent in filtered} == {"Alice", "Bob", "David"}


def test_scenario_list_field_filtering():
    """Test filtering ScenarioList with Field expressions."""
    # Create test data
    scenario_list = ScenarioList([
        Scenario({"age": 25, "name": "Alice", "active": True}),
        Scenario({"age": 30, "name": "Bob", "active": False}),
        Scenario({"age": 20, "name": "Charlie", "active": True}),
        Scenario({"age": 35, "name": "David", "active": False}),
    ])
    
    # Test simple Field expression
    filtered = scenario_list.filter(Field("age") < 30)
    assert len(filtered) == 2
    assert filtered[0]["name"] == "Alice"
    assert filtered[1]["name"] == "Charlie"
    
    # Test string operations
    filtered = scenario_list.filter(Field("name").startswith("A"))
    assert len(filtered) == 1
    assert filtered[0]["name"] == "Alice"
    
    filtered = scenario_list.filter(Field("name").contains("a"))
    assert len(filtered) == 2
    assert {scenario["name"] for scenario in filtered} == {"Charlie", "David"}


def test_dataset_field_filtering():
    """Test filtering Dataset with Field expressions."""
    # Create test data
    dataset = Dataset([
        {"age": [25, 30, 20, 35]},
        {"name": ["Alice", "Bob", "Charlie", "David"]},
        {"active": [True, False, True, False]},
    ])
    
    # Test simple Field expression
    filtered = dataset.filter(Field("age") > 25)
    assert len(filtered) == 2  # Two rows match
    assert filtered[0]["age"] == [30, 35]
    assert filtered[1]["name"] == ["Bob", "David"]
    
    # Test compound Field expression
    filtered = dataset.filter((Field("age") <= 25) & (Field("active") == True))
    assert len(filtered) == 2  # Two rows match
    assert filtered[0]["age"] == [25, 20]
    assert filtered[1]["name"] == ["Alice", "Charlie"]


def test_backward_compatibility():
    """Test that string-based filtering still works."""
    # Create test data
    agent_list = AgentList([
        Agent(traits={"age": 25, "name": "Alice"}),
        Agent(traits={"age": 30, "name": "Bob"}),
    ])
    
    # Test string expression
    filtered = agent_list.filter("age > 25")
    assert len(filtered) == 1
    assert filtered[0].traits["name"] == "Bob"