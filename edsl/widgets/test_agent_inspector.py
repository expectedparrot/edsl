#!/usr/bin/env python3
"""
Test script for AgentInspectorWidget

This script creates sample agents and tests the widget functionality.
Run this script to verify the widget works correctly.
"""

import sys
import os

# Add the parent directory to the path so we can import the agent
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_agent_inspector_widget():
    """Test the AgentInspectorWidget with various agent configurations."""
    
    print("Testing AgentInspectorWidget...")
    
    try:
        # Import required modules
        from edsl.agents import Agent
        from edsl.widgets import AgentInspectorWidget
        
        print("✓ Successfully imported required modules")
        
        # Test 1: Basic agent
        print("\n--- Test 1: Basic Agent ---")
        basic_agent = Agent(
            name="Basic Test Agent",
            traits={
                "age": 30,
                "profession": "teacher",
                "experience_years": 5
            },
            instruction="Answer questions as a helpful teacher."
        )
        
        widget1 = AgentInspectorWidget(basic_agent)
        summary1 = widget1.export_summary()
        print(f"Basic agent summary: {summary1}")
        assert summary1['name'] == "Basic Test Agent"
        assert summary1['trait_count'] == 3
        print("✓ Basic agent test passed")
        
        # Test 2: Agent with codebook
        print("\n--- Test 2: Agent with Codebook ---")
        codebook_agent = Agent(
            name="Research Assistant",
            traits={
                "field": "computer_science",
                "education": "PhD",
                "specialization": "machine_learning",
                "publications": 15
            },
            codebook={
                "field": "Academic field of expertise",
                "education": "Highest level of education completed",
                "specialization": "Area of specialized research focus",
                "publications": "Number of peer-reviewed publications"
            },
            instruction="Respond from the perspective of a computer science researcher."
        )
        
        widget2 = AgentInspectorWidget(codebook_agent)
        summary2 = widget2.export_summary()
        print(f"Codebook agent summary: {summary2}")
        assert summary2['codebook_entries'] == 4
        print("✓ Codebook agent test passed")
        
        # Test 3: Agent with trait categories
        print("\n--- Test 3: Agent with Trait Categories ---")
        categorized_agent = Agent(
            name="Survey Participant",
            traits={
                "age": 25,
                "gender": "female",
                "income": 50000,
                "education": "bachelor",
                "city": "new_york",
                "state": "ny",
                "interests": ["reading", "hiking", "cooking"],
                "tech_usage": "high"
            },
            trait_categories={
                "demographics": ["age", "gender", "education"],
                "location": ["city", "state"],
                "economic": ["income"],
                "lifestyle": ["interests", "tech_usage"]
            }
        )
        
        widget3 = AgentInspectorWidget(categorized_agent)
        summary3 = widget3.export_summary()
        print(f"Categorized agent summary: {summary3}")
        assert summary3['has_categories'] == True
        print("✓ Categorized agent test passed")
        
        # Test 4: Search functionality
        print("\n--- Test 4: Search Functionality ---")
        search_results = widget2.search_traits("computer")
        print(f"Search results for 'computer': {list(search_results.keys())}")
        assert "field" in search_results
        print("✓ Search functionality test passed")
        
        # Test 5: Empty agent
        print("\n--- Test 5: Empty Agent ---")
        empty_agent = Agent()
        widget4 = AgentInspectorWidget(empty_agent)
        summary4 = widget4.export_summary()
        print(f"Empty agent summary: {summary4}")
        assert summary4['trait_count'] == 0
        print("✓ Empty agent test passed")
        
        # Test 6: Widget without agent
        print("\n--- Test 6: Widget without Agent ---")
        widget5 = AgentInspectorWidget()
        assert widget5.agent is None
        assert widget5.agent_data == {}
        print("✓ Widget without agent test passed")
        
        # Test 7: Method chaining
        print("\n--- Test 7: Method Chaining ---")
        widget6 = AgentInspectorWidget().inspect(basic_agent)
        assert widget6.agent == basic_agent
        print("✓ Method chaining test passed")
        
        print("\n🎉 All tests passed! The AgentInspectorWidget is working correctly.")
        
        return widget1  # Return a widget for optional display
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you're in the EDSL environment and all dependencies are installed.")
        return None
    except AssertionError as e:
        print(f"❌ Test assertion failed: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return None


def demo_widget():
    """Create a demo widget with a rich agent for interactive testing."""
    
    print("\n" + "="*60)
    print("Creating Demo AgentInspectorWidget")
    print("="*60)
    
    try:
        from edsl.agents import Agent
        from edsl.widgets import AgentInspectorWidget
        
        # Create a comprehensive demo agent
        demo_agent = Agent(
            name="Dr. Sarah Chen - AI Research Specialist",
            traits={
                # Demographics
                "age": 34,
                "gender": "female",
                "nationality": "canadian",
                
                # Professional
                "position": "senior_researcher",
                "institution": "university_of_toronto",
                "department": "computer_science",
                "years_experience": 12,
                
                # Expertise
                "primary_field": "artificial_intelligence",
                "specializations": ["natural_language_processing", "machine_learning", "ethics_in_ai"],
                "programming_languages": ["python", "r", "java", "cpp"],
                
                # Academic
                "education": "phd_computer_science",
                "publications": 47,
                "h_index": 23,
                "grants_received": 8,
                
                # Personal
                "interests": ["quantum_computing", "science_communication", "hiking"],
                "languages": ["english", "mandarin", "french"],
                "availability": "weekdays_9_to_5_est"
            },
            codebook={
                # Demographics
                "age": "Age in years",
                "gender": "Gender identity", 
                "nationality": "Country of citizenship",
                
                # Professional  
                "position": "Current job title/role",
                "institution": "Current workplace/affiliation",
                "department": "Academic department or division",
                "years_experience": "Total years of professional experience",
                
                # Expertise
                "primary_field": "Main area of academic/research focus",
                "specializations": "Specific research specialties within primary field",
                "programming_languages": "Programming languages proficiently used",
                
                # Academic
                "education": "Highest degree obtained",
                "publications": "Number of peer-reviewed publications",
                "h_index": "H-index citation metric",
                "grants_received": "Number of research grants awarded",
                
                # Personal
                "interests": "Professional interests and emerging areas of curiosity",
                "languages": "Languages spoken fluently",
                "availability": "Typical availability for consultations"
            },
            trait_categories={
                "demographics": ["age", "gender", "nationality"],
                "professional": ["position", "institution", "department", "years_experience"],
                "expertise": ["primary_field", "specializations", "programming_languages"],
                "academic": ["education", "publications", "h_index", "grants_received"],
                "personal": ["interests", "languages", "availability"]
            },
            instruction="""I am Dr. Sarah Chen, a senior AI researcher with expertise in natural language processing, machine learning, and AI ethics. 

I approach questions with:
- Deep technical knowledge backed by 12+ years of experience
- Awareness of current research trends and ethical implications  
- Clear explanations suitable for both technical and general audiences
- Evidence-based reasoning citing relevant research when appropriate

I'm particularly knowledgeable about:
• NLP model architectures and training methodologies
• Machine learning bias detection and mitigation
• AI safety and alignment principles
• Responsible AI deployment in industry settings
• Cross-cultural considerations in AI system design"""
        )
        
        # Create and return the widget
        widget = AgentInspectorWidget(demo_agent)
        
        print("Demo agent created with:")
        summary = widget.export_summary() 
        for key, value in summary.items():
            print(f"  - {key}: {value}")
            
        print("\nTo display the widget in Jupyter, use:")
        print("widget = demo_widget()")
        print("widget  # This will display the interactive widget")
        
        return widget
        
    except Exception as e:
        print(f"❌ Error creating demo widget: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    # Run tests
    widget = test_agent_inspector_widget()
    
    # Create demo if tests passed
    if widget is not None:
        demo = demo_widget()
        
        print(f"\n{'='*60}")
        print("AgentInspectorWidget is ready to use!")
        print(f"{'='*60}")
        print("\nIn Jupyter notebook, you can now use:")
        print("from edsl.widgets import AgentInspectorWidget")
        print("from edsl.agents import Agent")
        print("")
        print("agent = Agent(name='My Agent', traits={'key': 'value'})")
        print("widget = AgentInspectorWidget(agent)")
        print("widget  # Display the widget")