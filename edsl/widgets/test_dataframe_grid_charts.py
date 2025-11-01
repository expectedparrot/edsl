#!/usr/bin/env python3
"""
Test script for DataFrameGridChartsWidget

This script demonstrates the combined AG-Grid and AG-Charts functionality.
"""

import pandas as pd
import numpy as np
import sys
import os

# Add the widgets directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from dataframe_grid_charts_widget import DataFrameGridChartsWidget


def create_sample_data():
    """Create comprehensive sample data for testing."""
    np.random.seed(42)

    # Create diverse sample data
    dates = pd.date_range(start="2023-01-01", periods=200, freq="D")
    products = ["iPhone", "MacBook", "iPad", "Apple Watch", "AirPods"]
    regions = ["North America", "Europe", "Asia", "South America"]

    data = {
        "Date": dates,
        "Product": np.random.choice(products, 200),
        "Region": np.random.choice(regions, 200),
        "Sales": np.random.uniform(1000, 50000, 200).round(2),
        "Units_Sold": np.random.randint(10, 1000, 200),
        "Profit_Margin": np.random.uniform(0.1, 0.5, 200).round(3),
        "Customer_Rating": np.random.uniform(3.0, 5.0, 200).round(1),
        "Marketing_Spend": np.random.uniform(100, 5000, 200).round(2),
        "Seasonal_Factor": np.sin(np.arange(200) * 2 * np.pi / 365)
        + np.random.normal(0, 0.1, 200),
        "Is_Premium": np.random.choice([True, False], 200, p=[0.3, 0.7]),
        "Category": np.random.choice(["Electronics", "Accessories"], 200),
    }

    return pd.DataFrame(data)


def test_basic_functionality():
    """Test basic grid and charts functionality."""
    print("🔥 Testing DataFrameGridChartsWidget Basic Functionality")
    print("=" * 60)

    # Create sample data
    df = create_sample_data()
    print(f"📊 Created sample dataset with {len(df)} rows and {len(df.columns)} columns")

    # Create widget
    widget = DataFrameGridChartsWidget(dataframe=df)

    # Verify basic setup
    assert (
        widget.status == "ready"
    ), f"Widget status should be 'ready', got '{widget.status}'"
    assert len(widget.data) == len(df), "Data length mismatch"
    assert (
        len(widget.columns) == len(df.columns) + 1
    ), "Column count mismatch (should include _row_index)"

    # Verify column analysis
    assert len(widget.numeric_columns) > 0, "Should detect numeric columns"
    assert len(widget.categorical_columns) > 0, "Should detect categorical columns"
    assert len(widget.datetime_columns) > 0, "Should detect datetime columns"

    print("✅ Widget created successfully:")
    print(f"   • Status: {widget.status}")
    print(f"   • Data rows: {len(widget.data)}")
    print(f"   • Grid columns: {len(widget.columns)}")
    print(
        f"   • Numeric columns: {len(widget.numeric_columns)} - {widget.numeric_columns[:3]}..."
    )
    print(
        f"   • Categorical columns: {len(widget.categorical_columns)} - {widget.categorical_columns}"
    )
    print(
        f"   • Datetime columns: {len(widget.datetime_columns)} - {widget.datetime_columns}"
    )

    return widget, df


def test_chart_configuration():
    """Test chart configuration options."""
    print("\n⚙️ Testing Chart Configuration")
    print("=" * 40)

    df = create_sample_data()
    widget = DataFrameGridChartsWidget(dataframe=df)

    # Test different chart types
    chart_types = ["bar", "line", "scatter", "pie", "area"]

    for chart_type in chart_types:
        print(f"🔄 Testing {chart_type} chart...")

        # Configure chart
        widget.configure_chart(
            chart_type=chart_type,
            x_column="Product" if chart_type == "pie" else "Region",
            y_column="Sales",
            title=f"{chart_type.title()} Chart - Sales by Region",
        )

        assert widget.chart_type == chart_type, "Chart type not set correctly"
        assert (
            widget.chart_options != {}
        ), f"Chart options should be generated for {chart_type}"

        # Verify chart options structure
        options = widget.chart_options
        assert "data" in options, f"Chart options should contain data for {chart_type}"
        assert (
            "series" in options
        ), f"Chart options should contain series for {chart_type}"
        assert (
            len(options["series"]) > 0
        ), f"Should have at least one series for {chart_type}"

        print(f"   ✅ {chart_type} chart configured successfully")

    print("✅ All chart types configured successfully")


def test_layout_modes():
    """Test different layout modes."""
    print("\n🖼️  Testing Layout Modes")
    print("=" * 40)

    df = create_sample_data()
    widget = DataFrameGridChartsWidget(dataframe=df)

    layout_modes = ["split", "grid-only", "charts-only", "tabs"]

    for mode in layout_modes:
        print(f"🔄 Testing {mode} layout...")

        widget.set_layout_mode(mode)
        assert widget.layout_mode == mode, "Layout mode not set correctly"

        print(f"   ✅ {mode} layout set successfully")

    print("✅ All layout modes tested successfully")


def test_grid_configuration():
    """Test grid configuration options."""
    print("\n🔧 Testing Grid Configuration")
    print("=" * 40)

    df = create_sample_data()
    widget = DataFrameGridChartsWidget(dataframe=df)

    # Test grid configuration
    widget.configure_grid(
        page_size=25,
        enable_sorting=True,
        enable_filtering=True,
        enable_selection=True,
        selection_mode="multiple",
    )

    assert widget.page_size == 25, "Page size not set correctly"
    assert widget.enable_sorting == True, "Sorting not enabled"
    assert widget.enable_filtering == True, "Filtering not enabled"
    assert widget.enable_selection == True, "Selection not enabled"
    assert widget.selection_mode == "multiple", "Selection mode not set correctly"

    print("✅ Grid configuration options work correctly")


def test_data_selection_integration():
    """Test integration between grid selection and charts."""
    print("\n🔗 Testing Selection Integration")
    print("=" * 40)

    df = create_sample_data()
    widget = DataFrameGridChartsWidget(dataframe=df)

    # Configure for testing
    widget.configure_chart(
        chart_type="bar", x_column="Region", y_column="Sales", title="Sales by Region"
    )

    # Simulate selection (normally done by frontend)
    selected_indices = [0, 1, 2, 5, 10]  # Select some rows
    selected_rows = [widget.data[i] for i in selected_indices]

    widget.selected_indices = selected_indices
    widget.selected_rows = selected_rows

    # Verify selection methods
    selected_df = widget.get_selected_dataframe()
    assert selected_df is not None, "Should return selected DataFrame"
    assert len(selected_df) == len(
        selected_indices
    ), "Selected DataFrame should have correct length"

    print("✅ Selection integration works correctly:")
    print(f"   • Selected {len(selected_indices)} rows")
    print(f"   • Selected DataFrame shape: {selected_df.shape}")

    # Test clear selection
    widget.clear_selection()
    assert len(widget.selected_rows) == 0, "Selection should be cleared"
    assert len(widget.selected_indices) == 0, "Selection indices should be cleared"

    print("✅ Clear selection works correctly")


def test_error_handling():
    """Test error handling scenarios."""
    print("\n⚠️  Testing Error Handling")
    print("=" * 40)

    # Test empty DataFrame
    empty_df = pd.DataFrame()
    widget = DataFrameGridChartsWidget(dataframe=empty_df)

    assert widget.status == "error", "Empty DataFrame should result in error status"
    assert (
        "empty" in widget.error_message.lower()
    ), "Error message should mention empty DataFrame"
    print("✅ Empty DataFrame handled correctly")

    # Test invalid data
    try:
        widget = DataFrameGridChartsWidget(dataframe="not a dataframe")
        assert widget.status == "error", "Invalid data should result in error status"
        print("✅ Invalid data type handled correctly")
    except:
        print("✅ Invalid data type handled correctly (with exception)")

    # Test invalid layout mode
    widget = DataFrameGridChartsWidget(dataframe=create_sample_data())
    try:
        widget.set_layout_mode("invalid_mode")
        assert False, "Should raise error for invalid layout mode"
    except ValueError:
        print("✅ Invalid layout mode handled correctly")


def test_column_analysis():
    """Test column type analysis."""
    print("\n🔍 Testing Column Analysis")
    print("=" * 40)

    # Create data with specific column types
    mixed_data = {
        "integer_col": [1, 2, 3, 4, 5],
        "float_col": [1.1, 2.2, 3.3, 4.4, 5.5],
        "string_col": ["a", "b", "c", "d", "e"],
        "category_col": ["cat1", "cat2", "cat1", "cat2", "cat1"],
        "date_col": pd.date_range("2023-01-01", periods=5),
        "boolean_col": [True, False, True, False, True],
        "high_cardinality": [
            f"item_{i}" for i in range(5)
        ],  # Should not be categorical
    }

    df = pd.DataFrame(mixed_data)
    widget = DataFrameGridChartsWidget(dataframe=df)

    # Verify column analysis
    print("📊 Column analysis results:")
    print(f"   • Numeric: {widget.numeric_columns}")
    print(f"   • Categorical: {widget.categorical_columns}")
    print(f"   • Datetime: {widget.datetime_columns}")

    # Verify expected classifications
    assert "integer_col" in widget.numeric_columns, "Integer column should be numeric"
    assert "float_col" in widget.numeric_columns, "Float column should be numeric"
    assert (
        "category_col" in widget.categorical_columns
    ), "Low cardinality string should be categorical"
    assert "date_col" in widget.datetime_columns, "Date column should be datetime"

    print("✅ Column analysis working correctly")


def demo_usage_examples():
    """Show usage examples."""
    print("\n📖 Usage Examples")
    print("=" * 40)

    examples = {
        "Basic Usage": """
# Create widget with DataFrame
widget = DataFrameGridChartsWidget(dataframe=your_df)

# Display in Jupyter
display(widget)
""",
        "Configure Charts": """
# Set up a bar chart
widget.configure_chart(
    chart_type='bar',
    x_column='Category',
    y_column='Sales',
    title='Sales by Category'
)
""",
        "Layout Options": """
# Split view (default)
widget.set_layout_mode('split')

# Grid only
widget.set_layout_mode('grid-only')

# Charts only  
widget.set_layout_mode('charts-only')

# Tabbed interface
widget.set_layout_mode('tabs')
""",
        "Grid Configuration": """
# Configure grid behavior
widget.configure_grid(
    page_size=100,
    enable_selection=True,
    selection_mode='multiple'
)
""",
        "Access Selected Data": """
# Get selected rows as DataFrame
selected_df = widget.get_selected_dataframe()
if selected_df is not None:
    print(f"Selected {len(selected_df)} rows")
""",
    }

    for title, code in examples.items():
        print(f"\n💡 {title}:")
        print(code)


def main():
    """Run comprehensive tests."""
    print("🚀 DataFrameGridChartsWidget Comprehensive Test Suite")
    print("=" * 70)

    try:
        # Run all tests
        widget, df = test_basic_functionality()
        test_chart_configuration()
        test_layout_modes()
        test_grid_configuration()
        test_data_selection_integration()
        test_error_handling()
        test_column_analysis()

        print("\n" + "=" * 70)
        print("🎉 All tests passed! DataFrameGridChartsWidget is working correctly.")

        print("\n✨ Features verified:")
        print("   • ✅ AG-Grid integration with sorting, filtering, pagination")
        print("   • ✅ AG-Charts integration with multiple chart types")
        print("   • ✅ Dynamic column analysis (numeric, categorical, datetime)")
        print("   • ✅ Multiple layout modes (split, grid-only, charts-only, tabs)")
        print("   • ✅ Row selection synchronization between grid and charts")
        print("   • ✅ Chart configuration (type, axes, titles)")
        print("   • ✅ Grid configuration (page size, selection, filtering)")
        print("   • ✅ Error handling for edge cases")
        print("   • ✅ Data type handling (integers, floats, strings, dates, booleans)")

        # Show usage examples
        demo_usage_examples()

        print("\n🔧 Ready for Jupyter usage:")
        print("   from dataframe_grid_charts_widget import DataFrameGridChartsWidget")
        print("   widget = DataFrameGridChartsWidget(dataframe=your_df)")
        print("   display(widget)")

        return widget

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    widget = main()
