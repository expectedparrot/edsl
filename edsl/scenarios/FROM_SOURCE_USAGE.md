# ScenarioList.from_source() - Enhanced with Auto-Detection

The `from_source()` method now has **two modes** based on the number of arguments:

## 🎯 Auto-Detect Mode (1 argument)

Pass only your data, and it will automatically detect the source type and print what was detected:

```python
from edsl.scenarios import ScenarioList

# Dictionary
sl = ScenarioList.from_source({'name': ['Alice', 'Bob'], 'age': [25, 30]})
# Output: Detected source type: dictionary

# CSV file
sl = ScenarioList.from_source('data.csv')
# Output: Detected source type: CSV file at data.csv

# Pandas DataFrame
import pandas as pd
df = pd.DataFrame({'x': [1, 2], 'y': [3, 4]})
sl = ScenarioList.from_source(df)
# Output: Detected source type: pandas DataFrame

# List
sl = ScenarioList.from_source(['apple', 'banana'], field_name='fruit')
# Output: Detected source type: list

# URL
sl = ScenarioList.from_source('https://example.com/data.csv')
# Output: Detected source type: CSV file at https://example.com/data.csv
```

## 📋 Explicit Mode (2+ arguments) 

Pass the source type explicitly for backward compatibility (no auto-detect message):

```python
# Original behavior - still works!
sl = ScenarioList.from_source('csv', 'data.csv')
sl = ScenarioList.from_source('excel', 'data.xlsx', sheet_name='Sheet1')
sl = ScenarioList.from_source('pdf', 'document.pdf', chunk_type='page')
```

## How It Works

The method checks the number of positional arguments:

- **1 argument** (`len(args) == 0`): Auto-detect mode → Uses the inferrer
- **2+ arguments** (`len(args) > 0`): Explicit mode → Uses ScenarioSource directly

## Supported Data Sources (Auto-Detect)

All the same sources supported by the inferrer:

### Data Structures
- Dictionaries (simple and nested)
- Lists (values and tuples)
- Pandas DataFrames

### File Formats
- CSV (`.csv`)
- TSV (`.tsv`)
- Excel (`.xls`, `.xlsx`, `.xlsm`)
- Parquet (`.parquet`)
- PDF (`.pdf`)
- SQLite (`.db`, `.sqlite`, `.sqlite3`)
- Stata (`.dta`)
- LaTeX (`.tex`, `.latex`)
- Text files (`.txt`, `.dat`)

### URLs
- Wikipedia tables
- Google Sheets
- Google Docs
- Direct file URLs (CSV, Excel, PDF, etc.)

### Directories
- File scanning with pattern matching

## Examples

### Auto-Detect Examples

```python
# From nested dictionary
data = {
    "item1": {"product": "coffee", "price": 4.99},
    "item2": {"product": "tea", "price": 3.50}
}
sl = ScenarioList.from_source(data, id_field="item_id")
# Output: Detected source type: nested dictionary

# From Excel file
sl = ScenarioList.from_source("sales.xlsx", sheet_name="Q4")
# Output: Detected source type: Excel file at sales.xlsx

# From Wikipedia
sl = ScenarioList.from_source("https://en.wikipedia.org/wiki/Example", table_index=0)
# Output: Detected source type: Wikipedia table at https://en.wikipedia.org/wiki/Example

# From list of tuples
data = [("Alice", 25), ("Bob", 30)]
sl = ScenarioList.from_source(data, field_names=["name", "age"])
# Output: Detected source type: list of tuples
```

### Explicit Mode Examples (Backward Compatible)

```python
# Explicitly specify source type (original behavior)
sl = ScenarioList.from_source('csv', 'data.csv')
sl = ScenarioList.from_source('directory', '/path/to/files', pattern='*.txt')
sl = ScenarioList.from_source('sqlite', 'db.sqlite3', 'users', fields=['name', 'age'])
```

## Benefits

1. **Simpler syntax**: `ScenarioList.from_source(data)` vs `ScenarioList.from_source('csv', data)`
2. **Transparency**: Prints what was detected so you know how your data is interpreted
3. **Backward compatible**: All existing code continues to work
4. **No getattr() needed**: Unlike using a reserved keyword like `from`, this works with normal syntax
5. **Less to remember**: Don't need to remember source type strings for common cases

## Migration Guide

### Before (Explicit)
```python
sl = ScenarioList.from_source('csv', 'data.csv')
sl = ScenarioList.from_source('pandas', df)
sl = ScenarioList.from_source('dict', data)
```

### After (Auto-Detect - Simpler!)
```python
sl = ScenarioList.from_source('data.csv')
sl = ScenarioList.from_source(df)
sl = ScenarioList.from_source(data)
```

Both approaches work! Use whichever you prefer.

## Error Handling

If auto-detection fails, you'll get a helpful error message:

```python
try:
    sl = ScenarioList.from_source(unsupported_data)
except ScenarioError as e:
    print(f"Could not auto-detect: {e}")
    # Fall back to explicit mode
    sl = ScenarioList.from_source('csv', 'data.txt')
```

## Comparison with Other Functions

- `ScenarioList.from_source(data)` - Auto-detects and prints source type ✨
- `from_any(data)` - Auto-detects but doesn't print by default
- `ScenarioSourceInferrer.infer_and_create(data, verbose=True)` - Full control over verbose flag

Choose the one that fits your use case!

