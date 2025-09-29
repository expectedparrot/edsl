#!/usr/bin/env python3
"""
Test: Chart Range Context Menu with Enterprise Widget

This script demonstrates the correct Enterprise widget usage with Chart Range context menu.
"""

import pandas as pd
import numpy as np
import sys
import os

# Add the widgets directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from dataframe_grid_charts_enterprise_widget import DataFrameGridChartsEnterpriseWidget

def create_simple_test_data():
    """Create simple data perfect for testing Chart Range."""
    np.random.seed(42)
    
    data = {
        'Category': ['Electronics', 'Clothing', 'Books', 'Home'] * 3,
        'Region': ['North', 'South', 'East'] * 4,
        'Sales': np.random.uniform(1000, 10000, 12),
        'Units': np.random.randint(10, 100, 12),
        'Profit': np.random.uniform(100, 1000, 12)
    }
    
    return pd.DataFrame(data)

def main():
    """Test Enterprise widget with Chart Range context menu."""
    print("🔧 Testing AG-Grid Enterprise Chart Range Context Menu")
    print("=" * 60)
    
    # Create test data
    df = create_simple_test_data()
    print(f"📋 Created test data: {len(df)} rows × {len(df.columns)} columns")
    print("\nData preview:")
    print(df.head())
    
    # Create Enterprise widget - THIS IS THE CORRECT ONE TO USE
    widget = DataFrameGridChartsEnterpriseWidget(dataframe=df)
    
    print("\n✅ CORRECT Enterprise Widget Created:")
    print("   Class: DataFrameGridChartsEnterpriseWidget")
    print(f"   Widget name: {widget.widget_short_name}")
    print(f"   Charts enabled: {widget.enable_charts}")
    print(f"   Range selection: {widget.enable_range_selection}")
    print(f"   Tool panel: {widget.show_tool_panel}")
    
    print("\n🎯 HOW TO USE CHART RANGE:")
    print("   1. Select cells with numeric data (drag across Sales or Profit columns)")
    print("   2. Right-click (or Ctrl+click on Mac)")
    print("   3. Look for 'Chart Range' in context menu")
    print("   4. Choose chart type (Column, Bar, Line, Pie)")
    
    print("\n📊 Column Analysis:")
    print(f"   • Numeric columns: {widget.numeric_columns}")
    print(f"   • Categorical columns: {widget.categorical_columns}")
    
    print("\n🚀 Usage in Jupyter:")
    print("   from dataframe_grid_charts_enterprise_widget import DataFrameGridChartsEnterpriseWidget")
    print("   widget = DataFrameGridChartsEnterpriseWidget(dataframe=your_df)")
    print("   display(widget)")
    print("   # Now try selecting data and right-clicking!")
    
    print("\n💡 Debugging Tips:")
    print("   • Open browser console (F12) to see debug logs")
    print("   • Check that columns are recognized as 'chartable series'")
    print("   • Verify 'Charts enabled: true' in console")
    print("   • Make sure you select numeric data ranges")
    
    return widget

if __name__ == "__main__":
    widget = main()