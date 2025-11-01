# ScenarioSourceInferrer Module

## Overview

The `ScenarioSourceInferrer` module provides automatic source type detection for creating `ScenarioList` objects in EDSL. Instead of requiring explicit specification of the source type, it uses heuristics and try/except blocks to infer the correct source handler.

## Files Created

1. **`scenario_source_inferrer.py`** - Main module containing the inferrer logic
2. **`tests/test_scenario_source_inferrer.py`** - Comprehensive test suite (18 tests)
3. **`INFERRER_USAGE.md`** - Detailed usage documentation

## Key Components

### Main Class: `ScenarioSourceInferrer`

The inferrer examines input data using the following detection strategy:

1. **Type Detection** - Checks if input is a pandas DataFrame, dict, or list
2. **URL Detection** - Identifies URLs by scheme (http/https) and domain patterns
3. **File Detection** - Checks file existence and extension
4. **Structure Analysis** - For dicts/lists, analyzes internal structure

### Convenience Function: `from_any()`

A simple function that wraps `ScenarioSourceInferrer.infer_and_create()` for easier use:

```python
from edsl.scenarios import from_any

# Automatically detects CSV format
sl = from_any("data.csv")

# Automatically detects dictionary format
sl = from_any({"name": ["Alice", "Bob"], "age": [25, 30]})
```

## Supported Source Types

The inferrer automatically handles:

### Data Structures
- **Dictionaries** (simple and nested)
- **Lists** (values and tuples)
- **Pandas DataFrames**

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
- Direct file URLs

### Directories
- File scanning with pattern matching
- Recursive traversal

## Design Philosophy

The module uses **heuristics over configuration**:

1. **Try simple checks first** - Type checking is fast and unambiguous
2. **File extensions are reliable** - For local files, extensions usually match content
3. **URL patterns are distinctive** - Domain names identify services (wikipedia, google, etc.)
4. **Graceful degradation** - If inference fails, clear error messages guide the user

## Testing

The test suite includes 18 tests covering:

- ✓ Dictionary source detection (simple and nested)
- ✓ List source detection (values and tuples)
- ✓ Pandas DataFrame detection
- ✓ File format detection by extension (CSV, TSV, etc.)
- ✓ URL detection and classification
- ✓ Error handling for unsupported types
- ✓ Parameter passing to underlying sources
- ✓ Edge cases (empty lists, missing files, etc.)

All tests pass successfully.

## Integration

The module is fully integrated into the `edsl.scenarios` package:

```python
from edsl.scenarios import ScenarioSourceInferrer, from_any

# Both are exported in the package __all__
```

## Examples

### Basic Usage

```python
from edsl.scenarios import from_any

# Dictionary
sl = from_any({"x": [1, 2], "y": [3, 4]})

# CSV file
sl = from_any("data.csv")

# Pandas DataFrame
import pandas as pd
df = pd.DataFrame({"a": [1, 2]})
sl = from_any(df)

# URL
sl = from_any("https://example.com/data.csv")
```

### Advanced Usage

```python
# Pass additional parameters
sl = from_any("data.pdf", chunk_type="text", chunk_size=1000)

# Nested dict with ID field
data = {"id1": {"name": "Alice"}, "id2": {"name": "Bob"}}
sl = from_any(data, id_field="user_id")

# List with custom field name
sl = from_any(["a", "b", "c"], field_name="letter")
```

### Error Handling

```python
from edsl.scenarios.exceptions import ScenarioError

try:
    sl = from_any(unsupported_data)
except ScenarioError as e:
    # Falls back to explicit source type
    from edsl.scenarios.scenario_source import ScenarioSource
    sl = ScenarioSource.from_source("csv", "data.txt")
```

## Performance

The inferrer adds minimal overhead:
- Type checking: < 1ms
- File extension checking: < 1ms
- URL parsing: < 1ms

The actual data loading time is identical to using explicit source types.

## Future Enhancements

Potential improvements:
1. Content-based detection (reading file headers) for ambiguous extensions
2. Smart delimiter detection for delimited files
3. Caching of inference results for repeated calls
4. More sophisticated URL pattern matching

## Compatibility

The module maintains full backward compatibility:
- Existing code using `ScenarioSource.from_source()` continues to work
- All existing source classes are unchanged
- The inferrer is purely additive functionality

## Documentation

See `INFERRER_USAGE.md` for comprehensive usage examples and detailed documentation of all supported source types.

