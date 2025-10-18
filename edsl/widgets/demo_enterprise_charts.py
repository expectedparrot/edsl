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
    categories = ["Electronics", "Clothing", "Books", "Home & Garden"]
    regions = ["North America", "Europe", "Asia Pacific"]

    data = []
    for category in categories:
        for region in regions:
            # Create clear, chartable data
            sales = np.random.uniform(10000, 100000)
            units = np.random.randint(100, 1000)
            data.append(
                {
                    "Category": category,
                    "Region": region,
                    "Sales": round(sales, 2),
                    "Units": units,
                    "Avg_Price": round(sales / units, 2),
                    "Quarter": np.random.choice(["Q1", "Q2", "Q3", "Q4"]),
                }
            )

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

    print("\n🚀 Enterprise widget created with chart functionality:")
    print(f"   • Charts enabled: {widget.enable_charts}")
    print(f"   • Tool panel enabled: {widget.show_tool_panel}")
    print(f"   • Range selection enabled: {widget.enable_range_selection}")

    print("\n📊 HOW TO CREATE CHARTS:")
    print("=" * 40)

    print("\n🎯 METHOD 1 - Quick Range Charts:")
    print("   1. Select data range (click & drag cells)")
    print("   2. Right-click selected area")
    print("   3. Choose 'Chart Range' from context menu")
    print("   4. Pick chart type (Column, Line, Pie, etc.)")

    print("\n🎯 METHOD 2 - Tool Panel Charts:")
    print("   1. Use tool panel on right side")
    print("   2. Drag 'Category' to 'Row Groups'")
    print("   3. Drag 'Sales' to 'Values'")
    print("   4. Right-click grouped data → 'Chart Range'")

    print("\n🎯 METHOD 3 - Pivot Charts:")
    print("   1. Toggle 'Pivot Mode' in tool panel")
    print("   2. Drag 'Region' to 'Column Labels'")
    print("   3. Drag 'Category' to 'Row Groups'")
    print("   4. Drag 'Sales' to 'Values'")
    print("   5. Right-click pivot table → 'Chart Range'")

    print("\n📈 BEST DATA FOR CHARTS:")
    print(f"   • Categories: {', '.join(df['Category'].unique())}")
    print(f"   • Numeric values: Sales (${df['Sales'].sum():,.0f} total)")
    print(f"   • Grouping: By Region ({len(df['Region'].unique())} regions)")

    print("\n💡 CHART CREATION TIPS:")
    print("   ✓ Select at least one category + one numeric column")
    print("   ✓ Use right-click context menu after selection")
    print("   ✓ Try different chart types (Column, Bar, Line, Pie)")
    print("   ✓ Charts update automatically with filters/grouping")

    print("\n🔧 TO USE IN JUPYTER:")
    print("   widget = DataFrameGridChartsEnterpriseWidget(dataframe=your_df)")
    print("   display(widget)")
    print("   # Then use right-click → 'Chart Range' on selected data")

    return widget


if __name__ == "__main__":
    widget = main()
