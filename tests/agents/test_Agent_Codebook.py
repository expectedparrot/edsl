import pytest
from edsl.agents import Agent

def test_agent_prompt_with_codebook():
    """Test that an agent with a codebook renders traits using codebook values."""
    # Create agent with traits and codebook
    traits = {"age": 30, "occupation": "engineer", "hobbies": "coding"}
    codebook = {
        "age": "Age in years",
        "occupation": "Current profession",
        "hobbies": "Leisure activities"
    }
    agent = Agent(traits=traits, codebook=codebook)
    
    # Get the rendered prompt
    prompt_result = agent.prompt()
    
    # Verify that codebook descriptions are used in the prompt
    assert "Age in years: 30" in prompt_result.text
    assert "Current profession: engineer" in prompt_result.text
    assert "Leisure activities: coding" in prompt_result.text
    
    # Verify the raw trait keys are not displayed
    assert "age: 30" not in prompt_result.text
    assert "occupation: engineer" not in prompt_result.text
    assert "hobbies: coding" not in prompt_result.text

def test_agent_prompt_with_partial_codebook():
    """Test that an agent with a partial codebook renders mixed traits properly."""
    # Create agent with traits and partial codebook
    traits = {"age": 30, "occupation": "engineer", "hobbies": "coding"}
    codebook = {
        "age": "Age in years",
        "occupation": "Current profession"
        # No entry for hobbies
    }
    agent = Agent(traits=traits, codebook=codebook)
    
    # Get the rendered prompt
    prompt_result = agent.prompt()
    
    # Verify that codebook descriptions are used for traits with codebook entries
    assert "Age in years: 30" in prompt_result.text
    assert "Current profession: engineer" in prompt_result.text
    
    # Verify that raw keys are used for traits without codebook entries
    assert "hobbies: coding" in prompt_result.text

def test_agent_prompt_codebook_change():
    """Test that updating the codebook after initialization updates the prompt."""
    # Create agent with traits but no codebook
    traits = {"age": 30, "occupation": "engineer"}
    agent = Agent(traits=traits)
    
    # Get the initial prompt without codebook
    initial_prompt = agent.prompt()
    assert "Your traits: " in initial_prompt.text
    assert "{'age': 30, 'occupation': 'engineer'}" in initial_prompt.text
    
    # Add a codebook
    agent.codebook = {"age": "Age in years", "occupation": "Current profession"}
    
    # Get the updated prompt with codebook
    updated_prompt = agent.prompt()
    assert "Age in years: 30" in updated_prompt.text
    assert "Current profession: engineer" in updated_prompt.text

def test_agent_prompt_custom_template_priority():
    """Test that custom templates take priority over the codebook-based template."""
    # Create agent with traits, codebook, and custom template
    traits = {"age": 30, "occupation": "engineer"}
    codebook = {"age": "Age in years", "occupation": "Current profession"}
    custom_template = "Person info: Age {{age}}, Job {{occupation}}"
    
    agent = Agent(traits=traits, codebook=codebook, traits_presentation_template=custom_template)
    
    # Get the rendered prompt
    prompt_result = agent.prompt()
    
    # Verify that the custom template is used, not the codebook-based template
    assert "Person info: Age 30, Job engineer" in prompt_result.text
    assert "Age in years: 30" not in prompt_result.text
    assert "Current profession: engineer" not in prompt_result.text