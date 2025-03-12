"""Tests for the QuestionJinjaFunction class."""

import pytest
from edsl import Scenario, Agent
from edsl.questions import QuestionJinjaFunction, QuestionBase


def simple_add(a, b):
    """Simple function to test conversion."""
    return a + b


def test_jinja_function_basic():
    """Test basic functionality of QuestionJinjaFunction."""
    # Create a simple Jinja2 template
    template_str = """
    {% macro add(scenario, agent_traits) %}
        {{ scenario.get("a", 0) + scenario.get("b", 0) }}
    {% endmacro %}
    """
    
    # Create the question
    question = QuestionJinjaFunction(
        question_name="add_numbers",
        jinja2_template=template_str,
        macro_name="add",
        question_presentation="Simple addition function",
        answering_instructions="This is a computational question"
    )
    
    # Test it
    scenario = Scenario({"a": 5, "b": 10})
    agent = Agent(traits={})
    results = question.by(scenario).by(agent).run(disable_remote_cache=True, disable_remote_inference=True)
    
    # Check result
    assert results.select("answer.*").to_list()[0] == "15"


def test_complex_jinja_function():
    """Test more complex Jinja2 functionality including loops and conditions."""
    # Create a template with loops and conditionals
    template_str = """
    {% macro process_list(scenario, agent_traits) %}
        {% set numbers = scenario.get("numbers", []) %}
        {% set operation = agent_traits.get("operation", "sum") %}
        {% set result = 0 %}
        
        {% if operation == "sum" %}
            {% for num in numbers %}
                {% set result = result + num %}
            {% endfor %}
        {% elif operation == "product" %}
            {% set result = 1 %}
            {% for num in numbers %}
                {% set result = result * num %}
            {% endfor %}
        {% endif %}
        
        {{ result }}
    {% endmacro %}
    """
    
    # Create the question
    question = QuestionJinjaFunction(
        question_name="process_numbers",
        jinja2_template=template_str,
        macro_name="process_list",
        question_presentation="List processing function",
        answering_instructions="Computational question"
    )
    
    # Test sum operation
    scenario = Scenario({"numbers": [1, 2, 3, 4, 5]})
    agent = Agent(traits={"operation": "sum"})
    results = question.by(scenario).by(agent).run(disable_remote_cache=True, disable_remote_inference=True)
    assert results.select("answer.*").to_list()[0] == "15"
    
    # Test product operation
    agent = Agent(traits={"operation": "product"})
    results = question.by(scenario).by(agent).run(disable_remote_cache=True, disable_remote_inference=True)
    assert results.select("answer.*").to_list()[0] == "120"


def test_function_conversion():
    """Test conversion of Python functions to Jinja2 macros."""
    def calculate_total(scenario, agent_traits):
        base_price = scenario.get("price", 0)
        quantity = scenario.get("quantity", 1)
        discount = agent_traits.get("discount", 0) if agent_traits else 0
        
        total = base_price * quantity
        discounted = total * (1 - discount/100)
        return discounted
    
    # Create question with function conversion
    question = QuestionJinjaFunction(
        question_name="calculate_price",
        func_for_conversion=calculate_total,
        question_presentation="Price calculation function",
        answering_instructions="This is a computational question"
    )
    
    # Check that the template was generated
    assert "{% macro calculate_total" in question.jinja2_template
    assert "{% set base_price" in question.jinja2_template
    
    # Test the function
    scenario = Scenario({"price": 100, "quantity": 5})
    agent = Agent(traits={"discount": 20})
    results = question.by(scenario).by(agent).run(disable_remote_cache=True, disable_remote_inference=True)
    
    # The result might be a string due to Jinja2 conversion, so convert to float for comparison
    result = float(results.select("answer.*").to_list()[0])
    expected = 400.0  # 100*5*(1-20/100)
    assert abs(result - expected) < 0.01


def test_serialization_deserialization():
    """Test that questions can be serialized and deserialized correctly."""
    # Create original question
    original = QuestionJinjaFunction.example()
    
    # Serialize and deserialize
    question_dict = original.to_dict()
    recreated = QuestionBase.from_dict(question_dict)
    
    # Check question properties were preserved
    assert recreated.question_name == original.question_name
    assert recreated.jinja2_template == original.jinja2_template
    assert recreated.macro_name == original.macro_name
    
    # Test functionality preserved
    scenario = Scenario({"numbers": [1, 2, 3, 4, 5]})
    agent = Agent(traits={"multiplier": 10})
    
    original_result = original.by(scenario).by(agent).run(disable_remote_cache=True, disable_remote_inference=True)
    recreated_result = recreated.by(scenario).by(agent).run(disable_remote_cache=True, disable_remote_inference=True)
    
    assert original_result.select("answer.*").to_list()[0] == recreated_result.select("answer.*").to_list()[0]


def test_error_handling():
    """Test error handling in Jinja2 templates."""
    # Invalid template syntax
    with pytest.raises(ValueError):
        QuestionJinjaFunction(
            question_name="invalid",
            jinja2_template="{% macro broken(scenario, agent_traits) %}{{ unclosed syntax {% endmacro %}",
            macro_name="broken",
            question_presentation="Invalid template",
            answering_instructions="Should fail"
        )
    
    # Missing macro
    question = QuestionJinjaFunction(
        question_name="missing_macro",
        jinja2_template="{% macro existing(scenario, agent_traits) %}42{% endmacro %}",
        macro_name="non_existent",
        question_presentation="Missing macro test",
        answering_instructions="Should fail"
    )
    
    scenario = Scenario({})
    agent = Agent(traits={})
    
    with pytest.raises(Exception):
        question.by(scenario).by(agent).run(disable_remote_cache=True, disable_remote_inference=True)