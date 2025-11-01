#!/usr/bin/env python3
"""
Demo script for the DataFrameGridChartsWidget

This shows how to use the new combined AG-Grid and AG-Charts widget.
Run this in a Jupyter notebook to see the interactive interface.
"""

import pandas as pd
import numpy as np
import sys
import os

# Add the widgets directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from dataframe_grid_charts_widget import DataFrameGridChartsWidget


def create_sales_data():
    """Create realistic sales data for demonstration."""
    np.random.seed(42)

    # Generate sample sales data
    dates = pd.date_range(start="2024-01-01", end="2024-12-31", freq="D")
    products = ["iPhone 15", "MacBook Pro", "iPad Air", "Apple Watch", "AirPods Pro"]
    regions = ["North America", "Europe", "Asia Pacific", "Latin America"]

    n_records = 500

    data = {
        "Date": np.random.choice(dates, n_records),
        "Product": np.random.choice(products, n_records),
        "Region": np.random.choice(regions, n_records),
        "Sales_Amount": np.random.uniform(1000, 100000, n_records).round(2),
        "Units_Sold": np.random.randint(1, 500, n_records),
        "Profit_Margin": np.random.uniform(0.15, 0.45, n_records).round(3),
        "Customer_Rating": np.random.uniform(3.5, 5.0, n_records).round(1),
        "Marketing_Spend": np.random.uniform(500, 15000, n_records).round(2),
        "Is_Online": np.random.choice([True, False], n_records, p=[0.6, 0.4]),
        "Sales_Rep": np.random.choice(
            ["Alice", "Bob", "Charlie", "Diana", "Eve"], n_records
        ),
        "Quarter": np.random.choice([1, 2, 3, 4], n_records),
    }

    df = pd.DataFrame(data)

    # Add calculated fields
    df["Revenue"] = df["Sales_Amount"] * df["Units_Sold"]
    df["Profit"] = df["Revenue"] * df["Profit_Margin"]

    return df.sort_values("Date").reset_index(drop=True)


def main():
    """Create and configure the demo widget."""
    print("🚀 DataFrameGridChartsWidget Demo")
    print("=" * 50)

    # Create sample data
    df = create_sales_data()
    print(f"📊 Created sales dataset: {df.shape[0]} rows × {df.shape[1]} columns")
    print("\nDataset preview:")
    print(df.head())

    # Create the widget
    print("\n🎯 Creating DataFrameGridChartsWidget...")
    widget = DataFrameGridChartsWidget(dataframe=df)

    # Configure for a nice default view
    widget.configure_chart(
        chart_type="bar",
        x_column="Region",
        y_column="Revenue",
        title="Revenue by Region",
    )

    widget.configure_grid(
        page_size=25, enable_selection=True, selection_mode="multiple"
    )

    print("✅ Widget configured with:")
    print(f"   • Layout: {widget.layout_mode} (default - clean tabbed interface)")
    print(
        f"   • Chart: {widget.chart_type} chart ({widget.chart_x_column} vs {widget.chart_y_column})"
    )
    print(f"   • Grid: {widget.page_size} rows per page, selection enabled")

    print("\n📈 Available columns for charting:")
    print(f"   • Numeric: {', '.join(widget.numeric_columns[:5])}...")
    print(f"   • Categorical: {', '.join(widget.categorical_columns)}")
    print(f"   • Datetime: {', '.join(widget.datetime_columns)}")

    print("\n💡 To use in Jupyter notebook:")
    print("   from dataframe_grid_charts_widget import DataFrameGridChartsWidget")
    print("   widget = DataFrameGridChartsWidget(dataframe=your_df)")
    print("   display(widget)")

    print("\n🎛️ Try different configurations:")
    print("   # Change chart type")
    print(
        "   widget.configure_chart(chart_type='line', x_column='Date', y_column='Revenue')"
    )
    print("   ")
    print("   # Change layout (default is now 'tabs')")
    print("   widget.set_layout_mode('split')  # or 'grid-only', 'charts-only')")
    print("   ")
    print("   # Access selected data")
    print("   selected_df = widget.get_selected_dataframe()")

    print("\n✨ New tabbed interface features:")
    print("   • Clean separation between Table and Charts views")
    print("   • Row count display in Table tab")
    print("   • Selected row count in Charts tab")
    print("   • Enhanced visual styling with hover effects")

    return widget


if __name__ == "__main__":
    widget = main()
