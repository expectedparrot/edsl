#!/usr/bin/env python3
"""
Demo: How to Create Charts with AG-Grid Enterprise

This script shows exactly how to create charts in the Enterprise widget.
"""

import pandas as pd
import numpy as np
import sys
import os

# Add the widgets directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from dataframe_grid_charts_enterprise_widget import DataFrameGridChartsEnterpriseWidget

def create_simple_chart_demo_data():
    """Create simple data perfect for chart creation demo."""
    np.random.seed(42)
    
    # Simple, clear data for charting
    categories = ['Electronics', 'Clothing', 'Books', 'Home & Garden']
    regions = ['North America', 'Europe', 'Asia Pacific']
    
    data = []
    for category in categories:
        for region in regions:
            # Create clear, chartable data
            sales = np.random.uniform(10000, 100000)
            units = np.random.randint(100, 1000)
            data.append({
                'Category': category,
                'Region': region,
                'Sales': round(sales, 2),
                'Units': units,
                'Avg_Price': round(sales / units, 2),
                'Quarter': np.random.choice(['Q1', 'Q2', 'Q3', 'Q4'])
            })
    
    return pd.DataFrame(data)

def main():
    """Demonstrate chart creation with Enterprise widget."""
    print("📊 AG-Grid Enterprise - Chart Creation Guide")
    print("=" * 60)
    
    # Create simple demo data
    df = create_simple_chart_demo_data()
    print(f"📋 Created demo data: {len(df)} rows × {len(df.columns)} columns")
    print("\nData preview:")
    print(df.head())
    
    # Create Enterprise widget
    widget = DataFrameGridChartsEnterpriseWidget(dataframe=df)
    
    print(f"\n🚀 Enterprise widget created with chart functionality:")
    print(f"   • Charts enabled: {widget.enable_charts}")
    print(f"   • Tool panel enabled: {widget.show_tool_panel}")
    print(f"   • Range selection enabled: {widget.enable_range_selection}")
    
    print(f"\n📊 HOW TO CREATE CHARTS:")
    print(f"=" * 40)
    
    print(f"\n🎯 METHOD 1 - Quick Range Charts:")
    print(f"   1. Select data range (click & drag cells)")
    print(f"   2. Right-click selected area")
    print(f"   3. Choose 'Chart Range' from context menu")
    print(f"   4. Pick chart type (Column, Line, Pie, etc.)")
    
    print(f"\n🎯 METHOD 2 - Tool Panel Charts:")
    print(f"   1. Use tool panel on right side")
    print(f"   2. Drag 'Category' to 'Row Groups'")
    print(f"   3. Drag 'Sales' to 'Values'")
    print(f"   4. Right-click grouped data → 'Chart Range'")
    
    print(f"\n🎯 METHOD 3 - Pivot Charts:")
    print(f"   1. Toggle 'Pivot Mode' in tool panel")
    print(f"   2. Drag 'Region' to 'Column Labels'") 
    print(f"   3. Drag 'Category' to 'Row Groups'")
    print(f"   4. Drag 'Sales' to 'Values'")
    print(f"   5. Right-click pivot table → 'Chart Range'")
    
    print(f"\n📈 BEST DATA FOR CHARTS:")
    print(f"   • Categories: {', '.join(df['Category'].unique())}")
    print(f"   • Numeric values: Sales (${df['Sales'].sum():,.0f} total)")
    print(f"   • Grouping: By Region ({len(df['Region'].unique())} regions)")
    
    print(f"\n💡 CHART CREATION TIPS:")
    print(f"   ✓ Select at least one category + one numeric column")
    print(f"   ✓ Use right-click context menu after selection")
    print(f"   ✓ Try different chart types (Column, Bar, Line, Pie)")
    print(f"   ✓ Charts update automatically with filters/grouping")
    
    print(f"\n🔧 TO USE IN JUPYTER:")
    print(f"   widget = DataFrameGridChartsEnterpriseWidget(dataframe=your_df)")
    print(f"   display(widget)")
    print(f"   # Then use right-click → 'Chart Range' on selected data")
    
    return widget

if __name__ == "__main__":
    widget = main()