#!/usr/bin/env python3
"""
Quick debug script - run this with your Results object
"""

import sys
sys.path.append('/Users/johnhorton/tools/ep/edsl')

def debug_results(results):
    """Quick debug function for Results objects."""
    
    print("🔍 Quick Results Debug")
    print("=" * 30)
    
    # Basic checks
    print(f"1. Type: {type(results)}")
    print(f"2. Length: {len(results) if hasattr(results, '__len__') else 'No __len__'}")
    
    # Method checks
    methods_to_check = ['_summary', 'to_dict', 'to_dataset']
    print(f"\n3. Required Methods:")
    for method in methods_to_check:
        has_method = hasattr(results, method)
        print(f"   - {method}: {'✅' if has_method else '❌'}")
        
        if has_method:
            try:
                if method == '_summary':
                    result = getattr(results, method)()
                    print(f"     → {result}")
                elif method == 'to_dict':
                    # Try with full_dict=True (what base widget expects)
                    result = getattr(results, method)(full_dict=True)
                    print(f"     → Keys: {list(result.keys())[:5]}...")
                    if 'survey' in result:
                        print(f"     → Survey questions: {len(result.get('survey', {}).get('questions', []))}")
                    if 'data' in result:
                        print(f"     → Data entries: {len(result.get('data', []))}")
                elif method == 'to_dataset':
                    dataset = getattr(results, method)()
                    print(f"     → Dataset type: {type(dataset)}")
                    if hasattr(dataset, 'relevant_columns'):
                        cols = dataset.relevant_columns()
                        print(f"     → Columns: {len(cols)}")
            except Exception as e:
                print(f"     ❌ Error calling {method}: {e}")

    # Now test widget creation
    print(f"\n4. Testing Widget Creation:")
    try:
        from edsl.widgets.unified_results_inspector import UnifiedResultsInspectorWidget
        widget = UnifiedResultsInspectorWidget(obj=results)
        
        # Check if data was set by base class
        print(f"   - Widget created: ✅")
        print(f"   - Base data set: {'✅' if widget.data else '❌'}")
        print(f"   - Results data set: {'✅' if widget.results_data else '❌'}")
        
        # Try manual data processing
        if not widget.results_data and widget.data:
            print(f"   - Trying manual data processing...")
            try:
                widget._process_object_data()
                print(f"   - Manual processing: {'✅' if widget.results_data else '❌'}")
            except Exception as e:
                print(f"   - Manual processing error: {e}")
        
        return widget
        
    except Exception as e:
        print(f"   ❌ Widget creation failed: {e}")
        import traceback
        traceback.print_exc()
        return None

# Instructions for use
if __name__ == "__main__":
    print("💡 Usage:")
    print("   from quick_debug import debug_results")
    print("   debug_results(your_results_object)")