"""
Demo script for DataFrameGridWidget

This script demonstrates how to use the AG-Grid widget with pandas DataFrames.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add the current directory to the Python path for importing the widget
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from dataframe_grid_widget import DataFrameGridWidget
except ImportError:
    print("Failed to import DataFrameGridWidget. Make sure the widget is properly installed.")
    sys.exit(1)

def create_demo_dataframes():
    """Create demo DataFrames for showcasing the widget."""
    
    # Sales data example
    np.random.seed(42)
    sales_data = pd.DataFrame({
        'Product': ['Laptop', 'Mouse', 'Keyboard', 'Monitor', 'Tablet', 'Phone', 'Headphones', 'Camera', 'Printer', 'Speaker'] * 10,
        'Category': ['Electronics', 'Accessories', 'Accessories', 'Electronics', 'Electronics', 'Electronics', 'Accessories', 'Electronics', 'Electronics', 'Electronics'] * 10,
        'Price': np.random.uniform(50, 2000, 100),
        'Quantity': np.random.randint(1, 100, 100),
        'Date': pd.date_range('2024-01-01', periods=100, freq='D'),
        'In_Stock': np.random.choice([True, False], 100, p=[0.8, 0.2]),
        'Rating': np.random.uniform(1, 5, 100),
        'Discount': np.random.uniform(0, 0.5, 100)
    })
    
    # Calculate additional columns
    sales_data['Total_Value'] = sales_data['Price'] * sales_data['Quantity'] * (1 - sales_data['Discount'])
    sales_data['Price'] = sales_data['Price'].round(2)
    sales_data['Rating'] = sales_data['Rating'].round(1)
    sales_data['Discount'] = (sales_data['Discount'] * 100).round(1)
    sales_data['Total_Value'] = sales_data['Total_Value'].round(2)
    
    # Employee data example
    employee_data = pd.DataFrame({
        'Employee_ID': range(1001, 1051),
        'Name': [f'Employee_{i}' for i in range(1, 51)],
        'Department': np.random.choice(['Engineering', 'Sales', 'Marketing', 'HR', 'Finance'], 50),
        'Salary': np.random.uniform(40000, 150000, 50),
        'Hire_Date': pd.date_range('2020-01-01', periods=50, freq='30D'),
        'Performance_Score': np.random.uniform(1, 10, 50),
        'Remote_Work': np.random.choice([True, False], 50, p=[0.6, 0.4]),
        'Years_Experience': np.random.randint(0, 15, 50)
    })
    
    employee_data['Salary'] = employee_data['Salary'].round(0).astype(int)
    employee_data['Performance_Score'] = employee_data['Performance_Score'].round(1)
    
    return {
        'sales': sales_data,
        'employees': employee_data
    }

def demo_basic_usage():
    """Demonstrate basic widget usage."""
    print("🔄 Creating basic demo DataFrame...")
    
    # Create a simple DataFrame
    df = pd.DataFrame({
        'Name': ['Alice Johnson', 'Bob Smith', 'Charlie Brown', 'Diana Prince', 'Eve Wilson'],
        'Age': [25, 30, 35, 28, 32],
        'City': ['New York', 'London', 'Tokyo', 'Paris', 'Berlin'],
        'Salary': [75000, 85000, 95000, 70000, 90000],
        'Department': ['Engineering', 'Marketing', 'Engineering', 'Sales', 'HR']
    })
    
    print("✓ DataFrame created with 5 employees")
    print("\nDataFrame preview:")
    print(df.head())
    
    # Create widget
    widget = DataFrameGridWidget(dataframe=df)
    print(f"\n✓ Widget created successfully (Status: {widget.status})")
    print(f"  - Data rows: {len(widget.data)}")
    print(f"  - Columns: {len(widget.columns)}")
    print(f"  - Page size: {widget.page_size}")
    
    return widget

def demo_advanced_features():
    """Demonstrate advanced widget features."""
    print("\n🔄 Creating advanced demo with sales data...")
    
    dataframes = create_demo_dataframes()
    sales_df = dataframes['sales']
    
    print(f"✓ Sales DataFrame created with {len(sales_df)} rows")
    print("\nDataFrame info:")
    print(f"  - Columns: {list(sales_df.columns)}")
    print(f"  - Data types: {sales_df.dtypes.to_dict()}")
    
    # Create widget with custom configuration
    widget = DataFrameGridWidget(dataframe=sales_df)
    widget.configure_grid(
        page_size=25,
        enable_sorting=True,
        enable_filtering=True,
        enable_selection=True,
        selection_mode='multiple'
    )
    
    print(f"\n✓ Advanced widget created (Status: {widget.status})")
    print(f"  - Configuration: Page size={widget.page_size}, Selection={widget.selection_mode}")
    
    # Demonstrate selection simulation (in a real Jupyter environment, this would be done via the UI)
    print("\n🔄 Simulating row selection...")
    widget.selected_indices = [0, 5, 10, 15, 20]  # Select some rows
    selected_df = widget.get_selected_dataframe()
    
    if selected_df is not None:
        print(f"✓ {len(selected_df)} rows selected")
        print("  Selected products:", selected_df['Product'].tolist()[:3], "...")
    
    return widget

def demo_data_types():
    """Demonstrate handling of various data types."""
    print("\n🔄 Creating demo with various data types...")
    
    # Create DataFrame with all supported data types
    df = pd.DataFrame({
        'ID': range(1, 11),
        'Name': [f'Item_{i}' for i in range(1, 11)],
        'Value': np.random.normal(100, 20, 10),
        'Timestamp': pd.date_range('2024-01-01', periods=10, freq='D'),
        'Is_Active': [True, False] * 5,
        'Category': pd.Categorical(['A', 'B', 'C'] * 3 + ['A']),
        'Description': [f'Description for item {i} with some longer text to test column width' for i in range(1, 11)],
        'Nullable_Value': [1, None, 3, 4, None, 6, 7, None, 9, 10]
    })
    
    print("✓ Multi-type DataFrame created")
    print("\nData types:")
    for col, dtype in df.dtypes.items():
        print(f"  - {col}: {dtype}")
    
    # Create widget
    widget = DataFrameGridWidget(dataframe=df)
    print(f"\n✓ Multi-type widget created (Status: {widget.status})")
    
    # Check column definitions
    data_columns = [col for col in widget.columns if not col.get('hide', False)]
    print(f"  - Column definitions created: {len(data_columns)} visible columns")
    
    return widget

def demo_error_handling():
    """Demonstrate error handling capabilities."""
    print("\n🔄 Testing error handling...")
    
    # Test with invalid data
    widget = DataFrameGridWidget()
    
    # Invalid input
    try:
        widget.dataframe = "not a dataframe"
        widget._process_dataframe()
        print(f"✓ Invalid input handled: Status={widget.status}, Error='{widget.error_message}'")
    except:
        print("✓ Invalid input caused expected exception")
    
    # Empty DataFrame
    empty_df = pd.DataFrame()
    widget.set_dataframe(empty_df)
    print(f"✓ Empty DataFrame handled: Status={widget.status}, Error='{widget.error_message}'")
    
    return widget

def main():
    """Run all demos."""
    print("=" * 60)
    print("🚀 DataFrameGridWidget Demo")
    print("=" * 60)
    
    try:
        # Basic demo
        basic_widget = demo_basic_usage()
        
        # Advanced demo
        advanced_widget = demo_advanced_features()
        
        # Data types demo
        types_widget = demo_data_types()
        
        # Error handling demo
        error_widget = demo_error_handling()
        
        print("\n" + "=" * 60)
        print("✅ All demos completed successfully!")
        print("=" * 60)
        
        print("\n📋 Summary:")
        print("  - Basic widget: Ready for Jupyter display")
        print("  - Advanced widget: Ready with custom configuration")
        print("  - Data types widget: Handles multiple column types")
        print("  - Error handling: Properly manages edge cases")
        
        print("\n🎯 Next Steps:")
        print("  1. In a Jupyter notebook, import the widget:")
        print("     from edsl.widgets import DataFrameGridWidget")
        print("  2. Create a DataFrame and display:")
        print("     widget = DataFrameGridWidget(dataframe=your_df)")
        print("     display(widget)")
        print("  3. Interact with the grid in the browser")
        
        print("\n💡 Features:")
        print("  - Sorting: Click column headers")
        print("  - Filtering: Use column filter menus")
        print("  - Selection: Click rows (single/multiple modes)")
        print("  - Pagination: Navigate large datasets")
        print("  - Export: CSV export functionality")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        raise

if __name__ == "__main__":
    main()