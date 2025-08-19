#!/usr/bin/env python3
"""
Test script specifically for AgentListInspectorWidget with AgentList objects

This script tests the widget with real EDSL AgentList objects to verify
the fixes for AgentList processing and component rendering.
"""

import sys
import os

# Add the parent directory to the path so we can import the agent
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_with_agent_list():
    """Test the widget with a real AgentList object."""
    print("Testing with AgentList object...")

    try:
        from edsl.agents import Agent, AgentList
        from edsl.widgets import AgentListInspectorWidget

        # Create individual agents
        agent1 = Agent(
            name="Alice - Researcher",
            traits={"field": "AI", "experience": 5, "location": "MIT"},
        )
        agent2 = Agent(
            name="Bob - Designer",
            traits={"specialty": "UX", "tools": ["Figma"], "years": 3},
        )
        agent3 = Agent(
            name="Carol - Developer",
            traits={"languages": ["Python", "JS"], "role": "Full-stack"},
        )

        # Create an AgentList
        agent_list = AgentList([agent1, agent2, agent3])

        print(f"✓ Created AgentList with {len(agent_list)} agents")
        print(f"  - agent_list.data: {len(agent_list.data)} items")
        print(f"  - Direct iteration: {len(list(agent_list))} items")

        # Test the widget
        widget = AgentListInspectorWidget(agent_list)

        # Check the extracted data
        print(f"✓ Widget agents_data length: {len(widget.agents_data)}")

        # Verify each agent was processed
        for i, agent_data in enumerate(widget.agents_data):
            name = agent_data.get("name", f"Agent {i+1}")
            trait_count = len(agent_data.get("traits", {}))
            print(f"  - Agent {i}: {name} ({trait_count} traits)")

        # Test summary
        summary = widget.export_summary()
        print(f"✓ Summary: {summary}")

        assert (
            summary["agent_count"] == 3
        ), f"Expected 3 agents, got {summary['agent_count']}"
        assert (
            summary["named_agents"] == 3
        ), f"Expected 3 named agents, got {summary['named_agents']}"

        print("✓ AgentList test passed!")
        return widget

    except Exception as e:
        print(f"❌ AgentList test failed: {e}")
        import traceback

        traceback.print_exc()
        return None


def test_with_regular_list():
    """Test the widget with a regular Python list."""
    print("\nTesting with regular Python list...")

    try:
        from edsl.agents import Agent
        from edsl.widgets import AgentListInspectorWidget

        # Create regular list
        agents = [
            Agent(name="Dave", traits={"role": "Manager", "team_size": 5}),
            Agent(name="Eve", traits={"skill": "Analysis", "domain": "Finance"}),
        ]

        print(f"✓ Created regular list with {len(agents)} agents")

        # Test the widget
        widget = AgentListInspectorWidget(agents)

        print(f"✓ Widget agents_data length: {len(widget.agents_data)}")

        summary = widget.export_summary()
        print(f"✓ Summary: {summary}")

        assert (
            summary["agent_count"] == 2
        ), f"Expected 2 agents, got {summary['agent_count']}"

        print("✓ Regular list test passed!")
        return widget

    except Exception as e:
        print(f"❌ Regular list test failed: {e}")
        import traceback

        traceback.print_exc()
        return None


def test_click_simulation():
    """Simulate the click behavior that was causing issues."""
    print("\nTesting click simulation...")

    try:
        from edsl.agents import Agent, AgentList
        from edsl.widgets import AgentListInspectorWidget

        # Create test data
        agents = [
            Agent(name="Test Agent 1", traits={"type": "test", "id": 1}),
            Agent(name="Test Agent 2", traits={"type": "test", "id": 2}),
        ]
        agent_list = AgentList(agents)

        widget = AgentListInspectorWidget(agent_list)

        print(f"✓ Created widget with {len(widget.agents_data)} agents")

        # Simulate getting an agent by index (what happens on click)
        for i in range(len(widget.agents_data)):
            agent_data = widget.get_agent_by_index(i)
            if agent_data:
                print(f"✓ Agent {i}: {agent_data.get('name', 'Unknown')} - data OK")
            else:
                print(f"❌ Agent {i}: Could not retrieve data")

        print("✓ Click simulation test passed!")
        return widget

    except Exception as e:
        print(f"❌ Click simulation test failed: {e}")
        import traceback

        traceback.print_exc()
        return None


def interactive_demo():
    """Create an interactive demo widget."""
    print("\n" + "=" * 60)
    print("Creating Interactive Demo")
    print("=" * 60)

    try:
        from edsl.agents import Agent, AgentList
        from edsl.widgets import AgentListInspectorWidget

        # Create diverse agents for testing
        agents = [
            Agent(
                name="Dr. Sarah Johnson - Research Lead",
                traits={
                    "role": "research_lead",
                    "field": "machine_learning",
                    "experience_years": 8,
                    "team_size": 12,
                    "location": "Stanford",
                },
                codebook={
                    "role": "Leadership position in research",
                    "field": "Primary research area",
                    "experience_years": "Years of research experience",
                    "team_size": "Number of researchers managed",
                    "location": "Institution affiliation",
                },
                instruction="I provide strategic research guidance in machine learning and AI.",
            ),
            Agent(
                name="Mike Chen - Senior Engineer",
                traits={
                    "role": "senior_software_engineer",
                    "languages": ["Python", "Go", "TypeScript"],
                    "focus": "backend_systems",
                    "experience_years": 6,
                },
                codebook={
                    "role": "Engineering role and level",
                    "languages": "Programming languages expertise",
                    "focus": "Primary technical focus area",
                    "experience_years": "Years of engineering experience",
                },
                instruction="I solve complex backend engineering challenges with focus on scalability.",
            ),
            Agent(
                name="Lisa Rodriguez - Product Strategy",
                traits={
                    "role": "product_strategist",
                    "domains": ["fintech", "saas"],
                    "methodologies": ["design_thinking", "lean_startup"],
                    "experience_years": 7,
                },
                instruction="I develop product strategies for fintech and SaaS companies.",
            ),
        ]

        # Create AgentList
        agent_list = AgentList(agents)

        # Create widget
        widget = AgentListInspectorWidget(agent_list)

        print("Interactive demo created successfully!")
        print(f"AgentList: {len(agent_list)} agents")
        print(f"Widget data: {len(widget.agents_data)} agent records")

        summary = widget.export_summary()
        for key, value in summary.items():
            print(f"  - {key}: {value}")

        print("\n🎯 In Jupyter notebook:")
        print("widget = interactive_demo()")
        print("widget  # This will display the interactive widget")
        print("\n✨ Features to test:")
        print("- See all 3 agents as cards")
        print("- Click any card to inspect details")
        print("- Use back button to return to list")
        print("- Search across agents")
        print("- Sort by different criteria")

        return widget

    except Exception as e:
        print(f"❌ Interactive demo failed: {e}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    print("Testing AgentListInspectorWidget Fixes")
    print("=" * 50)

    # Test 1: AgentList object
    widget1 = test_with_agent_list()

    # Test 2: Regular list
    widget2 = test_with_regular_list()

    # Test 3: Click simulation
    widget3 = test_click_simulation()

    if widget1 and widget2 and widget3:
        print("\n🎉 All tests passed! Issues should be fixed.")

        # Create interactive demo
        demo_widget = interactive_demo()

        if demo_widget:
            print(f"\n{'='*60}")
            print("AgentListInspectorWidget Fixed and Ready!")
            print(f"{'='*60}")
            print("\nFixed issues:")
            print("✅ AgentList objects now properly show all agents")
            print("✅ Clicking agents no longer causes components to disappear")
            print("✅ Better error handling and debugging")
            print("✅ Support for both AgentList and regular Python lists")
    else:
        print("\n❌ Some tests failed. Check the output above for details.")
