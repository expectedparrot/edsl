# ScenarioSourceInferrer Usage Guide

The `ScenarioSourceInferrer` module provides automatic source type detection for creating `ScenarioList` objects. Instead of explicitly specifying the source type, you can pass your data directly and let the inferrer determine the appropriate handler.

## Quick Start

```python
from edsl.scenarios import from_any

# From a dictionary
sl = from_any({"name": ["Alice", "Bob"], "age": [25, 30]})

# From a CSV file
sl = from_any("data.csv")

# From a pandas DataFrame
import pandas as pd
df = pd.DataFrame({"x": [1, 2, 3]})
sl = from_any(df)

# From a URL
sl = from_any("https://example.com/data.csv")
```

## Supported Source Types

### 1. Dictionaries

**Simple dictionary** (field names to lists):
```python
data = {"product": ["coffee", "tea"], "price": [4.99, 3.99]}
sl = from_any(data)
```

**Nested dictionary** (IDs to record dictionaries):
```python
data = {
    "item1": {"name": "coffee", "price": 4.99},
    "item2": {"name": "tea", "price": 3.99}
}
sl = from_any(data, id_field="item_id")
```

### 2. Lists

**Simple list**:
```python
values = ["apple", "banana", "cherry"]
sl = from_any(values, field_name="fruit")
```

**List of tuples**:
```python
data = [("Alice", 25), ("Bob", 30)]
sl = from_any(data, field_names=["name", "age"])
```

### 3. Pandas DataFrames

```python
import pandas as pd
df = pd.DataFrame({"col1": [1, 2], "col2": [3, 4]})
sl = from_any(df)
```

### 4. File Paths

The inferrer automatically detects file types by extension:

- **CSV**: `.csv`
- **TSV**: `.tsv`
- **Excel**: `.xls`, `.xlsx`, `.xlsm`
- **Parquet**: `.parquet`
- **PDF**: `.pdf`
- **SQLite**: `.db`, `.sqlite`, `.sqlite3`
- **Stata**: `.dta`
- **LaTeX**: `.tex`, `.latex`
- **Text files**: `.txt`, `.dat`

```python
# CSV file
sl = from_any("data.csv")

# Excel file with specific sheet
sl = from_any("data.xlsx", sheet_name="Sheet1")

# PDF file
sl = from_any("document.pdf", chunk_type="page")

# SQLite database
sl = from_any("database.db", table="users")
```

### 5. URLs

The inferrer detects URL types based on domain and file extension:

```python
# Wikipedia table
sl = from_any("https://en.wikipedia.org/wiki/Example", table_index=0)

# Google Sheets
sl = from_any("https://docs.google.com/spreadsheets/d/abc123")

# Google Docs
sl = from_any("https://docs.google.com/document/d/abc123")

# CSV from URL
sl = from_any("https://example.com/data.csv")
```

### 6. Directories

```python
# All files in directory
sl = from_any("path/to/directory")

# With pattern matching
sl = from_any("path/to/directory", pattern="*.txt", recursive=True)
```

## Advanced Usage

### Using ScenarioSourceInferrer directly

```python
from edsl.scenarios import ScenarioSourceInferrer

sl = ScenarioSourceInferrer.infer_and_create(
    source="data.csv",
    delimiter=",",
    encoding="utf-8"
)
```

### Passing additional parameters

Most parameters are passed through to the underlying source handler:

```python
# PDF with custom chunking
sl = from_any("document.pdf", chunk_type="text", chunk_size=1000)

# Excel with specific sheet
sl = from_any("data.xlsx", sheet_name="Results")

# CSV with custom delimiter
sl = from_any("data.txt", delimiter="\t")
```

## How It Works

The inferrer uses a series of heuristics to determine the source type:

1. **Type checking**: Is it a pandas DataFrame, dict, or list?
2. **URL detection**: Does it start with `http://` or `https://`?
3. **File existence**: Does the path exist on the filesystem?
4. **Extension matching**: What file extension does it have?
5. **Content inspection**: For dicts and lists, what structure do they have?

If the inferrer cannot determine the source type, it raises a `ScenarioError` with helpful information about supported formats.

## Error Handling

The inferrer uses try/except blocks internally to gracefully handle edge cases:

```python
try:
    sl = from_any("unknown_file.xyz")
except ScenarioError as e:
    print(f"Could not infer source type: {e}")
    # Fall back to explicit source type specification
    sl = ScenarioSource.from_source("csv", "unknown_file.xyz")
```

## When to Use Explicit Source Types

While the inferrer handles most common cases, you may want to use explicit source type specification when:

- The file extension doesn't match the actual format
- You need more control over the source creation process
- The heuristics might be ambiguous for your use case

In these cases, use `ScenarioSource.from_source()` directly:

```python
from edsl.scenarios.scenario_source import ScenarioSource

sl = ScenarioSource.from_source(
    "csv",
    "data_with_wrong_extension.txt",
    delimiter=","
)
```

## Performance Notes

The inferrer adds minimal overhead:
- Type checking is fast (milliseconds)
- File extension checking is instantaneous
- No file I/O happens during inference, only during actual data loading

The performance of creating the ScenarioList is identical whether you use the inferrer or specify the source type explicitly.

