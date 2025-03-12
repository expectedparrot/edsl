"""Tests for the Field-based filtering."""

import pytest
from edsl import Agent, AgentList, Scenario, ScenarioList, Dataset, Field
from edsl.utilities.query_utils import QueryExpression


def test_agent_list_field_filtering():
    """Test filtering AgentList with Field expressions."""
    # Create test data
    agent_list = AgentList([
        Agent(name="Alice", traits={"age": 25, "active": True}),
        Agent(name="Bob", traits={"age": 30, "active": False}),
        Agent(name="Charlie", traits={"age": 20, "active": True}),
        Agent(name="David", traits={"age": 35, "active": False}),
    ])
    
    # Test simple Field expression
    filtered = agent_list.filter(Field("age") > 25)
    assert len(filtered) == 2
    assert filtered[0].name == "Bob"
    assert filtered[1].name == "David"
    
    # Test compound Field expression with &
    filtered = agent_list.filter((Field("age") > 20) & (Field("active") == True))
    assert len(filtered) == 1
    assert filtered[0].name == "Alice"
    
    # Test compound Field expression with |
    filtered = agent_list.filter((Field("age") >= 30) | (Field("active") == True))
    assert len(filtered) == 4  # All agents match this condition
    assert {agent.name for agent in filtered} == {"Alice", "Bob", "Charlie", "David"}


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
        Agent(name="Alice", traits={"age": 25}),
        Agent(name="Bob", traits={"age": 30}),
    ])
    
    # Test string expression
    filtered = agent_list.filter("age > 25")
    assert len(filtered) == 1
    assert filtered[0].name == "Bob"


def test_scenario_list_advanced_field_filtering():
    """Test advanced filtering capabilities for ScenarioList with Field expressions."""
    # Create a more complex test dataset
    scenario_list = ScenarioList([
        Scenario({
            "product": "Laptop",
            "price": 1200,
            "brand": "Apple",
            "in_stock": True,
            "rating": 4.8,
            "tags": ["electronics", "computers", "premium"]
        }),
        Scenario({
            "product": "Smartphone",
            "price": 800,
            "brand": "Samsung",
            "in_stock": True,
            "rating": 4.5,
            "tags": ["electronics", "phones", "android"]
        }),
        Scenario({
            "product": "Tablet",
            "price": 600,
            "brand": "Apple",
            "in_stock": False,
            "rating": 4.3,
            "tags": ["electronics", "tablets", "premium"]
        }),
        Scenario({
            "product": "Headphones",
            "price": 300,
            "brand": "Bose",
            "in_stock": True,
            "rating": 4.6,
            "tags": ["electronics", "audio", "premium"]
        }),
        Scenario({
            "product": "Phone Case",
            "price": 50,
            "brand": "Generic",
            "in_stock": True,
            "rating": 3.9,
            "tags": ["accessories", "phones"]
        }),
    ])
    
    # Test numeric comparisons
    filtered = scenario_list.filter(Field("price") > 500)
    assert len(filtered) == 3
    assert {s["product"] for s in filtered} == {"Laptop", "Smartphone", "Tablet"}
    
    filtered = scenario_list.filter((Field("price") >= 300) & (Field("price") <= 800))
    assert len(filtered) == 3
    assert {s["product"] for s in filtered} == {"Smartphone", "Tablet", "Headphones"}
    
    # Test equality and inequality
    filtered = scenario_list.filter(Field("brand") == "Apple")
    assert len(filtered) == 2
    assert {s["product"] for s in filtered} == {"Laptop", "Tablet"}
    
    filtered = scenario_list.filter(Field("brand") != "Apple")
    assert len(filtered) == 3
    assert {s["product"] for s in filtered} == {"Smartphone", "Headphones", "Phone Case"}
    
    # Test boolean fields
    filtered = scenario_list.filter(Field("in_stock") == True)
    assert len(filtered) == 4
    assert len(scenario_list.filter(Field("in_stock") == False)) == 1
    
    # Test string operations
    filtered = scenario_list.filter(Field("product").contains("phone"))
    assert len(filtered) == 2
    assert {s["product"] for s in filtered} == {"Smartphone", "Headphones"}
    
    filtered = scenario_list.filter(Field("brand").startswith("A"))
    assert len(filtered) == 2
    assert {s["product"] for s in filtered} == {"Laptop", "Tablet"}
    
    filtered = scenario_list.filter(Field("brand").endswith("e"))
    assert len(filtered) == 3  # Apple (2 entries) and Bose (1 entry)
    assert {s["brand"] for s in filtered} == {"Apple", "Bose"}
    
    # Test regex matching
    filtered = scenario_list.filter(Field("product").matches("^[A-Z][a-z]+$"))
    assert len(filtered) == 4  # Laptop, Smartphone, Tablet, Headphones
    assert {s["product"] for s in filtered} == {"Laptop", "Smartphone", "Tablet", "Headphones"}
    
    # Test complex compound expressions
    complex_filter = (
        (Field("price") > 100) & 
        (
            (Field("brand") == "Apple") | 
            (Field("rating") >= 4.5)
        ) & 
        (Field("in_stock") == True)
    )
    filtered = scenario_list.filter(complex_filter)
    assert len(filtered) == 3
    assert {s["product"] for s in filtered} == {"Laptop", "Smartphone", "Headphones"}
    
    # Test chained compound expressions
    chained_filter = (
        (Field("price") < 1000) & 
        (Field("rating") > 4.0) & 
        (Field("in_stock") == True)
    )
    filtered = scenario_list.filter(chained_filter)
    assert len(filtered) == 2
    assert {s["product"] for s in filtered} == {"Smartphone", "Headphones"}


def test_scenario_list_edge_cases():
    """Test edge cases for ScenarioList Field filtering."""
    # Test with empty scenario list
    empty_list = ScenarioList([])
    
    # Empty list should not cause errors in field type checks
    with pytest.raises(Exception):  # Expect some kind of exception for empty list
        empty_list.filter(Field("any_field") > 10)
    
    # Test with missing fields
    ragged_list = ScenarioList([
        Scenario({"field1": "value1", "field2": 10}),
        Scenario({"field1": "value2"}),  # Missing field2
        Scenario({"field2": 30})         # Missing field1
    ])
    
    # Should handle missing fields gracefully
    filtered = ragged_list.filter(Field("field2") > 20)
    assert len(filtered) == 1
    assert filtered[0]["field2"] == 30
    
    # Test with None values
    none_values = ScenarioList([
        Scenario({"field1": None, "field2": 10}),
        Scenario({"field1": "value", "field2": None})
    ])
    
    # Should handle None values gracefully
    filtered = none_values.filter(Field("field1") == None)
    assert len(filtered) == 1
    assert filtered[0]["field2"] == 10


def test_scenario_list_backward_compatibility():
    """Test backward compatibility of string filters with ScenarioList."""
    scenario_list = ScenarioList([
        Scenario({"price": 100, "category": "A", "in_stock": True}),
        Scenario({"price": 200, "category": "B", "in_stock": False}),
        Scenario({"price": 300, "category": "A", "in_stock": True})
    ])
    
    # Test simple string filter
    filtered = scenario_list.filter("price > 150")
    assert len(filtered) == 2
    assert [s["price"] for s in filtered] == [200, 300]
    
    # Test complex string filter
    filtered = scenario_list.filter("price >= 100 and category == 'A' and in_stock == True")
    assert len(filtered) == 2
    assert [s["price"] for s in filtered] == [100, 300]
    
    # Test that string filters and Field filters produce the same results
    string_filtered = scenario_list.filter("price > 150 and category == 'A'")
    field_filtered = scenario_list.filter((Field("price") > 150) & (Field("category") == "A"))
    assert len(string_filtered) == len(field_filtered)
    assert [s["price"] for s in string_filtered] == [s["price"] for s in field_filtered]