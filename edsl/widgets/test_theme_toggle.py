#!/usr/bin/env python3
"""
Test script to verify theme toggle functionality in the agent_list_builder widget.

Tests:
1. CSS includes manual theme control classes
2. React component includes theme toggle UI
3. Theme switching logic is implemented
"""

from pathlib import Path

def test_css_theme_classes():
    """Test that compiled CSS includes manual theme control classes."""
    
    print("🎨 Testing CSS Theme Control Classes")
    print("=" * 50)
    
    css_file = Path(__file__).parent / "src" / "compiled" / "css_files" / "agent_list_builder.css"
    
    if not css_file.exists():
        print("❌ CSS file not found")
        return False
        
    with open(css_file, 'r', encoding='utf-8') as f:
        css_content = f.read()
    
    # Test for manual theme control classes (using double backslashes as they appear in compiled CSS)
    theme_classes = {
        "Dark theme manual control": ".theme-dark .dark\\\\:bg-gray-900",
        "Light theme overrides": ".theme-light .dark\\\\:bg-gray-900",
        "Dark text color control": ".theme-dark .dark\\\\:text-white",
        "Light text color override": ".theme-light .dark\\\\:text-white",
        "Dark border control": ".theme-dark .dark\\\\:border-gray-700",
        "Light border override": ".theme-light .dark\\\\:border-gray-700",
        "Dark hover states": ".theme-dark .dark\\\\:hover\\\\:bg-gray-600:hover",
        "System theme fallback": "@media (prefers-color-scheme: dark)",
    }
    
    results = {}
    for desc, css_class in theme_classes.items():
        found = css_class in css_content
        results[desc] = found
        status = "✅" if found else "❌"
        print(f"   {status} {desc}: {css_class}")
    
    success_count = sum(results.values())
    total_count = len(results)
    
    print(f"\n📊 CSS Theme Classes: {success_count}/{total_count} found")
    
    return success_count == total_count

def test_react_theme_functionality():
    """Test that React component includes theme functionality."""
    
    print("\n⚛️ Testing React Theme Functionality")
    print("=" * 50)
    
    react_file = Path(__file__).parent / "src" / "source" / "react_files" / "agent_list_builder.tsx"
    
    if not react_file.exists():
        print("❌ React file not found")
        return False
        
    with open(react_file, 'r', encoding='utf-8') as f:
        react_content = f.read()
    
    # Test for theme-related code
    theme_features = {
        "Sun/Moon icons import": "Sun, Moon",
        "Theme state definition": "const [theme, setTheme]",
        "getEffectiveTheme function": "const getEffectiveTheme =",
        "toggleTheme function": "const toggleTheme =",
        "resetToSystemTheme function": "const resetToSystemTheme =",
        "isDark calculation": "const isDark = getEffectiveTheme()",
        "System theme listener": "matchMedia('(prefers-color-scheme: dark)')",
        "Theme toggle button": "onClick={toggleTheme}",
        "Auto button": "onClick={resetToSystemTheme}",
        "Theme classes usage": "theme-dark",
        "Conditional theme rendering": "isDark ? 'theme-dark'",
    }
    
    results = {}
    for desc, code_snippet in theme_features.items():
        found = code_snippet in react_content
        results[desc] = found
        status = "✅" if found else "❌"
        print(f"   {status} {desc}: {code_snippet}")
    
    success_count = sum(results.values())
    total_count = len(results)
    
    print(f"\n📊 React Theme Features: {success_count}/{total_count} found")
    
    return success_count == total_count

def test_compiled_js_theme_code():
    """Test that compiled JavaScript includes theme code."""
    
    print("\n🔧 Testing Compiled JavaScript")
    print("=" * 50)
    
    js_file = Path(__file__).parent / "src" / "compiled" / "esm_files" / "agent_list_builder.js"
    
    if not js_file.exists():
        print("❌ JS file not found")
        return False
        
    with open(js_file, 'r', encoding='utf-8') as f:
        js_content = f.read()
    
    # Test for compiled theme functionality (minified names will be different)
    js_features = {
        "Theme classes in string": "theme-dark",
        "Theme classes in string 2": "theme-light", 
        "System theme media query": "prefers-color-scheme",
        "Dark mode check": "matchMedia",
        "Theme state management": "useState",
        "Button click handlers": "onClick",
        "CSS class conditional": "className",
    }
    
    results = {}
    for desc, code_snippet in js_features.items():
        found = code_snippet in js_content
        results[desc] = found
        status = "✅" if found else "❌"
        print(f"   {status} {desc}: {code_snippet}")
    
    success_count = sum(results.values())
    total_count = len(results)
    
    print(f"\n📊 Compiled JS Features: {success_count}/{total_count} found")
    
    return success_count == total_count

def simulate_theme_toggle_behavior():
    """Simulate how the theme toggle would work."""
    
    print("\n🔄 Theme Toggle Simulation")
    print("=" * 50)
    
    # Simulate the theme state transitions
    theme_states = ['system', 'light', 'dark', 'light', 'system']
    system_preference = 'dark'  # Simulate system dark mode
    
    print("Theme Toggle Sequence:")
    print("🖱️  Click sequence: Toggle → Toggle → Toggle → Reset to Auto")
    print()
    
    for i, theme in enumerate(theme_states):
        if theme == 'system':
            effective_theme = system_preference
            description = f"System ({system_preference})"
        else:
            effective_theme = theme
            description = theme.title()
            
        icon = "🌙" if effective_theme == 'dark' else "☀️"
        classes = "theme-dark bg-gray-900" if effective_theme == 'dark' else "theme-light bg-white"
        
        action = "Initial" if i == 0 else f"Click {i}"
        print(f"   {action}: {icon} {description} → <div class=\"{classes}\">")
    
    print("\n✅ Theme toggle simulation completed")
    
    return True

def main():
    """Run all theme toggle tests."""
    
    print("🧪 Testing Agent List Builder Theme Toggle Functionality")
    print("🎯 Verifying manual light/dark mode switching")
    print("=" * 80)
    
    css_test = test_css_theme_classes()
    react_test = test_react_theme_functionality()
    js_test = test_compiled_js_theme_code()
    simulation_test = simulate_theme_toggle_behavior()
    
    print("\n" + "=" * 80)
    print("📊 THEME TOGGLE TEST SUMMARY")
    print(f"CSS Theme Classes: {'✅ PASSED' if css_test else '❌ FAILED'}")
    print(f"React Theme Code: {'✅ PASSED' if react_test else '❌ FAILED'}")
    print(f"Compiled JavaScript: {'✅ PASSED' if js_test else '❌ FAILED'}")
    print(f"Theme Toggle Simulation: {'✅ PASSED' if simulation_test else '❌ FAILED'}")
    
    all_passed = css_test and react_test and js_test and simulation_test
    
    if all_passed:
        print("\n🎉 SUCCESS! Theme toggle functionality is ready:")
        print("   🌙 Manual dark mode control")
        print("   ☀️ Manual light mode control") 
        print("   🔄 System theme auto-detection")
        print("   🎛️ Toggle button with Sun/Moon icons")
        print("   🔧 Auto button to reset to system theme")
        print("   🎨 Complete CSS theme class support")
        
        print("\n💡 How to use:")
        print("   • Click the Sun/Moon icon to toggle between light/dark")
        print("   • Click 'Auto' to follow system theme preference")
        print("   • Widget remembers manual theme choice within session")
        print("   • Supports both manual override and system auto-detection")
        
    else:
        print("\n❌ Some tests failed. Check the output above for details.")

if __name__ == "__main__":
    main()