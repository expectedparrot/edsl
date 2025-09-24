#!/usr/bin/env python3
"""
Test script to verify CSS loading for the agent_list_builder widget.

This script tests:
1. Widget initialization
2. CSS file loading
3. HTML output inspection
4. Tailwind CSS class verification
"""

import os
import sys
from pathlib import Path

# Add the parent directories to the path for imports
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

def test_widget_css_loading():
    """Test that the AgentListBuilderWidget loads CSS correctly."""
    try:
        # Import the widget
        sys.path.insert(0, str(current_dir))
        from agent_list_builder import AgentListBuilderWidget
        
        print("✅ Successfully imported AgentListBuilderWidget")
        
        # Test widget short name
        widget_name = AgentListBuilderWidget.get_widget_short_name()
        print(f"✅ Widget short name: {widget_name}")
        
        # Test CSS file existence
        css_file_path = current_dir / "src" / "compiled" / "css_files" / f"{widget_name}.css"
        print(f"🔍 Looking for CSS file at: {css_file_path}")
        
        if css_file_path.exists():
            print("✅ CSS file exists")
            
            # Read CSS content
            with open(css_file_path, 'r', encoding='utf-8') as f:
                css_content = f.read()
            
            print(f"📊 CSS file size: {len(css_content)} characters")
            
            # Check for key Tailwind classes that our React component uses
            required_classes = [
                '.p-5',
                '.max-w-6xl', 
                '.text-2xl',
                '.bg-white',
                '.dark\\:bg-gray-900',
                '.flex',
                '.items-center',
                '.hover\\:bg-gray-50'
            ]
            
            missing_classes = []
            found_classes = []
            
            for cls in required_classes:
                if cls in css_content:
                    found_classes.append(cls)
                else:
                    missing_classes.append(cls)
            
            if found_classes:
                print(f"✅ Found {len(found_classes)} required CSS classes:")
                for cls in found_classes[:5]:  # Show first 5
                    print(f"   - {cls}")
                if len(found_classes) > 5:
                    print(f"   ... and {len(found_classes) - 5} more")
            
            if missing_classes:
                print(f"❌ Missing {len(missing_classes)} required CSS classes:")
                for cls in missing_classes:
                    print(f"   - {cls}")
            
            # Test widget instantiation and asset loading
            print("\n🔧 Testing widget instantiation...")
            widget = AgentListBuilderWidget()
            print("✅ Widget instantiated successfully")
            
            # Check if the widget has loaded its assets
            if hasattr(widget.__class__, '_css') and widget.__class__._css:
                print("✅ Widget has loaded CSS content")
                widget_css_length = len(widget.__class__._css)
                print(f"📊 Widget CSS content size: {widget_css_length} characters")
                
                # Verify the CSS content matches the file
                if widget_css_length == len(css_content):
                    print("✅ Widget CSS matches file content exactly")
                else:
                    print(f"⚠️ Widget CSS size differs from file: {widget_css_length} vs {len(css_content)}")
            else:
                print("❌ Widget CSS not loaded or empty")
                
            # Test a few key widget properties
            print(f"📋 Widget properties:")
            print(f"   - Loading state: {widget.loading}")
            print(f"   - Error message: {repr(widget.error_message)}")
            print(f"   - Agent list data keys: {list(widget.agent_list_data.keys())}")
            
            return True
            
        else:
            print(f"❌ CSS file not found at {css_file_path}")
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return False

def test_html_output_simulation():
    """Simulate HTML output to verify CSS classes would be applied correctly."""
    print("\n🌐 Testing HTML output simulation...")
    
    # Simulate the key HTML structure that the React component generates
    html_structure = {
        "root_container": ["p-5", "font-sans", "max-w-6xl", "mx-auto", "relative", "bg-white", "dark:bg-gray-900"],
        "header": ["text-2xl", "font-bold", "text-gray-900", "dark:text-white"],
        "stats_grid": ["grid", "grid-cols-1", "lg:grid-cols-3", "gap-4", "mb-5"],
        "button": ["px-4", "py-2", "bg-blue-600", "hover:bg-blue-700", "text-white", "rounded", "transition-colors"],
        "agent_card": ["p-3", "border", "border-gray-200", "dark:border-gray-700", "rounded-lg", "hover:bg-gray-50", "dark:hover:bg-gray-800"]
    }
    
    css_file_path = Path(__file__).parent / "src" / "compiled" / "css_files" / "agent_list_builder.css"
    
    if css_file_path.exists():
        with open(css_file_path, 'r', encoding='utf-8') as f:
            css_content = f.read()
        
        all_classes_found = True
        total_classes = 0
        found_classes = 0
        
        for element, classes in html_structure.items():
            total_classes += len(classes)
            element_found = 0
            print(f"\n🔍 Testing element: {element}")
            
            for css_class in classes:
                # Convert class name to CSS selector format for searching
                escaped_class = css_class.replace(':', '\\:')
                css_selector = f".{escaped_class}"
                if css_selector in css_content:
                    element_found += 1
                    found_classes += 1
                else:
                    print(f"   ❌ Missing class: {css_class}")
                    all_classes_found = False
            
            if element_found == len(classes):
                print(f"   ✅ All {len(classes)} classes found")
            else:
                print(f"   ⚠️ Found {element_found}/{len(classes)} classes")
        
        print(f"\n📊 Overall results:")
        print(f"   Total classes tested: {total_classes}")
        print(f"   Classes found: {found_classes}")
        print(f"   Success rate: {(found_classes/total_classes)*100:.1f}%")
        
        if all_classes_found:
            print("✅ All CSS classes are available - widget should render correctly!")
        else:
            print("⚠️ Some CSS classes are missing - widget styling may be incomplete")
        
        return all_classes_found
    else:
        print("❌ Cannot test HTML output - CSS file not found")
        return False

def main():
    """Run all tests."""
    print("🧪 Testing Agent List Builder Widget CSS Loading\n")
    print("=" * 60)
    
    # Test 1: Basic CSS loading
    print("\n📋 Test 1: Basic CSS Loading")
    css_test_passed = test_widget_css_loading()
    
    # Test 2: HTML output simulation
    print("\n📋 Test 2: HTML Output Simulation")
    html_test_passed = test_html_output_simulation()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print(f"CSS Loading Test: {'✅ PASSED' if css_test_passed else '❌ FAILED'}")
    print(f"HTML Simulation Test: {'✅ PASSED' if html_test_passed else '⚠️ PARTIAL'}")
    
    if css_test_passed and html_test_passed:
        print("\n🎉 All tests passed! The widget should render with proper styling.")
    elif css_test_passed:
        print("\n⚠️ CSS loads correctly but some classes may be missing.")
    else:
        print("\n❌ CSS loading failed. Widget may not render correctly.")
    
    print("\n💡 Next steps:")
    print("   1. Test the widget in a Jupyter notebook")
    print("   2. Inspect the rendered HTML in browser dev tools")
    print("   3. Verify Tailwind classes are being applied correctly")

if __name__ == "__main__":
    main()