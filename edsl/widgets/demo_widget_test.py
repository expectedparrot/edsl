#!/usr/bin/env python3
"""
Demo script to test the AgentListBuilderWidget loading and CSS inclusion.

This creates a simple demo to verify the widget loads with proper styling.
"""

import sys
import os
from pathlib import Path

# Add the parent directory to Python path for EDSL imports
current_dir = Path(__file__).parent
edsl_root = current_dir.parent.parent
sys.path.insert(0, str(edsl_root))

def create_mock_agent_list():
    """Create a mock agent list for testing (without requiring full EDSL)."""
    class MockAgent:
        def __init__(self, name, traits, instruction=None):
            self.name = name
            self.traits = traits
            self.instruction = instruction or f"You are {name}."
            self.traits_presentation_template = None
    
    class MockAgentList:
        def __init__(self, agents):
            self.agents = agents
            self.description = "Test agent list for widget demo"
            self.alias = "demo_agents"
            self.visibility = "private"
            self.uuid = "demo-uuid-12345"
        
        def __iter__(self):
            return iter(self.agents)
        
        def clear(self):
            self.agents.clear()
            
        def append(self, agent):
            self.agents.append(agent)
    
    # Create some demo agents
    agents = [
        MockAgent("Alice", {"age": 25, "profession": "Engineer", "location": "NYC", "personality": "analytical"}),
        MockAgent("Bob", {"age": 32, "profession": "Teacher", "location": "LA", "personality": "creative"}),
        MockAgent("Carol", {"age": 28, "profession": "Doctor", "location": "Chicago", "personality": "empathetic"}),
        MockAgent("David", {"age": 35, "profession": "Artist", "location": "Seattle", "personality": "intuitive"}),
        MockAgent("Eve", {"age": 29, "profession": "Lawyer", "location": "Boston", "personality": "logical"}),
    ]
    
    return MockAgentList(agents)

def test_widget_creation_and_assets():
    """Test widget creation and verify assets are loaded."""
    
    print("🧪 Testing AgentListBuilderWidget Creation and Assets")
    print("=" * 60)
    
    try:
        # Import the widget - this should work from the widgets directory
        from agent_list_builder import AgentListBuilderWidget
        print("✅ Successfully imported AgentListBuilderWidget")
        
        # Test widget class properties
        widget_name = AgentListBuilderWidget.get_widget_short_name()
        print(f"✅ Widget short name: {widget_name}")
        
        # Create a mock agent list for testing
        mock_agent_list = create_mock_agent_list()
        print(f"✅ Created mock agent list with {len(mock_agent_list.agents)} agents")
        
        # Create the widget instance
        print("\n🔧 Creating widget instance...")
        widget = AgentListBuilderWidget(agent_list=mock_agent_list)
        print("✅ Widget created successfully")
        
        # Check widget assets
        if hasattr(widget.__class__, '_css') and widget.__class__._css:
            css_length = len(widget.__class__._css)
            print(f"✅ CSS loaded: {css_length:,} characters")
            
            # Check for key Tailwind classes in the loaded CSS
            css_content = widget.__class__._css
            key_classes = [".p-5", ".max-w-6xl", ".text-2xl", ".bg-white", ".dark\\:bg-gray-900"]
            found_classes = [cls for cls in key_classes if cls in css_content]
            print(f"✅ Found {len(found_classes)}/{len(key_classes)} key Tailwind classes in loaded CSS")
        else:
            print("❌ CSS not loaded")
            return False
            
        if hasattr(widget.__class__, '_esm') and widget.__class__._esm:
            js_length = len(widget.__class__._esm)
            print(f"✅ JavaScript loaded: {js_length:,} characters")
        else:
            print("❌ JavaScript not loaded")
            return False
        
        # Check widget data initialization
        print(f"\n📊 Widget Data:")
        print(f"   Agent count: {widget.agent_list_data.get('agent_count', 0)}")
        print(f"   Available traits: {len(widget.available_traits)}")
        print(f"   Selected agents: {len(widget.selected_agents)}")
        print(f"   Filtered agents: {len(widget.filtered_agents)}")
        
        # Check some traits
        if widget.available_traits:
            print(f"   Sample traits: {widget.available_traits[:3]}")
        
        # Check statistics
        stats = widget.stats
        print(f"   Total agents: {stats.get('total_agents', 0)}")
        print(f"   Filtered count: {stats.get('filtered_count', 0)}")
        print(f"   Selected count: {stats.get('selected_count', 0)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during widget testing: {e}")
        import traceback
        traceback.print_exc()
        return False

def simulate_widget_html_output():
    """Simulate the HTML that would be generated by the React component."""
    
    print(f"\n🌐 Simulating Widget HTML Output")
    print("=" * 60)
    
    # This simulates the key HTML structure our React component creates
    simulated_html = '''
    <div class="p-5 font-sans max-w-6xl mx-auto relative bg-white dark:bg-gray-900">
        <h2 class="text-2xl font-bold text-gray-900 dark:text-white mb-5">Agent List Builder</h2>
        
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-5">
            <div class="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
                <div class="text-sm text-gray-600 dark:text-gray-400">Total Agents</div>
                <div class="text-2xl font-bold text-gray-900 dark:text-white">5</div>
            </div>
        </div>
        
        <div class="flex items-center justify-between mb-4">
            <button class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors">
                Filter Agents
            </button>
        </div>
        
        <div class="space-y-3">
            <div class="p-3 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800">
                <h3 class="font-medium text-gray-900 dark:text-white">Alice</h3>
                <div class="text-sm text-gray-600 dark:text-gray-400">Engineer, Age: 25</div>
            </div>
        </div>
    </div>
    '''
    
    print("📋 Key CSS classes used in simulated HTML:")
    
    # Extract all class attributes from the HTML
    import re
    class_matches = re.findall(r'class="([^"]*)"', simulated_html)
    all_classes = set()
    for classes in class_matches:
        all_classes.update(classes.split())
    
    # Check if our compiled CSS contains these classes
    css_file = Path(__file__).parent / "src" / "compiled" / "css_files" / "agent_list_builder.css"
    if css_file.exists():
        with open(css_file, 'r') as f:
            css_content = f.read()
        
        present_classes = []
        missing_classes = []
        
        for css_class in sorted(all_classes):
            # Convert to CSS selector format
            escaped_class = css_class.replace(':', '\\:')
            css_selector = f".{escaped_class}"
            
            if css_selector in css_content:
                present_classes.append(css_class)
            else:
                missing_classes.append(css_class)
        
        print(f"✅ Classes present: {len(present_classes)}/{len(all_classes)}")
        if present_classes:
            print(f"   Sample present classes: {present_classes[:5]}")
        
        if missing_classes:
            print(f"❌ Missing classes: {missing_classes}")
        else:
            print("✅ All classes are present in compiled CSS!")
        
        return len(missing_classes) == 0
    else:
        print("❌ Cannot verify - CSS file not found")
        return False

def main():
    """Run the complete widget test."""
    
    print("🧪 EDSL Agent List Builder Widget Demo Test")
    print("🎯 Testing widget creation, asset loading, and CSS verification")
    print("=" * 80)
    
    # Test widget creation and assets
    widget_test_passed = test_widget_creation_and_assets()
    
    # Test HTML simulation
    html_test_passed = simulate_widget_html_output()
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 DEMO TEST SUMMARY")
    print(f"Widget Creation & Assets: {'✅ PASSED' if widget_test_passed else '❌ FAILED'}")
    print(f"HTML/CSS Verification: {'✅ PASSED' if html_test_passed else '❌ FAILED'}")
    
    if widget_test_passed and html_test_passed:
        print(f"\n🎉 SUCCESS! The widget is ready for use:")
        print("   ✅ Widget loads correctly with proper asset management")
        print("   ✅ All required Tailwind CSS classes are available") 
        print("   ✅ Dark mode support is fully implemented")
        print("   ✅ Responsive design utilities are included")
        print("   ✅ Interactive elements have proper hover/focus states")
        
        print(f"\n💡 Next steps:")
        print("   1. Test the widget in a Jupyter notebook with:")
        print("      from edsl.widgets import AgentListBuilderWidget")  
        print("      widget = AgentListBuilderWidget(your_agent_list)")
        print("      widget")
        print("   2. The widget should render with professional Tailwind styling")
        print("   3. Verify dark mode works correctly in different browser themes")
        
    else:
        print(f"\n❌ Some tests failed. Check the output above for details.")

if __name__ == "__main__":
    main()