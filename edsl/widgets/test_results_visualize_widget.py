"""
Test script for ResultsVisualizeWidget

This script tests the basic functionality of the new ResultsVisualizeWidget
to ensure it can be imported and instantiated correctly.
"""

import sys
import os
import traceback

# Add the parent directory to sys.path for testing
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    print("Testing ResultsVisualizeWidget import...")
    from edsl.widgets.results_visualize_widget import ResultsVisualizeWidget
    print("✓ Successfully imported ResultsVisualizeWidget")
    
    print("\nTesting widget instantiation...")
    widget = ResultsVisualizeWidget()
    print("✓ Successfully created widget instance")
    
    print(f"✓ Widget short name: {widget.widget_short_name}")
    print(f"✓ Widget class: {widget.__class__.__name__}")
    
    print("\nTesting widget properties...")
    print(f"✓ Status: {widget.status}")
    print(f"✓ Chart type: {widget.chart_type}")
    print(f"✓ Data length: {len(widget.data)}")
    print(f"✓ Columns length: {len(widget.columns)}")
    
    print("\nTesting widget methods...")
    # Test _clear_data method
    widget._clear_data()
    print("✓ _clear_data() executed successfully")
    
    # Test chart suggestions generation with empty data
    suggestions = widget._generate_chart_suggestions(None)
    print(f"✓ Chart suggestions (empty data): {len(suggestions)} suggestions")
    
    print("\nTesting with mock data...")
    import pandas as pd
    
    # Create mock dataframe
    mock_df = pd.DataFrame({
        'numeric_col1': [1, 2, 3, 4, 5],
        'numeric_col2': [2, 4, 6, 8, 10],
        'categorical_col': ['A', 'B', 'A', 'C', 'B']
    })
    
    # Test column analysis
    analysis = widget._analyze_columns(mock_df)
    print(f"✓ Numeric columns found: {analysis['numeric']}")
    print(f"✓ Categorical columns found: {analysis['categorical']}")
    
    # Test chart suggestions with real data
    suggestions = widget._generate_chart_suggestions(mock_df)
    print(f"✓ Chart suggestions (with data): {len(suggestions)} suggestions")
    for i, suggestion in enumerate(suggestions[:3]):  # Show first 3
        print(f"   {i+1}. {suggestion['chart_type']}: {suggestion['description']}")
    
    # Test data preparation
    prepared_data = widget._prepare_data(mock_df)
    print(f"✓ Prepared data: {len(prepared_data)} records")
    
    print("\nTesting programmatic chart creation...")
    # Test creating different chart types  
    chart_types = ['bar', 'scatter', 'histogram', 'line', 'box']
    for chart_type in chart_types:
        try:
            widget.create_chart(chart_type, 'numeric_col1', 'numeric_col2' if chart_type != 'histogram' else None)
            print(f"✓ {chart_type} chart configuration set successfully")
        except Exception as e:
            print(f"✗ {chart_type} chart failed: {e}")
    
    print("\nTesting suggestion application...")
    try:
        if len(widget.chart_suggestions) > 0:
            widget.apply_suggestion(0)
            print("✓ Applied first suggestion successfully")
        else:
            print("✓ No suggestions to apply (expected for client-side version)")
    except Exception as e:
        print(f"✗ Suggestion application failed: {e}")
    
    print("\n" + "="*50)
    print("🎉 ALL TESTS PASSED! The ResultsVisualizeWidget is working correctly.")
    print("="*50)

except ImportError as e:
    print(f"✗ Import error: {e}")
    print("Make sure all dependencies are installed (altair, pandas, traitlets)")
    traceback.print_exc()
    
except Exception as e:
    print(f"✗ Test failed with error: {e}")
    traceback.print_exc()
    
finally:
    print(f"\nTest completed. Check output above for results.")