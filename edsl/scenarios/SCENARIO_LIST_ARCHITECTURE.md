# ScenarioList Version Control System - Architecture Specification

## Overview

The ScenarioList implements a **git-like version control system** for tabular data using three core patterns:

1. **Event Sourcing** - All mutations are captured as immutable events
2. **Columnar Storage** - Data stored by columns with UUID-based addressing for O(1) renames
3. **Immutable/Functional API** - Methods return new instances; the original is never mutated

This architecture enables:
- **Time travel**: Checkout any historical version
- **Branching**: Fork datasets and evolve them independently
- **Audit trail**: Full history of every change
- **Collaboration**: Push/pull to remote servers like git

---

## Core Components

### 1. ColumnStore (`store/column_store.py`)

The underlying storage engine using **column-oriented storage with ID-based addressing**:

```python
# Internal Structure:
_cols: Dict[col_id → List[values]]     # Actual data by UUID
_col_names: Dict[col_name → col_id]    # Name→ID mapping (O(1) rename)
_row_ids: List[row_uuid]               # Row identity tracking
_nrows: int                            # Row count
_meta: Dict                            # Metadata (codebook, id, etc.)
_version: int                          # Current version number
_log: EventLog                         # Attached event history
_branch: str                           # Current branch name ("main" by default)
```

**Key Design Decisions:**
- **O(1) Column Renames** - Just update `_col_names` mapping; data stays in place
- **Row Identity** - `_row_ids` preserves identity across operations
- **Indirection** - All column access goes through name→ID lookup

### 2. EventLog (`store/event_log.py`)

A **git-like event log** with branching, commits, and fork-on-write:

```python
# Structure:
branches: Dict[branch_name → BranchMeta]
commits: Dict[branch_name → Dict[version → Event]]
applied_ids: Set[event_id]  # Deduplication tracking

# BranchMeta:
parent: Optional[str]       # Parent branch (None for root)
fork_point: Optional[int]   # Version where forked
head: int                   # Current head version
```

### 3. Events (`store/events.py`)

**Immutable frozen dataclasses** representing operations:

```python
@dataclass(frozen=True)
class AppendRow(SerializableEvent):
    event_type = "append_row"
    version: int
    row: Dict[str, Any]
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        # Mutate the store
        ...
```

### 4. VersionedMixin (`store/versioned_mixin.py`)

Mixin providing **git-like API** to ScenarioList:

```python
class ScenarioList(VersionedMixin, ...):
    # Inherits: _apply, checkout, snapshot, push, pull, clone, log, status, etc.
```

---

## The Immutability Model

**All mutating operations return NEW instances:**

```python
# Example: Appending data
sl = ScenarioList([{"name": "Alice"}])
sl2 = sl.append({"name": "Bob"})     # sl is unchanged!
sl3 = sl2.filter("name == 'Bob'")    # sl2 is unchanged!

print(len(sl))   # 1 - original untouched
print(len(sl2))  # 2 - has both rows
print(len(sl3))  # 1 - filtered result

# Under the hood:
def append(self, value) -> "ScenarioList":
    event = AppendRow(version=self.version + 1, row=dict(value))
    return self._apply(event)  # Returns NEW instance
```

**Immutability Enforcement:**
- `__setattr__` raises `ImmutabilityError` for unauthorized mutations
- Only allowed attrs: caches, managers, internal tracking state

---

## Event-Based Methods Reference

All methods that modify data create Events and return new instances via `_apply()`:

### Row Operations

| Method | Event | Description |
|--------|-------|-------------|
| `append(row)` | `AppendRow` | Add a single row |
| `filter(expr)` | `FilterRows` | Keep rows matching expression |
| `sample(n, seed)` | `SampleRows` | Random sample of n rows |
| `shuffle(seed)` | `ShuffleRows` | Randomize row order |
| `order_by(*fields, reverse)` | `SortRows` | Sort by one or more columns |
| `expand(*fields, number_field)` | `ExpandRows` | Unpack list columns into rows |
| `unique()` | `DeduplicateRows` | Remove duplicate rows |
| `tack_on(replacements, index)` | `TackOnRow` | Duplicate row with changes |

### Column Operations

| Method | Event | Description |
|--------|-------|-------------|
| `select(*fields)` | `SelectColumns` | Keep only specified columns |
| `drop(*fields)` | `DropColumns` | Remove columns |
| `rename(dict)` | `RenameColumn` | Rename columns (O(1)) |
| `add_list(name, values)` | `AddColumn` | Add column from list |
| `add_value(name, value)` | `AddColumn` | Add constant column |
| `give_valid_names()` | `RenameColumnsToValid` | Make column names valid identifiers |

### Value Operations

| Method | Event | Description |
|--------|-------|-------------|
| `string_cat(key, addend, position)` | `ConcatToColumn` | Concatenate string to column |
| `uniquify(field)` | `UniquifyColumn` | Make values unique with suffixes |
| `numberify()` | `NumberifyColumns` | Convert strings to numbers |
| `transform_column(col, op, **kwargs)` | `TransformColumn` | Apply built-in transformation |
| `transform_expr(col, expr)` | `TransformColumn` | Apply arithmetic expression |

### Reshape Operations

| Method | Event | Description |
|--------|-------|-------------|
| `group_by_agg(id_vars, aggregations)` | `GroupByAggregate` | Group and aggregate |
| `zip(field_a, field_b, new_name)` | `ZipColumns` | Zip two columns into dict |

### Version Control Operations (from VersionedMixin)

| Method | Description |
|--------|-------------|
| `checkout(version)` | View historical state |
| `snapshot(name)` | Fork at current state |
| `log()` | Print commit history |
| `history(n)` | Get events as list |
| `diff(since)` | Events since version |
| `status()` | Git-like status report |
| `push(remote, ...)` | Push to server |
| `pull(remote, ...)` | Pull from server |
| `clone(store_id, ...)` | Clone from server |

---

## Detailed Examples

### Example 1: Basic Mutations and Immutability

```python
from edsl.scenarios import ScenarioList, Scenario

# Create initial data
sl = ScenarioList([
    {"name": "Alice", "age": 30},
    {"name": "Bob", "age": 25}
])
print(sl.version)  # 0

# Append returns NEW instance
sl2 = sl.append({"name": "Charlie", "age": 35})
print(sl.version)   # 0 - unchanged
print(sl2.version)  # 1 - new version
print(len(sl))      # 2
print(len(sl2))     # 3

# Chain operations
sl3 = (sl2
    .filter("age > 25")
    .add_value("status", "active")
    .order_by("age", reverse=True))

print(sl3.version)  # 4 (filter=2, add_value=3, order_by=4)
print(list(sl3))    # Charlie (35), Alice (30)
```

### Example 2: Time Travel with Checkout

```python
# Build up history
sl = ScenarioList([{"x": 1}])
sl = sl.append({"x": 2})    # v1
sl = sl.append({"x": 3})    # v2
sl = sl.append({"x": 4})    # v3

print(sl.version)           # 3
print([s["x"] for s in sl]) # [1, 2, 3, 4]

# Time travel to version 1
old = sl.checkout(1)
print(old.version)           # 1
print([s["x"] for s in old]) # [1, 2]

# Original unchanged
print(sl.version)            # 3
print([s["x"] for s in sl])  # [1, 2, 3, 4]
```

### Example 3: Branching with Snapshot

```python
# Main branch
sl = ScenarioList([{"item": "apple", "price": 1.00}])
sl = sl.append({"item": "banana", "price": 0.50})

# Fork for "sale" experiment
sale_branch = sl.snapshot("sale-prices")
sale_branch = sale_branch.transform_column("price", "multiply", factor=0.8)

# Fork for "premium" experiment
premium_branch = sl.snapshot("premium-prices")
premium_branch = premium_branch.transform_column("price", "multiply", factor=1.5)

# All three exist independently
print(sl.branch)              # main
print(sale_branch.branch)     # sale-prices
print(premium_branch.branch)  # premium-prices

# View branch structure
sl.branch_graph()
# EventLog
# └── main head=2
#     ├── sale-prices head=3
#     └── premium-prices head=3
```

### Example 4: Event History and Audit Trail

```python
sl = ScenarioList([{"name": "test"}])
sl = sl.add_value("count", 0)
sl = sl.transform_column("count", "add", amount=10)
sl = sl.rename({"count": "total"})

# View history
sl.log()
# ╭─────────── main (head=3) ───────────╮
# │  ● v3  rename_column  old=count, new=total
# │  │
# │  ● v2  transform_column  column=count, operation=add
# │  │
# │  ● v1  add_column  column_name=count
# ╰─────────────────────────────────────╯

# Get events programmatically
events = sl.history()
for e in events:
    print(f"v{e.version}: {e.event_type}")
# v3: rename_column
# v2: transform_column
# v1: add_column
```

### Example 5: Remote Sync (Push/Pull/Clone)

```python
# Create and push
sl = ScenarioList([
    {"product": "Widget", "sales": 100},
    {"product": "Gadget", "sales": 250}
])

# First push requires metadata
sl.push(
    title="Q4 Sales Data",
    description="Sales figures for Q4 2024",
    alias="q4-sales",
    visibility="private"
)

# Make local changes
sl2 = sl.append({"product": "Gizmo", "sales": 175})
sl2.push()  # Pushes only the new event

# Someone else clones
other_sl = ScenarioList.clone("q4-sales")
print(len(other_sl))  # 3

# They make changes and push
other_sl = other_sl.transform_column("sales", "multiply", factor=1.1)
other_sl.push()

# You pull their changes
sl3 = sl2.pull()
# Pulling from q4-sales...
#   ↓ v4  transform_column  column=sales, operation=multiply
# Updated: v3 → v4
```

### Example 6: Filtering with Field Expressions

```python
from edsl.store.filters import Field

sl = ScenarioList([
    {"name": "Alice", "age": 30, "city": "NYC"},
    {"name": "Bob", "age": 25, "city": "LA"},
    {"name": "Charlie", "age": 35, "city": "NYC"}
])

# Using Field expressions (recommended)
nyc_people = sl.filter(Field("city") == "NYC")
adults = sl.filter(Field("age") >= 30)
young_la = sl.filter((Field("age") < 30) & (Field("city") == "LA"))

# Equivalent string syntax (legacy)
nyc_people = sl.filter("city == 'NYC'")
adults = sl.filter("age >= 30")
```

### Example 7: Column Transformations

```python
sl = ScenarioList([
    {"name": "alice smith", "price": 10.567, "quantity": "5"}
])

# String operations
sl2 = sl.transform_column("name", "upper")
# [{"name": "ALICE SMITH", ...}]

# Math operations
sl3 = sl.transform_column("price", "round", digits=2)
# [{"price": 10.57, ...}]

# Create new column
sl4 = sl.transform_column("price", "multiply", new_column="total", factor=2)
# [{"price": 10.567, "total": 21.134, ...}]

# Expression-based transform
sl5 = sl.transform_expr("price", "x * 1.1 + 5")  # 10% markup + $5 fee
# [{"price": 16.6237, ...}]

# Convert types
sl6 = sl.numberify()  # Converts "5" → 5
# [{"quantity": 5, ...}]
```

### Example 8: Grouping and Aggregation

```python
sl = ScenarioList([
    {"category": "A", "region": "East", "value": 10},
    {"category": "A", "region": "West", "value": 20},
    {"category": "A", "region": "East", "value": 15},
    {"category": "B", "region": "East", "value": 5},
])

# Group by category, sum values
result = sl.group_by_agg(
    id_vars=["category"],
    aggregations={"value": "sum"}
)
# [{"category": "A", "value": 45}, {"category": "B", "value": 5}]

# Group by multiple columns
result2 = sl.group_by_agg(
    id_vars=["category", "region"],
    aggregations={"value": "mean"}
)
# [{"category": "A", "region": "East", "value": 12.5}, ...]

# Supported aggregations: sum, mean, min, max, count, first, last, list, concat
```

### Example 9: Expanding List Columns

```python
sl = ScenarioList([
    {"id": 1, "tags": ["python", "data"]},
    {"id": 2, "tags": ["javascript", "web", "frontend"]}
])

# Expand single column
expanded = sl.expand("tags")
# [{"id": 1, "tags": "python"},
#  {"id": 1, "tags": "data"},
#  {"id": 2, "tags": "javascript"},
#  {"id": 2, "tags": "web"},
#  {"id": 2, "tags": "frontend"}]

# With index tracking
expanded = sl.expand("tags", number_field=True)
# [{"id": 1, "tags": "python", "tags_number": 1}, ...]

# Multi-column aligned expansion
sl2 = ScenarioList([
    {"id": 1, "keys": ["a", "b"], "vals": [1, 2]}
])
result = sl2.expand("keys", "vals")
# [{"id": 1, "keys": "a", "vals": 1},
#  {"id": 1, "keys": "b", "vals": 2}]
```

### Example 10: Status and Sync Information

```python
sl = ScenarioList([{"x": 1}])
sl = sl.append({"x": 2})
sl.push(title="Test", description="Test data")
sl = sl.append({"x": 3})  # Local change

# Check status (like `git status`)
status = sl.status()
# ╭─────────── Status ───────────╮
# │ On branch: main              │
# │ Store ID: abc123...          │
# │                              │
# │ ↑ Your branch is ahead of    │
# │   'origin' by 1 commit.      │
# │   (use "obj.push()" to       │
# │    publish your local        │
# │    commits)                  │
# │                              │
# │ Local version:  3            │
# │ Server version: 2            │
# ╰──────────────────────────────╯

# Access status programmatically
print(status.local_version)   # 3
print(status.server_version)  # 2
print(status.ahead)           # 1
print(status.is_synced)       # False
```

---

## How Events Flow Through the System

```
User calls: sl.filter("age > 18")
                    │
                    ▼
    ┌─────────────────────────────────┐
    │ 1. Create FilterRows Event      │
    │    version=self.version + 1     │
    │    expression={"op": ">", ...}  │
    │    event_id=uuid4()             │
    └─────────────────────────────────┘
                    │
                    ▼
    ┌─────────────────────────────────┐
    │ 2. _apply(event):               │
    │    a. Copy current store state  │
    │    b. event.execute(new_store)  │
    │    c. log.commit(branch, event) │
    │    d. Return NEW ScenarioList   │
    └─────────────────────────────────┘
                    │
                    ▼
    ┌─────────────────────────────────┐
    │ 3. EventLog records:            │
    │    commits["main"][2] = event   │
    │    branches["main"].head = 2    │
    └─────────────────────────────────┘
                    │
                    ▼
    New ScenarioList returned (version=2)
    Original ScenarioList unchanged (version=1)
```

---

## Key Design Properties

1. **O(1) Column Renames** - Just update name→ID mapping
2. **Event Deduplication** - `event_id` tracking prevents double-application
3. **Cheap Branching** - Branches share EventLog, only store divergent events
4. **Full Audit Trail** - Every change recorded with type, version, parameters
5. **Cross-Language Compat** - Seeded RNG for shuffle/sample reproduces in TypeScript
6. **Lazy Materialization** - `_ScenarioDataView` converts columnar→Scenario on-demand

---

## Event Categories Reference

### Row Operations
- `AppendRow` / `AppendRows` - Add rows
- `DeleteRows` - Remove rows by index or ID
- `FilterRows` - Keep rows matching expression
- `SampleRows` - Random sample
- `ShuffleRows` - Randomize order
- `SortRows` - Sort by columns
- `ExpandRows` - Unpack list columns
- `DeduplicateRows` - Remove duplicates
- `TackOnRow` - Duplicate with modifications
- `ChunkRows` - Split text into chunks

### Column Operations
- `AddColumn` - Add new column
- `DropColumns` - Remove columns
- `SelectColumns` - Keep only specified columns
- `RenameColumn` - Rename single column (O(1))
- `RenameColumnsToValid` - Make names valid identifiers
- `ReorderColumns` - Change column order
- `UniquifyColumn` - Make values unique with suffixes

### Value Operations
- `SetValue` - Set single cell
- `FillNA` - Fill null values
- `ReplaceValues` - Replace specific values
- `TransformColumn` - Apply transformation
- `NumberifyColumns` - Convert strings to numbers
- `ConcatToColumn` - Append/prepend string

### Reshape Operations
- `PivotRows` - Long to wide format
- `UnpivotRows` - Wide to long format
- `CollapseRows` - Group and collect values
- `GroupByAggregate` - Group and aggregate
- `ZipColumns` - Combine two columns into dict

### Metadata Operations
- `MetaSet` - Set single metadata key
- `MetaUpdate` - Update metadata dict

### Special Operations
- `VibesSnapshot` - Wholesale state replacement (AI operations)
