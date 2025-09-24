#!/usr/bin/env python3
"""
Even simpler test - bypass all our custom logic and just test basic functionality
"""

import sys
sys.path.append('/Users/johnhorton/tools/ep/edsl')

def basic_widget_test(results):
    """Test the basic widget functionality step by step."""
    
    print("🧪 BASIC WIDGET TEST")
    print("=" * 30)
    
    # Test 1: Original results inspector (that works)
    print("1. Testing original ResultsInspectorWidget...")
    try:
        from edsl.widgets.results_inspector import ResultsInspectorWidget
        original_widget = ResultsInspectorWidget(obj=results)
        print(f"   ✅ Original widget created")
        print(f"   - results_data: {bool(original_widget.results_data)}")
        print(f"   - paginated_results: {bool(original_widget.paginated_results)}")
        if original_widget.results_data:
            print(f"   - data items: {len(original_widget.results_data.get('data', []))}")
    except Exception as e:
        print(f"   ❌ Original widget failed: {e}")
        return None
    
    # Test 2: Our unified widget
    print(f"\n2. Testing unified widget...")
    try:
        from edsl.widgets.unified_results_inspector import UnifiedResultsInspectorWidget
        unified_widget = UnifiedResultsInspectorWidget(obj=results)
        print(f"   ✅ Unified widget created")
        print(f"   - results_data: {bool(unified_widget.results_data)}")
        print(f"   - paginated_results: {bool(unified_widget.paginated_results)}")
    except Exception as e:
        print(f"   ❌ Unified widget failed: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    # Test 3: Compare the two
    print(f"\n3. Comparison:")
    print(f"   Original data items: {len(original_widget.results_data.get('data', []))}")
    print(f"   Unified data items: {len(unified_widget.results_data.get('data', []))}")
    
    # Test 4: Try to figure out what's different
    print(f"\n4. Detailed unified widget state:")
    print(f"   - Object: {type(unified_widget.object)}")
    print(f"   - Base data: {bool(unified_widget.data)}")
    print(f"   - Results data keys: {list(unified_widget.results_data.keys()) if unified_widget.results_data else 'empty'}")
    
    return original_widget, unified_widget

if __name__ == "__main__":
    print("💡 Run: basic_widget_test(your_results_object)")