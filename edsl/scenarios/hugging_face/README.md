# Hugging Face Integration for EDSL ScenarioList

This module provides integration with Hugging Face datasets, allowing you to easily load datasets from the Hugging Face Hub into EDSL ScenarioList objects.

## Installation

To use this functionality, you need to install the `datasets` library:

```bash
pip install datasets
```

## Usage

### Basic Usage

```python
from edsl.scenarios import ScenarioList

# Load a simple dataset
scenarios = ScenarioList.from_hugging_face("squad")
print(f"Loaded {len(scenarios)} scenarios")
```

### Datasets with Multiple Configurations

Some datasets (like GLUE) have multiple configurations. You must specify which one to load:

```python
# This will raise an error because GLUE has multiple configs
try:
    scenarios = ScenarioList.from_hugging_face("glue")
except ValueError as e:
    print(f"Error: {e}")

# Specify a configuration
scenarios = ScenarioList.from_hugging_face("glue", config_name="cola")
```

### Alternative Import

You can also import the function directly:

```python
from edsl.scenarios.hugging_face import from_hugging_face

scenarios = from_hugging_face("squad")
```

## Handling Multiple Splits

When a dataset has multiple splits (train, validation, test), the loader will:

1. Use the 'train' split if available
2. Otherwise, use the first available split and issue a warning

## Error Handling

The function handles several error cases:

- **Missing datasets library**: Raises `ImportError` with installation instructions
- **Multiple configurations**: Raises `ValueError` listing available configurations
- **Invalid configuration**: Raises `ValueError` if the specified config doesn't exist
- **Dataset loading failures**: Raises `ValueError` with the underlying error

## Examples

### Loading SQuAD Dataset

```python
from edsl.scenarios import ScenarioList

# Load the SQuAD dataset
scenarios = ScenarioList.from_hugging_face("squad")

# Access the data
print(scenarios[0].keys())  # Show available columns
print(scenarios[0]['question'])  # Access a specific question
```

### Loading GLUE Dataset

```python
from edsl.scenarios import ScenarioList

# Load CoLA task from GLUE
scenarios = ScenarioList.from_hugging_face("glue", config_name="cola")

# Check the data structure
print(scenarios[0].keys())  # ['sentence', 'label']
print(scenarios[0]['sentence'])  # Access the sentence
```

## Implementation Details

- The function loads the entire dataset into memory as a pandas DataFrame
- Data is converted to a list of dictionaries and then to ScenarioList using the existing `from_list_of_dicts` method
- Multiple splits are handled automatically, with preference for the 'train' split
- Configuration validation is performed before loading the dataset

## Testing

Run the test suite:

```bash
pytest edsl/scenarios/hugging_face/test_hugging_face_loader.py
```

Or run the example usage script:

```bash
python edsl/scenarios/hugging_face/example_usage.py
```