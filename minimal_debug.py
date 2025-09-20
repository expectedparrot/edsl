#!/usr/bin/env python3
"""
Minimal debug - let's see what's actually happening
"""

import sys
sys.path.append('/Users/johnhorton/tools/ep/edsl')

from edsl.widgets.unified_results_inspector import UnifiedResultsInspectorWidget

def minimal_test(results):
    print("=== MINIMAL DEBUG TEST ===")
    
    # Step 1: Basic object check
    print(f"1. Results object type: {type(results)}")
    print(f"2. Results object length: {len(results)}")
    
    # Step 2: Create widget and check immediate state
    print(f"\n3. Creating widget...")
    widget = UnifiedResultsInspectorWidget(obj=results)
    
    print(f"4. Widget created successfully: {widget is not None}")
    print(f"5. Widget object set: {widget.object is not None}")
    print(f"6. Widget object is same: {widget.object is results}")
    
    # Step 3: Check traitlets immediately after creation
    print(f"\n7. Traitlet states:")
    print(f"   - results_data: {type(widget.results_data)} with {len(widget.results_data)} items")
    print(f"   - paginated_results: {type(widget.paginated_results)} with {len(widget.paginated_results)} items")
    print(f"   - analysis_data: {type(widget.analysis_data)} with {len(widget.analysis_data)} items")
    
    # Step 4: Check data attribute from base class
    print(f"\n8. Base class data:")
    print(f"   - widget.data: {type(widget.data)} with {len(widget.data)} items")
    if widget.data:
        print(f"   - data keys: {list(widget.data.keys())}")
    
    # Step 5: Manual method calls
    print(f"\n9. Manual method testing:")
    
    # Test base class to_dict
    if hasattr(results, 'to_dict'):
        try:
            result_dict = results.to_dict(full_dict=True)
            print(f"   - to_dict(full_dict=True): SUCCESS - {len(result_dict)} keys")
            print(f"   - Keys: {list(result_dict.keys())}")
        except Exception as e:
            print(f"   - to_dict(full_dict=True): FAILED - {e}")
    
    # Test _summary
    if hasattr(results, '_summary'):
        try:
            summary = results._summary()
            print(f"   - _summary(): SUCCESS - {summary}")
        except Exception as e:
            print(f"   - _summary(): FAILED - {e}")
    
    # Step 6: Force manual processing
    print(f"\n10. Force manual processing...")
    try:
        # Manually set data if needed
        if not widget.data and hasattr(results, 'to_dict'):
            widget.data = results.to_dict(full_dict=True)
            print(f"    - Manually set widget.data")
        
        # Call processing manually
        result = widget._process_object_data()
        print(f"    - Manual _process_object_data(): {result is not None}")
        
        # Check traitlets after manual processing
        print(f"    - results_data after processing: {len(widget.results_data)} items")
        print(f"    - paginated_results after processing: {len(widget.paginated_results)} items")
        
    except Exception as e:
        print(f"    - Manual processing FAILED: {e}")
        import traceback
        traceback.print_exc()
    
    return widget

# Test function
if __name__ == "__main__":
    print("💡 Run: minimal_test(your_results_object)")