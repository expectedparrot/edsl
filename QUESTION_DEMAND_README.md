# QuestionDemand - Demand Curve Question Type

## Overview

`QuestionDemand` is a new question type in EDSL that allows you to collect demand curves from language models. It asks for the quantity that would be purchased at each of several specified price points.

## Features

- ✅ Specify multiple price points (must be numbers: int or float)
- ✅ Collect quantities demanded at each price point
- ✅ Automatic validation (quantities must be non-negative)
- ✅ Formatted output as price-quantity pairs
- ✅ Full integration with EDSL framework (scenarios, agents, serialization)

## Installation

`QuestionDemand` is part of the EDSL questions module. Import it like any other question type:

```python
from edsl.questions import QuestionDemand
```

## Basic Usage

```python
from edsl.questions import QuestionDemand

# Create a demand question
q = QuestionDemand(
    question_name="coffee_demand",
    question_text="How many cups of coffee would you buy per week at each price?",
    prices=[1.0, 2.0, 3.0, 4.0, 5.0]
)

# Use with a model
from edsl import Model
result = q.by(Model()).run()

# Access the results
demand_curve = result.select("coffee_demand").to_list()[0]
```

## Parameters

### Required Parameters

- **question_name** (str): Unique identifier for the question
- **question_text** (str): The question text to present
- **prices** (List[Union[int, float]]): List of price points (at least 2, must be unique numbers)

### Optional Parameters

- **include_comment** (bool): Whether to allow comments with answers (default: True)
- **question_presentation** (str): Custom presentation template (default: uses built-in template)
- **answering_instructions** (str): Custom answering instructions (default: uses built-in template)

## Answer Format

Responses must be a list of non-negative numbers, one for each price point:

```python
{
    "answer": [10, 8, 5, 2],  # quantities at each price
    "comment": "Typical downward sloping demand"  # optional
}
```

## Validation

The question type automatically validates that:

1. The answer contains exactly the same number of quantities as there are prices
2. All quantities are non-negative (≥ 0)
3. All quantities are numeric (int or float)

## Examples

### Example 1: Coffee Demand

```python
from edsl.questions import QuestionDemand

q = QuestionDemand(
    question_name="coffee_demand",
    question_text="How many cups of coffee would you buy per week at each price?",
    prices=[1.0, 2.0, 3.0, 4.0, 5.0]
)

# Simulate an answer
answer = q._simulate_answer()
print(answer)
# {'answer': [15, 12, 8, 5, 2], 'comment': None}

# Translate to readable format
translated = q._translate_answer_code_to_answer(answer['answer'], {})
print(translated)
# [{'$1.00': 15}, {'$2.00': 12}, {'$3.00': 8}, {'$4.00': 5}, {'$5.00': 2}]
```

### Example 2: Using with Scenarios

```python
from edsl import QuestionDemand, Scenario, ScenarioList

q = QuestionDemand(
    question_name="product_demand",
    question_text="How many units of {{ product }} would you buy at each price?",
    prices=[5.0, 10.0, 15.0, 20.0]
)

scenarios = ScenarioList([
    Scenario({"product": "apples"}),
    Scenario({"product": "oranges"}),
    Scenario({"product": "bananas"})
])

# Run with scenarios
results = q.by(scenarios).run()
```

### Example 3: Using the Built-in Example

```python
from edsl.questions import QuestionDemand

# Get a pre-configured example
q = QuestionDemand.example()
print(q.question_text)
# "How many cups of coffee would you buy per week at each price?"
print(q.prices)
# [1.0, 2.0, 3.0, 4.0]
```

## Testing

Comprehensive unit tests are available in:
```
tests/questions/test_QuestionDemand.py
```

Run tests with:
```bash
python -m pytest tests/questions/test_QuestionDemand.py -v
```

## Implementation Details

### File Structure

- **Question class**: `edsl/questions/question_demand.py`
- **Templates**: `edsl/questions/templates/demand/`
  - `question_presentation.jinja`
  - `answering_instructions.jinja`
- **Tests**: `tests/questions/test_QuestionDemand.py`

### Key Components

1. **DemandResponse** (Pydantic model): Validates the structure of responses
2. **DemandResponseValidator**: Handles response fixing and validation
3. **QuestionDemand**: Main question class with all EDSL integration

### Response Validator

The validator can fix common response issues:
- String to list conversion: `"10, 8, 5, 2"` → `[10.0, 8.0, 5.0, 2.0]`
- Dictionary to list conversion: `{0: 10, 1: 8, 2: 5, 3: 2}` → `[10.0, 8.0, 5.0, 2.0]`
- Type conversion: `["10", "8", "5", "2"]` → `[10.0, 8.0, 5.0, 2.0]`

## Use Cases

- **Market research**: Understanding price sensitivity
- **Economic experiments**: Testing demand theories
- **Product pricing**: Optimal pricing analysis
- **Consumer behavior**: Studying purchasing patterns
- **A/B testing**: Comparing demand across segments

## Design Decisions

1. **Prices as numbers**: Unlike `QuestionBudget` which uses string options, `QuestionDemand` uses numeric prices to enable economic calculations
2. **Non-negative validation**: Quantities cannot be negative (you can't buy -5 apples)
3. **List format**: Answers are lists rather than dictionaries for simplicity and order preservation
4. **Similar to QuestionBudget**: Follows the same patterns as `QuestionBudget` for consistency

## Future Enhancements

Potential additions:
- Optional maximum quantity constraint
- Built-in elasticity calculations
- Visualization helpers for demand curves
- Support for discrete choice formats

## Contributing

When modifying QuestionDemand:
1. Update tests in `test_QuestionDemand.py`
2. Update templates if changing presentation
3. Run full test suite before committing
4. Update this README with any API changes
