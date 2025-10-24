#!/usr/bin/env python3
"""
Test script for AG-Grid DataFrameGridWidget implementation

This script demonstrates the AG-Grid functionality with various DataFrame types.
"""

import pandas as pd
import numpy as np
import sys
import os

# Add the widgets directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from dataframe_grid_widget import DataFrameGridWidget


def create_sample_data():
    """Create sample data for testing."""
    np.random.seed(42)

    # Create a diverse dataset
    dates = pd.date_range(start="2023-01-01", periods=100, freq="D")
    data = {
        "id": range(1, 101),
        "name": [f"Item {i}" for i in range(1, 101)],
        "category": np.random.choice(["A", "B", "C", "D"], 100),
        "value": np.random.randn(100) * 100 + 500,
        "price": np.random.uniform(10, 1000, 100).round(2),
        "date": dates,
        "active": np.random.choice([True, False], 100),
        "score": np.random.randint(1, 100, 100),
        "description": [f"Description for item {i}" for i in range(1, 101)],
    }

    return pd.DataFrame(data)


def test_basic_functionality():
    """Test basic AG-Grid functionality."""
    print("Testing basic AG-Grid functionality...")

    # Create sample data
    df = create_sample_data()

    # Create widget
    widget = DataFrameGridWidget(dataframe=df)

    # Check that data was processed correctly
    assert len(widget.data) == len(
        df
    ), f"Data length mismatch: expected {len(df)}, got {len(widget.data)}"
    assert (
        len(widget.columns) == len(df.columns) + 1
    ), "Column count mismatch (should include _row_index)"
    assert (
        widget.status == "ready"
    ), f"Widget status should be 'ready', got '{widget.status}'"

    print(
        f"✓ Widget created successfully with {len(widget.data)} rows and {len(widget.columns)} columns"
    )

    return widget


def test_configuration():
    """Test AG-Grid configuration options."""
    print("\nTesting AG-Grid configuration...")

    df = create_sample_data()
    widget = DataFrameGridWidget(dataframe=df)

    # Test configuration
    widget.configure_grid(
        page_size=25,
        enable_sorting=False,
        enable_filtering=False,
        enable_selection=True,
        selection_mode="single",
    )

    assert widget.page_size == 25, "Page size not set correctly"
    assert widget.enable_sorting == False, "Sorting not disabled"
    assert widget.enable_filtering == False, "Filtering not disabled"
    assert widget.enable_selection == True, "Selection not enabled"
    assert widget.selection_mode == "single", "Selection mode not set to single"

    print("✓ Configuration options work correctly")


def test_data_types():
    """Test AG-Grid with various data types."""
    print("\nTesting AG-Grid with various data types...")

    # Create data with various types
    data = {
        "integers": [1, 2, 3, 4, 5],
        "floats": [1.1, 2.2, 3.3, 4.4, 5.5],
        "strings": ["a", "b", "c", "d", "e"],
        "booleans": [True, False, True, False, True],
        "dates": pd.date_range("2023-01-01", periods=5),
        "mixed": [1, "text", 3.14, True, None],
    }

    df = pd.DataFrame(data)
    widget = DataFrameGridWidget(dataframe=df)

    assert widget.status == "ready", "Widget should handle mixed data types"

    # Check column definitions were created with appropriate types
    columns = [col for col in widget.columns if col["field"] != "_row_index"]

    # Find numeric columns
    numeric_cols = [col for col in columns if col.get("type") == "numericColumn"]
    assert len(numeric_cols) >= 2, "Should detect numeric columns (integers and floats)"

    print("✓ Various data types handled correctly")


def test_empty_data():
    """Test AG-Grid with empty data."""
    print("\nTesting AG-Grid with empty data...")

    # Empty DataFrame
    df = pd.DataFrame()
    widget = DataFrameGridWidget(dataframe=df)

    assert widget.status == "error", "Empty DataFrame should result in error status"
    assert (
        "empty" in widget.error_message.lower()
    ), "Error message should mention empty DataFrame"

    print("✓ Empty data handled correctly")


def test_large_dataset():
    """Test AG-Grid with a larger dataset."""
    print("\nTesting AG-Grid with larger dataset...")

    # Create larger dataset
    np.random.seed(42)
    large_data = {
        "id": range(1, 1001),
        "value": np.random.randn(1000),
        "category": np.random.choice(["A", "B", "C"], 1000),
        "timestamp": pd.date_range("2023-01-01", periods=1000, freq="H"),
    }

    df = pd.DataFrame(large_data)
    widget = DataFrameGridWidget(dataframe=df)

    assert widget.status == "ready", "Large dataset should be processed successfully"
    assert len(widget.data) == 1000, "All rows should be processed"

    print("✓ Large dataset (1000 rows) handled correctly")


def test_column_definitions():
    """Test AG-Grid column definitions."""
    print("\nTesting AG-Grid column definitions...")

    df = create_sample_data()
    widget = DataFrameGridWidget(dataframe=df)

    # Check column definitions
    visible_columns = [col for col in widget.columns if col["field"] != "_row_index"]

    # Should have one column per DataFrame column
    assert len(visible_columns) == len(
        df.columns
    ), f"Should have {len(df.columns)} visible columns"

    # Check that all DataFrame columns are represented
    df_columns = set(df.columns)
    widget_columns = set(col["field"] for col in visible_columns)
    assert (
        df_columns == widget_columns
    ), f"Column mismatch: {df_columns} vs {widget_columns}"

    # Check that sorting and filtering are enabled by default
    sortable_columns = [col for col in visible_columns if col.get("sortable", False)]
    filterable_columns = [col for col in visible_columns if col.get("filter", False)]

    assert len(sortable_columns) == len(
        visible_columns
    ), "All columns should be sortable by default"
    assert len(filterable_columns) == len(
        visible_columns
    ), "All columns should be filterable by default"

    print("✓ Column definitions created correctly")


def main():
    """Run all tests."""
    print("Testing AG-Grid DataFrameGridWidget Implementation")
    print("=" * 50)

    try:
        # Run tests
        widget = test_basic_functionality()
        test_configuration()
        test_data_types()
        test_empty_data()
        test_large_dataset()
        test_column_definitions()

        print("\n" + "=" * 50)
        print("🎉 All tests passed! AG-Grid implementation is working correctly.")
        print("\nFeatures verified:")
        print("- Basic data processing and display")
        print("- Configuration options (pagination, sorting, filtering, selection)")
        print("- Various data types (integers, floats, strings, booleans, dates)")
        print("- Error handling for empty data")
        print("- Large dataset handling (1000+ rows)")
        print("- Proper column definitions with AG-Grid options")

        return widget

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    widget = main()
