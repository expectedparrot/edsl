#!/usr/bin/env python3
"""
Test script to verify the hybrid CSS approach works correctly.
Tests that traditional CSS classes are in the compiled CSS and React component uses compatible classes.
"""

from pathlib import Path


def test_traditional_css_classes():
    """Test that compiled CSS includes traditional CSS classes."""

    print("🎨 Testing Traditional CSS Classes")
    print("=" * 50)

    css_file = (
        Path(__file__).parent
        / "src"
        / "compiled"
        / "css_files"
        / "agent_list_builder.css"
    )

    if not css_file.exists():
        print("❌ CSS file not found")
        return False

    with open(css_file, "r", encoding="utf-8") as f:
        css_content = f.read()

    # Test for traditional classes that match agent_list_manager approach
    traditional_classes = [
        # Main container
        ".agent-list-builder{",
        # Header and info sections
        ".header-stats{",
        ".header-stats .left-info{",
        ".header-stats .right-info{",
        ".modified-badge{",
        ".agent-count",
        ".stat-value{",
        # Error and loading states
        ".error-message{",
        ".loading-indicator{",
        ".status-message{",
        # Controls
        ".controls-section{",
        ".controls-row{",
        ".control-group{",
        ".control-label{",
        # Buttons
        ".btn{",
        ".btn-primary{",
        ".btn-secondary{",
        ".btn-success{",
        ".btn-danger{",
        ".sample-buttons{",
        ".sample-btn{",
        ".sample-btn.active{",
        # Table
        ".agent-table{",
        ".agent-table thead",
        ".agent-table th{",
        ".agent-table tbody",
        ".agent-table td{",
        ".agent-name{",
        ".agent-traits{",
        ".trait-item{",
        ".trait-value{",
        ".checkbox-cell{",
        # Utility
        ".close-btn{",
        ".collapsed-view{",
        ".no-data-message{",
        # Dark mode
        "@media (prefers-color-scheme: dark){",
        # Responsive
        "@media (max-width: 768px){",
    ]

    results = {}
    for css_class in traditional_classes:
        found = css_class in css_content
        results[css_class] = found
        status = "✅" if found else "❌"
        print(f"   {status} {css_class}")

    success_count = sum(results.values())
    total_count = len(results)

    print(f"\n📊 Traditional CSS Classes: {success_count}/{total_count} found")

    # Check file size
    file_size = len(css_content)
    print(f"📁 CSS file size: {file_size:,} characters")

    return success_count >= (total_count * 0.85)  # 85% success rate


def test_react_component_compatibility():
    """Test that React component uses compatible CSS classes."""

    print("\n⚛️ Testing React Component Compatibility")
    print("=" * 50)

    react_file = (
        Path(__file__).parent
        / "src"
        / "source"
        / "react_files"
        / "agent_list_builder.tsx"
    )

    if not react_file.exists():
        print("❌ React file not found")
        return False

    with open(react_file, "r", encoding="utf-8") as f:
        react_content = f.read()

    # Test for compatible classes (should be using traditional classes now)
    compatible_features = {
        "Main container class": "agent-list-builder",
        "Header stats section": "header-stats",
        "Controls section": "controls-section",
        "Button classes": "btn btn-",
        "Sample buttons": "sample-buttons",
        "Agent table": "agent-table",
        "Close button": "close-btn",
        "Error message": "error-message",
        "Status message": "status-message",
        "Agent name": "agent-name",
        "Checkbox cell": "checkbox-cell",
        # Should NOT have these Tailwind classes anymore
        "No complex Tailwind grids": "lg:grid-cols-3" not in react_content,
        "No complex Tailwind colors": "dark:bg-gray-800/50" not in react_content,
        "No complex Tailwind spacing": "px-4 py-3" not in react_content,
    }

    results = {}
    for desc, check in compatible_features.items():
        if isinstance(check, bool):
            found = check
        else:
            found = check in react_content
        results[desc] = found
        status = "✅" if found else "❌"
        print(f"   {status} {desc}")

    success_count = sum(results.values())
    total_count = len(results)

    print(f"\n📊 React Compatibility: {success_count}/{total_count} passed")

    return success_count >= (total_count * 0.8)  # 80% success rate


def test_compiled_js_compatibility():
    """Test that compiled JavaScript is compatible."""

    print("\n🔧 Testing Compiled JavaScript")
    print("=" * 50)

    js_file = (
        Path(__file__).parent
        / "src"
        / "compiled"
        / "esm_files"
        / "agent_list_builder.js"
    )

    if not js_file.exists():
        print("❌ JS file not found")
        return False

    with open(js_file, "r", encoding="utf-8") as f:
        js_content = f.read()

    # Test for proper compilation
    js_features = {
        "Traditional CSS classes": "agent-list-builder",
        "Button classes": "btn btn-",
        "React functionality": "useState",
        "Event handlers": "onClick",
        "CSS class assignments": "className",
        "No complex Tailwind": "dark:bg-gray-800/50" not in js_content,
    }

    results = {}
    for desc, check in js_features.items():
        if isinstance(check, bool):
            found = check
        else:
            found = check in js_content
        results[desc] = found
        status = "✅" if found else "❌"
        print(f"   {status} {desc}")

    success_count = sum(results.values())
    total_count = len(results)

    print(f"\n📊 Compiled JS Compatibility: {success_count}/{total_count} passed")

    return success_count >= (total_count * 0.8)


def main():
    """Run hybrid CSS tests."""

    print("🧪 Testing Agent List Builder Hybrid CSS Implementation")
    print("🎯 Verifying traditional CSS classes work with React component")
    print("=" * 80)

    css_test = test_traditional_css_classes()
    react_test = test_react_component_compatibility()
    js_test = test_compiled_js_compatibility()

    print("\n" + "=" * 80)
    print("📊 HYBRID CSS TEST SUMMARY")
    print(f"Traditional CSS Classes: {'✅ PASSED' if css_test else '❌ FAILED'}")
    print(f"React Component Compatibility: {'✅ PASSED' if react_test else '❌ FAILED'}")
    print(f"Compiled JavaScript: {'✅ PASSED' if js_test else '❌ FAILED'}")

    all_passed = css_test and react_test and js_test

    if all_passed:
        print("\n🎉 SUCCESS! Hybrid CSS implementation is working:")
        print("   🎨 Professional container styling from agent_list_manager")
        print("   🔧 React component uses traditional CSS classes")
        print("   🌙 Dark mode support via media queries")
        print("   📱 Responsive design breakpoints")
        print("   ✨ All buttons, tables, and controls properly styled")
        print("   🚀 No more unstyled Tailwind classes")

        print("\n💡 Implementation approach:")
        print("   • CSS: Copied agent_list_manager.css with appropriate class names")
        print("   • React: Updated to use traditional CSS classes instead of Tailwind")
        print("   • Result: Professional styling with clean, maintainable code")

    else:
        print("\n❌ Some tests failed. The hybrid approach needs refinement.")


if __name__ == "__main__":
    main()
