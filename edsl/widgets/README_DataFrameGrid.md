# DataFrameGridWidget

An interactive AG-Grid widget for displaying and manipulating pandas DataFrames in Jupyter notebooks using anywidget and React.

## Features

- 📊 **Interactive Data Grid**: Display pandas DataFrames with professional-grade table interface
- 🔍 **Advanced Filtering**: Column-specific filters (text, number, date) with search capabilities  
- 📈 **Sorting**: Multi-column sorting with visual indicators
- ✅ **Row Selection**: Single or multiple row selection with programmatic access
- 📄 **Pagination**: Handle large datasets with configurable page sizes
- 💾 **Export Ready**: Built-in CSV export functionality
- 🎨 **Responsive Design**: Modern UI that adapts to different screen sizes
- 🔧 **Configurable**: Extensive customization options for appearance and behavior

## Installation

The widget is part of the EDSL widgets package. Make sure you have the required dependencies:

```bash
# Install EDSL (includes the widget)
pip install edsl

# For development, install additional dependencies
cd edsl/widgets/src
npm install
```

## Quick Start

```python
import pandas as pd
from edsl.widgets import DataFrameGridWidget

# Create sample data
df = pd.DataFrame({
    'Name': ['Alice', 'Bob', 'Charlie', 'Diana'],
    'Age': [25, 30, 35, 28],
    'City': ['New York', 'London', 'Tokyo', 'Paris'],
    'Salary': [75000, 85000, 95000, 70000]
})

# Create and display widget
widget = DataFrameGridWidget(dataframe=df)
display(widget)
```

## Advanced Usage

### Custom Configuration

```python
# Create widget with custom settings
widget = DataFrameGridWidget(dataframe=df)
widget.configure_grid(
    page_size=25,                    # Rows per page
    enable_sorting=True,             # Enable column sorting
    enable_filtering=True,           # Enable column filters
    enable_selection=True,           # Enable row selection
    selection_mode='multiple'        # 'single' or 'multiple'
)
```

### Working with Selections

```python
# Get selected data programmatically
selected_df = widget.get_selected_dataframe()

# Clear selection
widget.clear_selection()

# Access selection state
print(f"Selected rows: {len(widget.selected_rows)}")
print(f"Selected indices: {widget.selected_indices}")
```

### Dynamic Data Updates

```python
# Update the DataFrame
new_df = pd.DataFrame({
    'Product': ['Laptop', 'Mouse', 'Keyboard'],
    'Price': [999.99, 25.50, 79.99],
    'Stock': [15, 100, 45]
})

widget.set_dataframe(new_df)
```

## Supported Data Types

The widget automatically handles various pandas data types:

| Pandas Type | AG-Grid Rendering | Features |
|-------------|-------------------|-----------|
| `int64`, `float64` | Numeric columns | Number filtering, right-aligned |
| `object` (strings) | Text columns | Text filtering, left-aligned |
| `bool` | Checkbox renderer | Boolean filtering |
| `datetime64` | Date format | Date range filtering |
| `category` | Text with categories | Categorical filtering |

## Configuration Options

### Widget Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `dataframe` | pd.DataFrame | None | The DataFrame to display |
| `page_size` | int | 50 | Number of rows per page |
| `enable_sorting` | bool | True | Enable column sorting |
| `enable_filtering` | bool | True | Enable column filtering |
| `enable_selection` | bool | True | Enable row selection |
| `selection_mode` | str | 'multiple' | 'single' or 'multiple' |

### Methods

| Method | Parameters | Description |
|--------|------------|-------------|
| `set_dataframe(df)` | df: pd.DataFrame | Set new DataFrame |
| `configure_grid(**kwargs)` | Configuration options | Update grid settings |
| `get_selected_dataframe()` | None | Get DataFrame with selected rows |
| `clear_selection()` | None | Clear current selection |

### State Properties (Read-only)

| Property | Type | Description |
|----------|------|-------------|
| `status` | str | Widget status ('ready', 'processing', 'error') |
| `error_message` | str | Error message if status is 'error' |
| `selected_rows` | list | Selected row data |
| `selected_indices` | list | Selected row indices |
| `data` | list | Processed data for display |
| `columns` | list | Column definitions for AG-Grid |

## Examples

### Sales Dashboard

```python
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Create sales data
np.random.seed(42)
sales_df = pd.DataFrame({
    'Product': ['Laptop', 'Mouse', 'Keyboard'] * 20,
    'Price': np.random.uniform(50, 1000, 60),
    'Quantity': np.random.randint(1, 50, 60),
    'Date': pd.date_range('2024-01-01', periods=60, freq='D'),
    'Category': np.random.choice(['Electronics', 'Accessories'], 60)
})
sales_df['Total'] = (sales_df['Price'] * sales_df['Quantity']).round(2)

# Create interactive grid
widget = DataFrameGridWidget(dataframe=sales_df)
widget.configure_grid(page_size=20)
display(widget)
```

### Employee Directory

```python
# Employee data
employees_df = pd.DataFrame({
    'ID': range(1001, 1021),
    'Name': [f'Employee_{i}' for i in range(1, 21)],
    'Department': np.random.choice(['Engineering', 'Sales', 'Marketing'], 20),
    'Salary': np.random.uniform(40000, 120000, 20).round(0),
    'Hire_Date': pd.date_range('2020-01-01', periods=20, freq='90D'),
    'Remote': np.random.choice([True, False], 20)
})

# Create filterable employee grid
widget = DataFrameGridWidget(dataframe=employees_df)
widget.configure_grid(
    selection_mode='single',
    page_size=15
)
display(widget)
```

## Error Handling

The widget provides comprehensive error handling:

```python
widget = DataFrameGridWidget()

# Check widget status
if widget.status == 'error':
    print(f"Error: {widget.error_message}")
elif widget.status == 'processing':
    print("Processing data...")
else:
    print("Widget ready!")
```

Common error scenarios:
- Invalid input (non-DataFrame)
- Empty DataFrame
- Memory issues with very large datasets
- Column type conversion errors

## Performance Considerations

- **Large Datasets**: For DataFrames with >10,000 rows, the widget automatically samples data for display
- **Memory Usage**: Row data is serialized to JSON, so very wide DataFrames may impact performance  
- **Real-time Updates**: Frequent DataFrame updates trigger re-processing; batch changes when possible
- **Selection Performance**: Large selections (>1000 rows) may experience UI lag

## Browser Compatibility

The widget requires a modern browser with JavaScript enabled:

- ✅ Chrome 90+
- ✅ Firefox 88+  
- ✅ Safari 14+
- ✅ Edge 90+

## Troubleshooting

### Widget Not Displaying

1. Ensure JavaScript is enabled in Jupyter
2. Check that anywidget is installed: `pip install anywidget`
3. Restart Jupyter kernel and try again

### Performance Issues

1. Reduce DataFrame size or use sampling
2. Disable unnecessary features (filtering/sorting)
3. Increase pagination page size
4. Check browser developer console for errors

### Selection Not Working

1. Ensure `enable_selection=True`
2. Check that `selection_mode` is set correctly
3. Verify DataFrame has proper index

## Development

### Building from Source

```bash
cd edsl/widgets/src
npm install
npm run build-react
```

### Running Tests

```bash
cd edsl/widgets
python test_dataframe_grid_widget.py
```

### Creating New Features

The widget follows the EDSL widget architecture:
1. Extend `EDSLBaseWidget` 
2. Define `widget_short_name`
3. Create corresponding React component in `src/source/react_files/`
4. Add CSS in `src/source/css_files/`
5. Build and test

## License

This widget is part of EDSL and is licensed under the MIT License.

## Contributing

Contributions are welcome! Please see the main EDSL repository for contribution guidelines.

## Support

For issues and questions:
- GitHub Issues: [EDSL Repository](https://github.com/expectedparrot/edsl)
- Documentation: [EDSL Docs](https://docs.expectedparrot.com)