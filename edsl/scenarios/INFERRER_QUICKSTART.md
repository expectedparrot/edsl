# ScenarioSourceInferrer - Quick Start

## TL;DR

Use `from_any()` to automatically create ScenarioLists without specifying source types:

```python
from edsl.scenarios import from_any

sl = from_any(your_data)  # Works with most data types!
```

## Common Use Cases

### From Dictionary
```python
sl = from_any({"name": ["Alice", "Bob"], "age": [25, 30]})
```

### From CSV File
```python
sl = from_any("data.csv")
```

### From Pandas DataFrame
```python
import pandas as pd
df = pd.DataFrame({"x": [1, 2, 3]})
sl = from_any(df)
```

### From List
```python
sl = from_any(["apple", "banana"], field_name="fruit")
```

### From URL
```python
sl = from_any("https://example.com/data.csv")
```

### From Excel
```python
sl = from_any("data.xlsx", sheet_name="Sheet1")
```

## What It Does

The inferrer automatically:
1. Detects the type of your input data
2. Chooses the right source handler
3. Creates a ScenarioList

## What It Supports

✓ Dictionaries (simple & nested)  
✓ Lists & tuples  
✓ Pandas DataFrames  
✓ CSV, TSV, Excel, Parquet  
✓ PDF files  
✓ SQLite databases  
✓ URLs (CSV, Wikipedia, Google Sheets, etc.)  
✓ Directories  

## When It Can't Infer

```python
# For ambiguous cases, use explicit source type:
from edsl.scenarios.scenario_source import ScenarioSource

sl = ScenarioSource.from_source("csv", "data_file.txt")
```

## More Info

- See `INFERRER_USAGE.md` for detailed examples
- See `INFERRER_README.md` for technical details
- Run tests: `pytest edsl/scenarios/tests/test_scenario_source_inferrer.py`

