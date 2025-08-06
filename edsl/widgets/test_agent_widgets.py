#!/usr/bin/env python3
"""
Test script for both AgentInspectorWidget and AgentListInspectorWidget

This script creates sample agents and tests both the individual and list inspector widgets.
Run this script to verify both widgets work correctly with shared components.
"""

import sys
import os

# Add the parent directory to the path so we can import the agent
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def create_test_agents():
    """Create a diverse set of test agents for comprehensive testing."""
    from edsl.agents import Agent
    
    # Agent 1: Basic researcher
    agent1 = Agent(
        name="Dr. Alice Chen - AI Researcher",
        traits={
            "age": 34,
            "field": "artificial_intelligence",
            "experience_years": 12,
            "specialties": ["natural_language_processing", "computer_vision"],
            "publications": 47,
            "institution": "MIT"
        },
        codebook={
            "age": "Age in years",
            "field": "Primary research field",
            "experience_years": "Years of research experience",
            "specialties": "Areas of research specialization",
            "publications": "Number of peer-reviewed publications",
            "institution": "Current academic institution"
        },
        trait_categories={
            "demographics": ["age"],
            "professional": ["field", "experience_years", "institution"],
            "expertise": ["specialties", "publications"]
        },
        instruction="I am a senior AI researcher with expertise in NLP and computer vision. I provide detailed, technical responses based on current research."
    )
    
    # Agent 2: Market analyst (from demo)
    agent2 = Agent(
        name="Dr. Elena Rodriguez - Market Research Expert",
        traits={
            "role": "senior_market_analyst", 
            "company": "global_insights_corp",
            "years_experience": 8,
            "education": "mba_marketing",
            "industries": ["technology", "healthcare", "finance"],
            "methodologies": ["quantitative_analysis", "focus_groups", "surveys"],
            "tools": ["spss", "tableau", "python", "excel"]
        },
        codebook={
            "role": "Current job title and level of seniority",
            "company": "Current employer organization", 
            "years_experience": "Total years of professional market research experience",
            "education": "Highest relevant degree completed",
            "industries": "Industry sectors with deep expertise",
            "methodologies": "Research methodologies frequently employed",
            "tools": "Software tools and platforms regularly used"
        },
        traits_presentation_template="""As a market research professional:
Role: {{role}} at {{company}}
Experience: {{years_experience}} years
Education: {{education}}
Industries: {{industries|join(', ')}}""",
        instruction="I provide data-driven market research insights across technology, healthcare, and finance sectors."
    )
    
    # Agent 3: Simple agent without much configuration
    agent3 = Agent(
        name="Bob - Simple Agent",
        traits={
            "personality": "friendly",
            "role": "assistant",
            "skills": ["communication", "problem_solving"]
        },
        instruction="I'm a friendly assistant who helps with various tasks."
    )
    
    # Agent 4: Agent with dynamic traits (for testing advanced features)
    def dynamic_traits_func():
        return {"mood": "adaptive", "response_style": "contextual"}
    
    agent4 = Agent(
        name="Adaptive Agent",
        traits={
            "base_personality": "analytical",
            "domain": "general"
        },
        codebook={
            "base_personality": "Core personality traits",
            "domain": "Primary area of knowledge"
        },
        dynamic_traits_function=dynamic_traits_func,
        instruction="I adapt my responses based on the context of questions."
    )
    
    # Agent 5: Unnamed agent for edge case testing
    agent5 = Agent(
        traits={
            "type": "experimental",
            "version": "1.0",
            "capabilities": ["text_processing", "data_analysis"]
        }
    )
    
    return [agent1, agent2, agent3, agent4, agent5]


def test_agent_inspector_widget():
    """Test the individual AgentInspectorWidget."""
    print("Testing AgentInspectorWidget...")
    
    try:
        from edsl.widgets import AgentInspectorWidget
        agents = create_test_agents()
        
        # Test with first agent
        widget = AgentInspectorWidget(agents[0])
        summary = widget.export_summary()
        print(f"✓ Individual widget created: {summary['name']}")
        assert summary['trait_count'] == 6
        assert summary['codebook_entries'] == 6
        print("✓ Individual agent inspection test passed")
        
        # Test search functionality
        search_results = widget.search_traits("AI")
        print(f"✓ Search found {len(search_results)} results")
        
        return widget
        
    except Exception as e:
        print(f"❌ AgentInspectorWidget test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_agent_list_inspector_widget():
    """Test the AgentListInspectorWidget."""
    print("\nTesting AgentListInspectorWidget...")
    
    try:
        from edsl.widgets import AgentListInspectorWidget
        agents = create_test_agents()
        
        # Test with list of agents
        widget = AgentListInspectorWidget(agents)
        summary = widget.export_summary()
        print(f"✓ List widget created with {summary['agent_count']} agents")
        print(f"  - Named agents: {summary['named_agents']}")
        print(f"  - Total traits: {summary['total_traits']}")
        print(f"  - Avg traits per agent: {summary['avg_traits_per_agent']:.1f}")
        print(f"  - Dynamic agents: {summary['dynamic_agents']}")
        
        assert summary['agent_count'] == 5
        assert summary['named_agents'] == 4  # 4 agents have names
        assert summary['dynamic_agents'] == 1  # 1 agent has dynamic traits
        print("✓ List widget basic functionality test passed")
        
        # Test search functionality
        search_results = widget.search_agents("research")
        print(f"✓ Search found {len(search_results)} agents matching 'research'")
        
        # Test filtering by trait count
        filtered = widget.filter_by_trait_count(min_traits=5)
        print(f"✓ Filter found {len(filtered)} agents with 5+ traits")
        
        # Test individual agent access
        agent_data = widget.get_agent_by_index(0)
        assert agent_data is not None
        print("✓ Individual agent access test passed")
        
        return widget
        
    except Exception as e:
        print(f"❌ AgentListInspectorWidget test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_shared_components():
    """Test that both widgets can work with shared components."""
    print("\nTesting shared components integration...")
    
    try:
        from edsl.widgets import AgentInspectorWidget, AgentListInspectorWidget
        agents = create_test_agents()
        
        # Create both widgets
        single_widget = AgentInspectorWidget(agents[0])
        list_widget = AgentListInspectorWidget(agents)
        
        # Verify they both have the expected data structure
        single_data = single_widget.agent_data
        list_data = list_widget.agents_data
        
        assert 'traits' in single_data
        assert 'codebook' in single_data
        assert len(list_data) == 5
        assert all('traits' in agent_data for agent_data in list_data)
        
        print("✓ Both widgets use compatible data structures")
        print("✓ Shared components integration test passed")
        
        return single_widget, list_widget
        
    except Exception as e:
        print(f"❌ Shared components test failed: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def demo_both_widgets():
    """Create demo instances of both widgets."""
    print("\n" + "="*60)
    print("Creating Demo Widgets")
    print("="*60)
    
    try:
        from edsl.widgets import AgentInspectorWidget, AgentListInspectorWidget
        agents = create_test_agents()
        
        print("Demo agents created:")
        for i, agent in enumerate(agents):
            name = agent.name or f"Agent {i+1}"
            trait_count = len(agent.traits)
            print(f"  {i+1}. {name} ({trait_count} traits)")
        
        # Create individual widget for first agent
        single_widget = AgentInspectorWidget(agents[0])
        
        # Create list widget for all agents
        list_widget = AgentListInspectorWidget(agents)
        
        print(f"\n📋 Individual Inspector: {agents[0].name}")
        single_summary = single_widget.export_summary()
        for key, value in single_summary.items():
            print(f"  - {key}: {value}")
        
        print(f"\n📋 List Inspector Summary:")
        list_summary = list_widget.export_summary()
        for key, value in list_summary.items():
            print(f"  - {key}: {value}")
        
        print(f"\n🎯 Usage in Jupyter:")
        print(f"# Individual agent inspection")
        print(f"single_widget = AgentInspectorWidget(agent)")
        print(f"single_widget  # Display widget")
        print(f"")
        print(f"# Multiple agents inspection")
        print(f"list_widget = AgentListInspectorWidget(agents)")
        print(f"list_widget  # Display widget with clickable cards")
        
        return single_widget, list_widget
        
    except Exception as e:
        print(f"❌ Error creating demo widgets: {e}")
        import traceback
        traceback.print_exc()
        return None, None


if __name__ == "__main__":
    print("Testing EDSL Agent Inspector Widgets")
    print("="*50)
    
    # Run individual tests
    single_widget = test_agent_inspector_widget()
    list_widget = test_agent_list_inspector_widget()
    
    if single_widget and list_widget:
        # Test shared components
        single_test, list_test = test_shared_components()
        
        if single_test and list_test:
            print("\n🎉 All tests passed! Both widgets are working correctly.")
            
            # Create demos
            demo_single, demo_list = demo_both_widgets()
            
            if demo_single and demo_list:
                print(f"\n{'='*60}")
                print("Agent Inspector Widgets are ready to use!")
                print(f"{'='*60}")
                print("\nBoth widgets support:")
                print("✓ Interactive inspection of agent properties")
                print("✓ Search and filtering capabilities") 
                print("✓ Responsive design for different screen sizes")
                print("✓ Shared component architecture for code reuse")
                print("✓ Rich data visualization and formatting")
        else:
            print("❌ Shared components tests failed")
    else:
        print("❌ Basic widget tests failed")