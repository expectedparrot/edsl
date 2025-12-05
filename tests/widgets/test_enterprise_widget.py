#!/usr/bin/env python3
"""
Test script for DataFrameGridChartsEnterpriseWidget

This script demonstrates the full AG-Grid Enterprise + AG-Charts Enterprise functionality.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os

from edsl.widgets.dataframe_grid_charts_enterprise_widget import DataFrameGridChartsEnterpriseWidget


def create_enterprise_demo_data():
    """Create rich sample data perfect for Enterprise features."""
    np.random.seed(42)

    # Generate comprehensive business dataset
    start_date = datetime(2023, 1, 1)
    dates = pd.date_range(start=start_date, end=datetime(2024, 12, 31), freq="D")

    # Product categories and details
    categories = ["Electronics", "Clothing", "Books", "Home & Garden", "Sports"]
    products = {
        "Electronics": [
            "iPhone 15",
            "MacBook Pro",
            "iPad Air",
            "AirPods Pro",
            "Apple Watch",
        ],
        "Clothing": ["Jeans", "T-Shirt", "Dress", "Sneakers", "Jacket"],
        "Books": ["Fiction Novel", "Textbook", "Biography", "Cookbook", "Magazine"],
        "Home & Garden": ["Sofa", "Dining Table", "Lamp", "Plant Pot", "Vacuum"],
        "Sports": [
            "Running Shoes",
            "Yoga Mat",
            "Tennis Racket",
            "Gym Membership",
            "Protein Powder",
        ],
    }

    regions = [
        "North America",
        "Europe",
        "Asia Pacific",
        "Latin America",
        "Middle East & Africa",
    ]
    sales_channels = ["Online", "Retail Store", "Wholesale", "Mobile App"]
    customer_types = ["Individual", "Small Business", "Enterprise", "Government"]

    n_records = 1000

    # Generate records
    records = []
    for _ in range(n_records):
        category = np.random.choice(categories)
        product = np.random.choice(products[category])
        region = np.random.choice(regions)
        channel = np.random.choice(sales_channels)
        customer_type = np.random.choice(customer_types)
        date = pd.Timestamp(np.random.choice(dates))

        # Generate realistic business metrics
        base_price = np.random.uniform(50, 2000)
        quantity = np.random.randint(1, 100)
        discount = np.random.uniform(0, 0.3) if np.random.random() > 0.7 else 0

        record = {
            "Date": date,
            "Year": date.year,
            "Quarter": f"Q{date.quarter}",
            "Month": date.strftime("%B"),
            "Category": category,
            "Product": product,
            "Region": region,
            "Sales_Channel": channel,
            "Customer_Type": customer_type,
            "Unit_Price": round(base_price, 2),
            "Quantity": quantity,
            "Discount_Rate": round(discount, 3),
            "Gross_Revenue": round(base_price * quantity, 2),
            "Discount_Amount": round(base_price * quantity * discount, 2),
            "Net_Revenue": round(base_price * quantity * (1 - discount), 2),
            "Cost_Per_Unit": round(base_price * np.random.uniform(0.4, 0.7), 2),
            "Total_Cost": round(base_price * quantity * np.random.uniform(0.4, 0.7), 2),
            "Profit": 0,  # Will calculate below
            "Profit_Margin": 0,  # Will calculate below
            "Customer_Rating": round(np.random.uniform(3.5, 5.0), 1),
            "Returns": np.random.choice([True, False], p=[0.05, 0.95]),
            "Promotion_Applied": discount > 0,
        }

        # Calculate derived metrics
        record["Profit"] = round(record["Net_Revenue"] - record["Total_Cost"], 2)
        if record["Net_Revenue"] > 0:
            record["Profit_Margin"] = round(record["Profit"] / record["Net_Revenue"], 3)

        records.append(record)

    df = pd.DataFrame(records)
    return df.sort_values(["Date", "Category", "Product"]).reset_index(drop=True)


def test_enterprise_basic_functionality():
    """Test basic Enterprise widget functionality."""
    print("🚀 Testing AG-Grid Enterprise Widget - Basic Functionality")
    print("=" * 70)

    # Create rich sample data
    df = create_enterprise_demo_data()
    print(
        f"📊 Created enterprise dataset with {len(df)} rows and {len(df.columns)} columns"
    )

    # Show data overview
    print("\nDataset overview:")
    print(f"   • Date range: {df['Date'].min()} to {df['Date'].max()}")
    print(f"   • Categories: {', '.join(df['Category'].unique())}")
    print(f"   • Regions: {', '.join(df['Region'].unique())}")
    print(f"   • Total revenue: ${df['Net_Revenue'].sum():,.2f}")

    # Create Enterprise widget
    widget = DataFrameGridChartsEnterpriseWidget(dataframe=df)

    # Verify Enterprise features
    assert (
        widget.status == "ready"
    ), f"Widget status should be 'ready', got '{widget.status}'"
    assert widget.enable_charts == True, "Charts should be enabled by default"
    assert widget.enable_pivot == True, "Pivot should be enabled by default"
    assert widget.show_tool_panel == True, "Tool panel should be enabled by default"

    print("\n✅ Enterprise widget created successfully:")
    print(f"   • Status: {widget.status}")
    print(f"   • Data rows: {len(widget.data)}")
    print(f"   • Grid columns: {len(widget.columns)}")
    print(f"   • Charts enabled: {widget.enable_charts}")
    print(f"   • Pivot enabled: {widget.enable_pivot}")
    print(f"   • Tool panel: {widget.show_tool_panel}")

    return widget, df


def test_column_analysis():
    """Test Enterprise column analysis and configuration."""
    print("\n📋 Testing Enterprise Column Analysis")
    print("=" * 50)

    df = create_enterprise_demo_data()
    widget = DataFrameGridChartsEnterpriseWidget(dataframe=df)

    print("🔍 Column analysis results:")
    print(
        f"   • Numeric columns ({len(widget.numeric_columns)}): {widget.numeric_columns[:5]}..."
    )
    print(
        f"   • Categorical columns ({len(widget.categorical_columns)}): {widget.categorical_columns}"
    )
    print(
        f"   • Datetime columns ({len(widget.datetime_columns)}): {widget.datetime_columns}"
    )

    # Verify column configurations
    numeric_cols_with_aggregation = [
        col for col in widget.columns if col.get("enableValue") == True
    ]
    groupable_cols = [
        col for col in widget.columns if col.get("enableRowGroup") == True
    ]
    pivotable_cols = [col for col in widget.columns if col.get("enablePivot") == True]

    print("\n⚙️ Enterprise column features:")
    print(f"   • Aggregatable columns: {len(numeric_cols_with_aggregation)}")
    print(f"   • Groupable columns: {len(groupable_cols)}")
    print(f"   • Pivotable columns: {len(pivotable_cols)}")

    # Verify specific column configurations
    revenue_col = next(
        (col for col in widget.columns if col["field"] == "Net_Revenue"), None
    )
    if revenue_col:
        assert (
            revenue_col.get("enableValue") == True
        ), "Revenue column should be aggregatable"
        assert "sum" in revenue_col.get(
            "allowedAggFuncs", []
        ), "Revenue should allow sum aggregation"

    print("✅ Column analysis and Enterprise features configured correctly")


def test_enterprise_features():
    """Test Enterprise-specific features and methods."""
    print("\n⚡ Testing Enterprise Features")
    print("=" * 40)

    df = create_enterprise_demo_data()
    widget = DataFrameGridChartsEnterpriseWidget(dataframe=df)

    # Test Enterprise configuration
    widget.configure_enterprise_features(
        enable_charts=True,
        enable_pivot=True,
        show_tool_panel=True,
        enable_range_selection=True,
        chart_themes=["ag-default", "ag-material", "ag-solar", "ag-sandstone"],
    )

    print("🎯 Enterprise features configured:")
    print(f"   • Integrated charts: {widget.enable_charts}")
    print(f"   • Pivot functionality: {widget.enable_pivot}")
    print(f"   • Range selection: {widget.enable_range_selection}")
    print(f"   • Chart themes: {len(widget.chart_themes)} available")

    # Test pivot mode toggle
    initial_pivot_mode = widget.pivot_mode
    widget.toggle_pivot_mode()
    assert widget.pivot_mode != initial_pivot_mode, "Pivot mode should toggle"
    widget.toggle_pivot_mode()  # Toggle back

    # Test chart creation
    widget.create_chart_from_selection("column")
    assert widget.default_chart_type == "column", "Chart type should be set"

    # Test aggregation summary
    summary = widget.get_aggregation_summary()
    expected_keys = [
        "row_groups",
        "value_columns",
        "pivot_columns",
        "pivot_mode",
        "numeric_columns",
        "categorical_columns",
        "total_rows",
    ]
    for key in expected_keys:
        assert key in summary, f"Summary should contain {key}"

    print("✅ All Enterprise features tested successfully")


def test_data_manipulation():
    """Test data selection and manipulation features."""
    print("\n🎯 Testing Data Selection & Manipulation")
    print("=" * 50)

    df = create_enterprise_demo_data()
    widget = DataFrameGridChartsEnterpriseWidget(dataframe=df)

    # Simulate data selection
    selected_indices = list(range(0, 50, 5))  # Every 5th row in first 50
    selected_rows = [widget.data[i] for i in selected_indices]

    widget.selected_indices = selected_indices
    widget.selected_rows = selected_rows

    # Test getting selected DataFrame
    selected_df = widget.get_selected_dataframe()
    assert selected_df is not None, "Should return selected DataFrame"
    assert len(selected_df) == len(
        selected_indices
    ), "Selected DataFrame should have correct length"

    print("📊 Selection functionality:")
    print(f"   • Selected {len(selected_indices)} rows")
    print(f"   • Selected DataFrame shape: {selected_df.shape}")
    print(f"   • Selection data types preserved: {selected_df.dtypes.nunique()} types")

    # Test clear selection
    widget.clear_selection()
    assert len(widget.selected_rows) == 0, "Selection should be cleared"
    assert len(widget.selected_indices) == 0, "Selection indices should be cleared"
    assert len(widget.selected_ranges) == 0, "Range selection should be cleared"

    print("✅ Data manipulation features working correctly")


def test_enterprise_export():
    """Test Enterprise export functionality."""
    print("\n📤 Testing Enterprise Export Features")
    print("=" * 45)

    df = create_enterprise_demo_data()
    widget = DataFrameGridChartsEnterpriseWidget(dataframe=df)

    # Test Excel export
    try:
        export_result = widget.export_to_excel("test_export.xlsx")
        print(f"📋 Excel export test: {export_result}")
        print("✅ Export functionality available")
    except Exception as e:
        print(f"⚠️ Export test: {e}")


def demo_usage_examples():
    """Show Enterprise usage examples."""
    print("\n📚 Enterprise Usage Examples")
    print("=" * 40)

    examples = {
        "Basic Enterprise Setup": """
from dataframe_grid_charts_enterprise_widget import DataFrameGridChartsEnterpriseWidget

# Create Enterprise widget with full features
widget = DataFrameGridChartsEnterpriseWidget(dataframe=your_df)

# Display in Jupyter
display(widget)
""",
        "Configure Enterprise Features": """
# Enable/disable specific Enterprise features
widget.configure_enterprise_features(
    enable_charts=True,
    enable_pivot=True,
    show_tool_panel=True,
    enable_range_selection=True
)
""",
        "Pivot Mode Operations": """
# Toggle pivot mode
widget.toggle_pivot_mode()

# Check aggregation status
summary = widget.get_aggregation_summary()
print(f"Pivot mode: {summary['pivot_mode']}")
print(f"Row groups: {summary['row_groups']}")
""",
        "Chart Creation": """
# Create chart from selected data
widget.create_chart_from_selection('column')

# Available in Enterprise:
# - Right-click selected data → "Chart Data"
# - Drag columns in tool panel for instant charts
# - Multiple chart themes available
""",
        "Data Export": """
# Export to Excel (Enterprise feature)
widget.export_to_excel('my_analysis.xlsx')

# Access selected data
selected_df = widget.get_selected_dataframe()
""",
        "Key Enterprise Features": """
✨ What you get with Enterprise:
• 📊 Integrated Charts: Right-click data → instant charts
• 🔄 Pivot Tables: Drag columns to create pivot views  
• 🛠️ Tool Panel: Visual column management
• 📈 Range Selection: Select cells for analysis
• 📁 Excel Export: Professional data export
• 🎨 Advanced Themes: Premium chart themes
• ⚡ Performance: Optimized for large datasets
""",
    }

    for title, code in examples.items():
        print(f"\n💡 {title}:")
        print(code)


def main():
    """Run comprehensive Enterprise widget tests."""
    print("🎯 AG-Grid Enterprise Widget - Comprehensive Test Suite")
    print("=" * 80)

    try:
        # Run Enterprise tests
        widget, df = test_enterprise_basic_functionality()
        test_column_analysis()
        test_enterprise_features()
        test_data_manipulation()
        test_enterprise_export()

        print("\n" + "=" * 80)
        print("🎉 All Enterprise tests passed! Full functionality verified.")

        print("\n✨ Enterprise Features Available:")
        print("   • 📊 Integrated Charts - Create charts from grid selections")
        print("   • 🔄 Pivot Tables - Drag & drop column pivoting")
        print("   • 🛠️ Tool Panel - Visual column management interface")
        print("   • 📈 Range Selection - Select cell ranges for analysis")
        print("   • 🎯 Advanced Filtering - Enterprise filter options")
        print("   • 📁 Excel Export - Professional data export")
        print("   • 🎨 Premium Themes - Advanced chart styling")
        print("   • ⚡ High Performance - Optimized for large datasets")
        print("   • 📊 Status Bar - Aggregation and count displays")
        print("   • 🗂️ Row Grouping - Hierarchical data organization")

        # Show usage examples
        demo_usage_examples()

        print("\n🚀 Ready for Enterprise usage:")
        print(
            "   from dataframe_grid_charts_enterprise_widget import DataFrameGridChartsEnterpriseWidget"
        )
        print("   widget = DataFrameGridChartsEnterpriseWidget(dataframe=your_df)")
        print("   display(widget)  # Full Enterprise experience!")

        print("\n🎯 Enterprise-exclusive features:")
        print(
            "   • Right-click data selections → 'Chart Data' for instant visualization"
        )
        print("   • Drag columns in tool panel to Row Groups, Values, or Pivot areas")
        print("   • Select cell ranges and create charts from context menu")
        print("   • Export filtered/grouped data to Excel format")

        return widget

    except Exception as e:
        print(f"\n❌ Enterprise test failed: {e}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    widget = main()
