# ScenarioList.from_source() Enhanced Implementation

## Overview

Successfully enhanced the existing `from_source()` method to automatically infer source types when called with a single argument, while maintaining full backward compatibility with explicit source type specification.

## Implementation

### Simple Logic

The method checks the number of positional arguments:

```python
@classmethod
def from_source(cls, source_type_or_data: Any, *args, **kwargs) -> "ScenarioList":
    if len(args) == 0:
        # Auto-detect mode: only one argument provided
        return ScenarioSourceInferrer.infer_and_create(
            source_type_or_data, verbose=True, **kwargs
        )
    else:
        # Explicit mode: source type + additional args
        return ScenarioSource.from_source(source_type_or_data, *args, **kwargs)
```

### Two Modes

**1. Auto-Detect Mode** (1 positional argument)
```python
ScenarioList.from_source(data)  # Infers type, prints detection
```

**2. Explicit Mode** (2+ positional arguments)
```python
ScenarioList.from_source('csv', 'data.csv')  # Original behavior
```

## Advantages Over Previous Approach

### Previous (Reserved Keyword Workaround)
```python
# Required getattr() because 'from' is a reserved keyword
sl = getattr(ScenarioList, 'from')(data)
```

### Current (Parameter Detection)
```python
# Clean, normal method syntax
sl = ScenarioList.from_source(data)
```

**Benefits:**
- ✅ No `getattr()` needed
- ✅ Natural Python syntax
- ✅ Full backward compatibility
- ✅ One method instead of multiple
- ✅ Clear intent based on arguments

## Code Changes

### Modified Files

1. **`scenario_list.py`**
   - Updated `from_source()` method signature to `source_type_or_data`
   - Added argument count detection
   - Added comprehensive docstring with both modes
   - Removed `_from_impl()` and `setattr()` workaround

2. **`scenario_source_inferrer.py`**
   - Added `verbose` parameter throughout (already done)
   - Prints detected source type when `verbose=True`

3. **`tests/test_scenario_source_inferrer.py`**
   - Updated 4 tests to use new `from_source()` syntax
   - Added test for explicit mode backward compatibility
   - Total: 24 tests, all passing

4. **Documentation**
   - `FROM_SOURCE_USAGE.md` - User guide
   - `FROM_SOURCE_IMPLEMENTATION.md` - This file

### Removed Files (No Longer Needed)

- `FROM_METHOD_USAGE.md` - Replaced by FROM_SOURCE_USAGE.md
- `FROM_METHOD_SUMMARY.md` - Replaced by this file

## Usage Examples

### Auto-Detect Mode

```python
from edsl.scenarios import ScenarioList

# Dictionary
sl = ScenarioList.from_source({'name': ['Alice'], 'age': [25]})
# Output: Detected source type: dictionary

# File (auto-detects CSV)
sl = ScenarioList.from_source('data.csv')
# Output: Detected source type: CSV file at data.csv

# DataFrame
import pandas as pd
df = pd.DataFrame({'x': [1, 2]})
sl = ScenarioList.from_source(df)
# Output: Detected source type: pandas DataFrame

# With kwargs
sl = ScenarioList.from_source('sales.xlsx', sheet_name='Q4')
# Output: Detected source type: Excel file at sales.xlsx
```

### Explicit Mode (Backward Compatible)

```python
# Original syntax still works perfectly
sl = ScenarioList.from_source('csv', 'data.csv')
sl = ScenarioList.from_source('excel', 'data.xlsx', sheet_name='Sheet1')
sl = ScenarioList.from_source('pdf', 'doc.pdf', chunk_type='page')
```

## Technical Details

### Argument Detection

The key insight: when users want auto-detection, they pass **one argument** (the data). When they specify a source type explicitly, they pass **two or more arguments** (source type + data + options).

```python
# One argument → Auto-detect
from_source(data)                    # len(args) == 0
from_source(data, key='value')       # len(args) == 0 (kwargs don't count)

# Two+ arguments → Explicit
from_source('csv', data)             # len(args) == 1 (has additional positional arg)
from_source('excel', data, 'Sheet1') # len(args) == 2
```

### Verbose Output

When in auto-detect mode, the inferrer is called with `verbose=True`, which prints messages like:
- `"Detected source type: dictionary"`
- `"Detected source type: CSV file at /path/to/data.csv"`
- `"Detected source type: pandas DataFrame"`
- etc.

When in explicit mode, no detection message is printed (original behavior).

## Testing

### Test Coverage

All 24 tests pass:
- ✅ 18 original inferrer tests
- ✅ 4 tests for auto-detect mode with different data types
- ✅ 1 test for explicit mode backward compatibility
- ✅ 1 test for verbose parameter control

### Test Results
```
============================= test session starts ==============================
edsl/scenarios/tests/test_scenario_source_inferrer.py
24 passed in 0.55s
======================================================================
```

## Backward Compatibility

### 100% Backward Compatible

All existing code continues to work:

```python
# These all still work exactly as before
ScenarioList.from_source('csv', 'data.csv')
ScenarioList.from_source('excel', 'file.xlsx', sheet_name='Sheet1')
ScenarioList.from_source('pdf', 'doc.pdf', chunk_type='page', chunk_size=1000)
ScenarioList.from_source('sqlite', 'db.sqlite3', 'users', fields=['name'])
```

### No Breaking Changes

- Existing explicit calls work identically
- No API changes to other methods
- No changes to ScenarioSource class
- All keyword arguments work the same way

## Design Rationale

### Why This Approach?

1. **Natural Syntax**: Users can write `from_source(data)` without thinking about it
2. **Discoverable**: One method instead of multiple (`from`, `from_`, `from_any`, etc.)
3. **Intuitive**: More args = more explicit, fewer args = more automatic
4. **Backward Compatible**: Zero breaking changes
5. **No Workarounds**: No `getattr()`, no reserved keyword issues

### Alternative Approaches Considered

1. **Reserved keyword (`from`)**: Requires `getattr()` - awkward syntax ❌
2. **New method (`from_`)**: Trailing underscore is ugly ❌
3. **Separate function (`from_any`)**: Adds another thing to remember ❌
4. **Parameter detection**: Clean, natural, backward compatible ✅

## Future Enhancements

Potential improvements:
1. Add a `silent` parameter to suppress detection messages
2. Add color-coded output for different source types
3. Add timing information for data loading
4. Cache inference results for repeated calls

## Comparison with Other Approaches

| Approach | Syntax | Backward Compatible | Notes |
|----------|--------|---------------------|-------|
| This Implementation | `from_source(data)` | ✅ Yes | Clean, natural |
| Reserved Keyword | `getattr(cls, 'from')(data)` | N/A | Awkward |
| Trailing Underscore | `from_(data)` | N/A | Ugly convention |
| Separate Function | `from_any(data)` | N/A | Extra to learn |

## Summary

This implementation provides the best developer experience:
- Simple, clean syntax
- Automatic detection with transparency
- Full backward compatibility
- No workarounds needed
- One method to rule them all

The user simply calls `ScenarioList.from_source(data)` and the system figures out what to do!

