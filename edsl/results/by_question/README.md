# ByQuestionAnswers: Answer Distribution Analysis

This module provides tools for analyzing and visualizing the distribution of answers for individual questions across survey responses.

## Overview

`ByQuestionAnswers` is an abstract base class that provides a framework for analyzing how respondents answered specific questions. Different question types have specialized analyzer classes that provide appropriate statistical summaries and terminal-based visualizations using `termplotlib`.

## Features

- **Question Type-Specific Analysis**: Automatically selects the appropriate analyzer based on question type
- **Statistical Summaries**: Computes relevant statistics for each question type (frequencies, means, distributions, etc.)
- **Terminal Visualizations**: Creates ASCII charts and histograms that display in the terminal
- **Easy Integration**: Works directly with `Results` objects from EDSL surveys

## Supported Question Types

| Question Type | Analyzer Class | Visualization |
|--------------|----------------|---------------|
| `multiple_choice` | `MultipleChoiceAnswers` | Horizontal bar chart of frequencies |
| `checkbox` | `CheckboxAnswers` | Bar chart of selection frequencies |
| `numerical` | `NumericalAnswers` | Histogram with statistics |
| `linear_scale` | `LinearScaleAnswers` | Bar chart with scale distribution |
| `free_text` | `FreeTextAnswers` | Response length histogram |
| `yes_no` | `YesNoAnswers` | Binary bar chart |
| `likert_five` | `LikertFiveAnswers` | 5-point scale distribution |
| `rank` | `RankAnswers` | Average ranking bar chart |
| Other types | `DefaultAnswers` | Frequency bar chart |

## Installation

Ensure `termplotlib` is installed:

```bash
pip install termplotlib
```

## Usage

### Basic Usage with Results Object

```python
from edsl.results import Results, ByQuestionAnswers

# Get your results
results = Results.example()

# Analyze a specific question
analyzer = ByQuestionAnswers.from_results(results, 'question_name')

# Show summary and visualization
analyzer.show()
```

### Direct Creation with Question and Answers

```python
from edsl.questions import QuestionMultipleChoice
from edsl.results import ByQuestionAnswers

# Create a question
q = QuestionMultipleChoice(
    question_name="favorite_color",
    question_text="What is your favorite color?",
    question_options=["Red", "Blue", "Green", "Yellow"]
)

# Your answer data
answers = ["Red", "Blue", "Red", "Green", "Red", "Blue"]

# Create analyzer
analyzer = ByQuestionAnswers.create(q, answers)

# Get summary statistics
print(analyzer.summary())

# Get visualization
print(analyzer.visualize())

# Or show both
analyzer.show()
```

## Examples by Question Type

### Multiple Choice

```python
from edsl.questions import QuestionMultipleChoice
from edsl.results import ByQuestionAnswers

q = QuestionMultipleChoice(
    question_name="transport",
    question_text="Preferred mode of transport?",
    question_options=["Car", "Bus", "Train", "Bike"]
)

answers = ["Car", "Bus", "Car", "Train", "Car", "Bike", "Bus"]
analyzer = ByQuestionAnswers.create(q, answers)
analyzer.show()
```

Output:
```
Question: Preferred mode of transport?
Type: Multiple Choice
Total responses: 7

Distribution:
  Car: 3 (42.9%)
  Bus: 2 (28.6%)
  Train: 1 (14.3%)
  Bike: 1 (14.3%)

Car  ▇▇▇▇▇▇▇▇▇▇▇▇▇▇ 3
Bus  ▇▇▇▇▇▇▇▇▇ 2
Train▇▇▇▇ 1
Bike ▇▇▇▇ 1
```

### Numerical

```python
from edsl.questions import QuestionNumerical
from edsl.results import ByQuestionAnswers
import numpy as np

q = QuestionNumerical(
    question_name="age",
    question_text="What is your age?"
)

# Generate some sample data
np.random.seed(42)
answers = list(np.random.normal(35, 10, 50).astype(int))

analyzer = ByQuestionAnswers.create(q, answers)
analyzer.show()
```

Output:
```
Question: What is your age?
Type: Numerical
Total responses: 50

Statistics:
  Mean: 35.24
  Median: 35.00
  Std Dev: 9.87
  Min: 15.00
  Max: 57.00

[Histogram visualization]
```

### Linear Scale

```python
from edsl.questions import QuestionLinearScale
from edsl.results import ByQuestionAnswers

q = QuestionLinearScale(
    question_name="satisfaction",
    question_text="How satisfied are you?",
    question_options=[1, 2, 3, 4, 5],
    option_labels={1: "Very Unsatisfied", 5: "Very Satisfied"}
)

answers = [5, 4, 5, 3, 4, 5, 5, 4, 3, 5]
analyzer = ByQuestionAnswers.create(q, answers)
analyzer.show()
```

### Checkbox (Multiple Selections)

```python
from edsl.questions import QuestionCheckBox
from edsl.results import ByQuestionAnswers

q = QuestionCheckBox(
    question_name="interests",
    question_text="What are your interests?",
    question_options=["Sports", "Music", "Reading", "Travel"]
)

answers = [
    ["Sports", "Music"],
    ["Reading", "Travel"],
    ["Sports", "Travel"],
    ["Music"]
]

analyzer = ByQuestionAnswers.create(q, answers)
analyzer.show()
```

Output:
```
Question: What are your interests?
Type: Checkbox (multiple selections)
Total respondents: 4
Total selections: 7
Avg selections per respondent: 1.8

Selection frequency:
  Sports: 2 (50.0% of respondents)
  Music: 2 (50.0% of respondents)
  Travel: 2 (50.0% of respondents)
  Reading: 1 (25.0% of respondents)
```

### Rank

```python
from edsl.questions import QuestionRank
from edsl.results import ByQuestionAnswers

q = QuestionRank(
    question_name="priorities",
    question_text="Rank these factors",
    question_options=["Cost", "Quality", "Speed", "Support"]
)

answers = [
    ["Quality", "Cost", "Speed", "Support"],
    ["Cost", "Speed", "Quality", "Support"],
    ["Quality", "Support", "Cost", "Speed"],
]

analyzer = ByQuestionAnswers.create(q, answers)
analyzer.show()
```

Output:
```
Question: Rank these factors
Type: Rank
Total responses: 3

Average Rankings (lower is better):
  Quality: 1.67
  Cost: 2.00
  Speed: 2.67
  Support: 3.67
```

## API Reference

### `ByQuestionAnswers` (Abstract Base Class)

#### Class Methods

- `from_results(results, question_name)`: Create analyzer from Results object
- `create(question, answers)`: Factory method to create appropriate subclass

#### Instance Methods

- `summary()`: Return formatted string with summary statistics
- `visualize()`: Return terminal visualization as string
- `show()`: Print both summary and visualization

### Concrete Analyzer Classes

All concrete classes inherit from `ByQuestionAnswers` and implement:
- `summary()`: Question type-specific summary
- `visualize()`: Question type-specific visualization

## Architecture

The module uses the Strategy pattern with an Abstract Base Class:

```
ByQuestionAnswers (ABC)
├── MultipleChoiceAnswers
├── CheckboxAnswers
├── NumericalAnswers
├── LinearScaleAnswers
├── FreeTextAnswers
├── YesNoAnswers
├── LikertFiveAnswers
├── RankAnswers
└── DefaultAnswers (fallback)
```

The factory method `create()` automatically selects the appropriate analyzer class based on the question's `question_type` attribute.

## Testing

Run the test suite:

```bash
cd edsl/results/by_question
python test_by_question_answers.py
```

## Examples

See `by_question_answers_example.py` for comprehensive examples of all question types.

```bash
cd edsl/results/by_question
python by_question_answers_example.py
```

## Notes

- Automatically filters out `None` values from answers
- All visualizations use `termplotlib` for terminal-friendly output
- The `show()` method prints output directly; use `summary()` and `visualize()` if you need the strings
- For question types without specific implementations, `DefaultAnswers` provides basic frequency analysis

## Future Enhancements

Possible future additions:
- Additional statistical tests (chi-square, t-tests, etc.)
- Export visualizations to HTML/PNG
- Comparative analysis across multiple questions
- Time-series analysis for repeated surveys
- Outlier detection for numerical data
