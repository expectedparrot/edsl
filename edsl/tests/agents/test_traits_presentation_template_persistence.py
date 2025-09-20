"""Tests for traits_presentation_template persistence fix.

This module tests the fix for Issue #2242 where setting traits_presentation_template
after agent construction was not persisting in serialization.
"""

from edsl.agents import Agent


def test_traits_presentation_template_constructor_persistence():
    """Test that traits_presentation_template set in constructor persists in serialization."""
    template = "hello, world!"
    agent = Agent(traits_presentation_template=template)

    # Should appear in serialization
    agent_dict = agent.to_dict()
    assert "traits_presentation_template" in agent_dict
    assert agent_dict["traits_presentation_template"] == template


def test_traits_presentation_template_setter_persistence():
    """Test that traits_presentation_template set after construction persists in serialization.

    This is the specific bug reported in Issue #2242 - setting traits_presentation_template
    after construction should persist in to_dict() output.
    """
    # Create agent without traits_presentation_template
    agent = Agent.example()

    # Set traits_presentation_template after construction
    template = "hello, world!"
    agent.traits_presentation_template = template

    # Verify it's accessible via property
    assert agent.traits_presentation_template == template

    # Verify it persists in serialization (this was the bug)
    agent_dict = agent.to_dict()
    assert "traits_presentation_template" in agent_dict
    assert agent_dict["traits_presentation_template"] == template


def test_traits_presentation_template_setter_flag():
    """Test that setting traits_presentation_template sets the persistence flag."""
    agent = Agent.example()

    # Initially flag should be False since not set in constructor
    assert not agent.set_traits_presentation_template

    # Setting the template should set the flag
    agent.traits_presentation_template = "test template"
    assert agent.set_traits_presentation_template

    # And should persist in serialization
    agent_dict = agent.to_dict()
    assert "traits_presentation_template" in agent_dict


def test_traits_presentation_template_roundtrip():
    """Test that traits_presentation_template survives serialization roundtrip."""
    # Create agent and set template after construction
    original_agent = Agent.example()
    template = "I am {{age}} years old with {{hair}} hair."
    original_agent.traits_presentation_template = template

    # Serialize and deserialize
    agent_dict = original_agent.to_dict()
    reconstructed_agent = Agent.from_dict(agent_dict)

    # Should preserve the template
    assert reconstructed_agent.traits_presentation_template == template
    assert reconstructed_agent.set_traits_presentation_template

    # And should still persist in subsequent serialization
    new_dict = reconstructed_agent.to_dict()
    assert "traits_presentation_template" in new_dict
    assert new_dict["traits_presentation_template"] == template


def test_traits_presentation_template_default_behavior():
    """Test that agents without custom template don't serialize it by default."""
    # Create agent without setting traits_presentation_template
    agent = Agent.example()

    # Should not appear in serialization since it's the default
    agent_dict = agent.to_dict()
    assert "traits_presentation_template" not in agent_dict

    # Flag should be False
    assert not agent.set_traits_presentation_template