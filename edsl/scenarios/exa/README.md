# EXA API Integration for EDSL

This module provides integration with the EXA API to create ScenarioLists from web search and enrichment data. EXA allows for sophisticated web searching with enrichment capabilities that can be useful for creating scenarios based on real-world data.

## Installation

To use the EXA integration, you need to install the EXA Python library:

```bash
pip install exa-py
```

## Setup

You'll need an EXA API key to use this integration. Set it as an environment variable:

```bash
export EXA_API_KEY="your-exa-api-key-here"
```

Alternatively, you can pass the API key directly to the functions.

## Usage

### Basic Search

Create a ScenarioList from a simple search query:

```python
from edsl.scenarios import ScenarioList

# Simple search
scenarios = ScenarioList.from_exa(
    query="Sales leaders at US fintech companies",
    count=50
)
```

### Search with Criteria and Enrichments

For more sophisticated searches, you can add criteria and enrichments:

```python
scenarios = ScenarioList.from_exa(
    query="Sales leaders at US fintech companies",
    criteria=[
        "currently holds a sales leadership position (e.g., head of sales, vp sales, sales director, or equivalent) at a company",
        "the company operates in the fintech industry",
        "the company is based in the united states"
    ],
    enrichments=[
        {
            "description": "Years of experience",
            "format": "number"
        },
        {
            "description": "University",
            "format": "text"
        }
    ],
    count=100
)
```

### Load from Existing Webset

You can also create a ScenarioList from an existing EXA webset:

```python
scenarios = ScenarioList.from_exa_webset("01k6m4wn1aykv03jq3p4hxs2m9")
```

### Using the Direct Functions

You can also import and use the functions directly:

```python
from edsl.scenarios.exa import from_exa, from_exa_webset

# Direct function usage
scenarios = from_exa("AI startup CTOs", count=30)
scenarios = from_exa_webset("webset-id")
```

## API Reference

### `ScenarioList.from_exa()`

Create a ScenarioList from EXA API web search and enrichment.

**Parameters:**
- `query` (str): The search query string
- `criteria` (list[str], optional): List of search criteria to refine the search
- `count` (int): Number of results to return (default: 100)
- `enrichments` (list[dict], optional): List of enrichment parameters with 'description' and 'format' keys
- `api_key` (str, optional): EXA API key (defaults to EXA_API_KEY environment variable)
- `wait_for_completion` (bool): Whether to wait for webset completion (default: True)
- `max_wait_time` (int): Maximum time to wait for completion in seconds (default: 120)
- `**kwargs`: Additional parameters to pass to EXA webset creation

**Returns:** `ScenarioList` containing the search results and enrichments

**Raises:**
- `ImportError`: If the exa-py library is not available
- `ValueError`: If the EXA API key is not provided or enrichments are malformed
- `RuntimeError`: If the EXA API call fails

### `ScenarioList.from_exa_webset()`

Create a ScenarioList from an existing EXA webset ID.

**Parameters:**
- `webset_id` (str): The ID of an existing EXA webset
- `api_key` (str, optional): EXA API key (defaults to EXA_API_KEY environment variable)

**Returns:** `ScenarioList` containing the webset results

**Raises:**
- `ImportError`: If the exa-py library is not available
- `ValueError`: If the EXA API key is not provided
- `RuntimeError`: If the webset cannot be retrieved

## Examples

See `example_usage.py` for comprehensive examples of how to use the EXA integration.

### Example: Tech Executives

```python
scenarios = ScenarioList.from_exa(
    query="CTO and engineering leaders at AI startups",
    criteria=[
        "holds a technical leadership position (CTO, VP Engineering, Head of Engineering)",
        "works at a startup company focused on artificial intelligence or machine learning",
        "company was founded after 2020"
    ],
    enrichments=[
        {
            "description": "Previous companies worked at",
            "format": "list"
        },
        {
            "description": "GitHub or personal website URL",
            "format": "url"
        },
        {
            "description": "Technical expertise areas",
            "format": "list"
        }
    ],
    count=30
)
```

### Example: Simple Industry Search

```python
scenarios = ScenarioList.from_exa(
    query="Renewable energy companies in California",
    count=20
)
```

## Data Structure

The resulting ScenarioList will contain scenarios with the following metadata fields:

- `exa_query`: The original search query
- `exa_count`: The requested number of results
- `exa_criteria`: The search criteria used (if any)
- `exa_enrichments`: The enrichment parameters used (if any)
- `exa_webset_id`: The webset ID (for webset-based results)
- `exa_results_count`: The actual number of results returned

Additional fields will depend on the EXA API response structure and enrichments requested.

## Error Handling

The module includes comprehensive error handling for common scenarios:

1. **Missing Dependencies**: Clear error messages when exa-py is not installed
2. **Missing API Key**: Helpful error messages when API key is not provided
3. **Invalid Parameters**: Validation of enrichment parameters and other inputs
4. **API Failures**: Graceful handling of EXA API errors with informative messages

## Testing

Run the tests with:

```bash
python test_exa_loader.py
```

Or use pytest:

```bash
pytest test_exa_loader.py -v
```

## Integration with EDSL Workflow

The EXA integration follows EDSL patterns and can be used seamlessly with other EDSL components:

```python
from edsl import Survey, Question
from edsl.scenarios import ScenarioList

# Create scenarios from EXA
scenarios = ScenarioList.from_exa(
    query="Marketing directors at SaaS companies",
    count=50
)

# Use in survey
q = Question.multiple_choice(
    question="What is your biggest marketing challenge?",
    options=["Lead generation", "Customer retention", "Brand awareness", "ROI measurement"]
)

survey = Survey([q])
results = survey.run(scenarios=scenarios)
```

## Asynchronous Processing

EXA websets are processed asynchronously. When you call `ScenarioList.from_exa()`, the module will:

1. Create a webset with your search parameters
2. Poll the webset status every 5 seconds until completion
3. Display progress updates when status changes or every 30 seconds
4. Extract and return the results once the webset is completed

You can control this behavior with:

- `wait_for_completion=False`: Return immediately with webset metadata (no actual results)
- `max_wait_time=60`: Set a shorter timeout (in seconds) for faster operations

Example:
```python
# Wait up to 2 minutes for results
scenarios = ScenarioList.from_exa(
    "Tech executives at AI startups",
    max_wait_time=120
)

# Don't wait, get webset ID for later retrieval
webset_info = ScenarioList.from_exa(
    "Large dataset query",
    wait_for_completion=False
)
webset_id = webset_info[0]['exa_webset_id']

# Later, retrieve results from the webset
scenarios = ScenarioList.from_exa_webset(webset_id)
```

## EXA API Resources

- [EXA API Documentation](https://docs.exa.ai/)
- [EXA Websets Guide](https://websets.exa.ai/)
- [EXA Python Library](https://github.com/exa-labs/exa-py)