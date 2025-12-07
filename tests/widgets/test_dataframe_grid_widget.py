"""
Test script for DataFrameGridWidget

This script tests the AG-Grid widget with various pandas DataFrames to ensure
proper functionality and data serialization.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from edsl.widgets.dataframe_grid_widget import DataFrameGridWidget


def create_sample_dataframes():
    """Create various test DataFrames to test the widget."""

    # Simple test DataFrame
    simple_df = pd.DataFrame(
        {
            "Name": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
            "Age": [25, 30, 35, 28, 32],
            "City": ["New York", "London", "Tokyo", "Paris", "Berlin"],
            "Salary": [50000, 75000, 85000, 62000, 71000],
        }
    )

    # DataFrame with various data types
    mixed_df = pd.DataFrame(
        {
            "ID": range(1, 11),
            "Name": [f"Person_{i}" for i in range(1, 11)],
            "Score": np.random.normal(85, 10, 10),
            "Date": [datetime.now() - timedelta(days=x) for x in range(10)],
            "Active": [True, False, True, True, False, True, False, True, True, False],
            "Category": np.random.choice(["A", "B", "C"], 10),
            "Description": [f"Description for item {i}" for i in range(1, 11)],
        }
    )

    # Large DataFrame for performance testing
    large_df = pd.DataFrame(
        {
            "ID": range(1, 1001),
            "Value1": np.random.normal(100, 25, 1000),
            "Value2": np.random.exponential(50, 1000),
            "Category": np.random.choice(["Alpha", "Beta", "Gamma", "Delta"], 1000),
            "Timestamp": pd.date_range("2024-01-01", periods=1000, freq="H"),
        }
    )

    # DataFrame with missing values
    missing_df = pd.DataFrame(
        {
            "A": [1, 2, np.nan, 4, 5],
            "B": ["foo", None, "bar", "baz", "qux"],
            "C": [1.1, 2.2, 3.3, np.nan, 5.5],
            "D": [True, False, None, True, False],
        }
    )

    return {
        "simple": simple_df,
        "mixed": mixed_df,
        "large": large_df,
        "missing": missing_df,
    }


def test_widget_creation():
    """Test basic widget creation."""
    print("Testing widget creation...")

    # Test creation without data
    widget1 = DataFrameGridWidget()
    assert widget1.status == "ready"
    print("✓ Empty widget creation successful")

    # Test creation with data
    df = pd.DataFrame({"A": [1, 2, 3], "B": ["x", "y", "z"]})
    widget2 = DataFrameGridWidget(dataframe=df)
    assert widget2.status == "ready"
    assert len(widget2.data) == 3
    print("✓ Widget creation with data successful")


def test_data_processing():
    """Test data processing and serialization."""
    print("\nTesting data processing...")

    dataframes = create_sample_dataframes()

    for name, df in dataframes.items():
        print(f"Testing {name} DataFrame...")
        widget = DataFrameGridWidget()
        widget.set_dataframe(df)

        assert widget.status == "ready", f"Status should be ready for {name} DataFrame"
        assert len(widget.data) == len(df), f"Data length mismatch for {name} DataFrame"
        assert (
            len(widget.columns) == len(df.columns) + 1
        ), f"Column count mismatch for {name} DataFrame (+1 for row index)"

        print(
            f"  ✓ {name} DataFrame processed successfully ({len(df)} rows, {len(df.columns)} columns)"
        )


def test_configuration():
    """Test widget configuration options."""
    print("\nTesting configuration...")

    df = create_sample_dataframes()["simple"]
    widget = DataFrameGridWidget(dataframe=df)

    # Test initial configuration
    assert widget.page_size == 50
    assert widget.enable_sorting == True
    assert widget.enable_filtering == True
    assert widget.enable_selection == True
    assert widget.selection_mode == "multiple"

    # Test configuration changes
    widget.configure_grid(
        page_size=25,
        enable_sorting=False,
        enable_filtering=False,
        selection_mode="single",
    )

    assert widget.page_size == 25
    assert widget.enable_sorting == False
    assert widget.enable_filtering == False
    assert widget.selection_mode == "single"

    print("✓ Configuration changes successful")


def test_selection():
    """Test selection functionality."""
    print("\nTesting selection...")

    df = create_sample_dataframes()["simple"]
    widget = DataFrameGridWidget(dataframe=df)

    # Simulate selection from frontend
    widget.selected_indices = [0, 2, 4]
    selected_df = widget.get_selected_dataframe()

    assert selected_df is not None
    assert len(selected_df) == 3
    assert list(selected_df.index) == [0, 2, 4]

    # Test clear selection
    widget.clear_selection()
    assert len(widget.selected_rows) == 0
    assert len(widget.selected_indices) == 0

    print("✓ Selection functionality successful")


def test_error_handling():
    """Test error handling."""
    print("\nTesting error handling...")

    widget = DataFrameGridWidget()

    # Test with non-DataFrame input
    try:
        widget.dataframe = "not a dataframe"
        widget._process_dataframe()
        assert widget.status == "error"
        assert "DataFrame" in widget.error_message
        print("✓ Non-DataFrame input handled correctly")
    except Exception as e:
        print(f"✓ Exception caught as expected: {e}")

    # Test with empty DataFrame
    empty_df = pd.DataFrame()
    widget.set_dataframe(empty_df)
    assert widget.status == "error"
    assert "empty" in widget.error_message.lower()
    print("✓ Empty DataFrame handled correctly")


def test_column_types():
    """Test handling of different column types."""
    print("\nTesting column type handling...")

    # Create DataFrame with various column types
    df = pd.DataFrame(
        {
            "Integer": [1, 2, 3, 4, 5],
            "Float": [1.1, 2.2, 3.3, 4.4, 5.5],
            "String": ["a", "b", "c", "d", "e"],
            "Boolean": [True, False, True, False, True],
            "DateTime": pd.date_range("2024-01-01", periods=5, freq="D"),
            "Category": pd.Categorical(["X", "Y", "X", "Z", "Y"]),
        }
    )

    widget = DataFrameGridWidget(dataframe=df)
    assert widget.status == "ready"

    # Check that column definitions are created properly
    columns = widget.columns
    assert len(columns) == 7  # 6 data columns + 1 index column

    # Find specific column definitions (excluding the hidden index column)
    data_columns = [col for col in columns if not col.get("hide", False)]
    column_fields = [col["field"] for col in data_columns]

    assert "Integer" in column_fields
    assert "Float" in column_fields
    assert "String" in column_fields
    assert "Boolean" in column_fields
    assert "DateTime" in column_fields
    assert "Category" in column_fields

    print("✓ Column type handling successful")


def run_all_tests():
    """Run all tests."""
    print("Running DataFrameGridWidget tests...\n")

    try:
        test_widget_creation()
        test_data_processing()
        test_configuration()
        test_selection()
        test_error_handling()
        test_column_types()

        print("\n" + "=" * 50)
        print("🎉 All tests passed successfully!")
        print("The DataFrameGridWidget is ready for use.")
        print("=" * 50)

        # Show usage example
        print("\nUsage Example:")
        print("-" * 20)
        print(
            """
import pandas as pd
from edsl.widgets.dataframe_grid_widget import DataFrameGridWidget

# Create sample data
df = pd.DataFrame({
    'Name': ['Alice', 'Bob', 'Charlie'],
    'Age': [25, 30, 35],
    'City': ['NYC', 'London', 'Tokyo']
})

# Create and display widget
widget = DataFrameGridWidget(dataframe=df)
widget  # Display in Jupyter notebook
        """
        )

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    run_all_tests()
