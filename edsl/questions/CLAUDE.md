# Questions Module

This module provides a framework for creating, validating, and processing questions to be asked to language models.

## Architecture Overview

```
QuestionBase (ABC)
  ├── PersistenceMixin      # to_dict/from_dict serialization
  ├── RepresentationMixin   # string representation
  ├── QuestionBasePromptsMixin  # template-based prompt generation
  ├── QuestionBaseGenMixin  # template rendering, question generation
  └── AnswerValidatorMixin  # response validation
```

The `RegisterQuestionsMeta` metaclass enforces required attributes and enables automatic registration of question types.

## Required Class Attributes

Every question type must define:
- `question_type` (str): Unique identifier (e.g., `"free_text"`)
- `_response_model` (Type): Pydantic model for validating responses
- `response_validator_class` (Type): Validator class for this question type

## Required Instance Attributes

- `question_name` (str): Identifier for the question instance (must be valid Python identifier)
- `question_text` (str): The actual question text
- `answering_instructions` (optional): Custom instructions for answering
- `question_presentation` (optional): Custom presentation template

## Available Question Types

### Core Types
- **QuestionFreeText** - Open-ended text responses
- **QuestionMultipleChoice** - Selection from predefined options
- **QuestionCheckBox** - Multiple selections from options
- **QuestionNumerical** - Numeric responses with optional min/max bounds
- **QuestionYesNo** - Binary yes/no (specialization of MultipleChoice)
- **QuestionList** - Response as a list of items
- **QuestionDict** - Response as key-value pairs
- **QuestionMatrix** - Grid-based responses (rows × columns)
- **QuestionRank** - Ranking/ordering of items
- **QuestionBudget** - Allocating a budget across options
- **QuestionExtract** - Extracting structured data from text
- **QuestionDropdown** - BM25-powered search through large option sets
- **QuestionMarkdown** - Responses with markdown formatting
- **QuestionPydantic** - User-defined Pydantic models as schemas

### Derived Types
- **QuestionLikertFive** - Standard 5-point Likert scale
- **QuestionLinearScale** - Linear scale with customizable range
- **QuestionTopK** - Selection of top K items
- **QuestionMultipleChoiceWithOther** - Multiple choice + "Other" option

### Special Purpose
- **QuestionFunctional** - Python function-based (not sent to LLMs)

## Key Files

| File | Purpose |
|------|---------|
| `question_base.py` | Abstract base class, core interface |
| `register_questions_meta.py` | Metaclass registration & validation |
| `question_base_prompts_mixin.py` | Template & prompt generation |
| `question_base_gen_mixin.py` | Question generation & rendering |
| `answer_validator_mixin.py` | Response validation interface |
| `response_validator_abc.py` | Validator base class |
| `descriptors.py` | Attribute validation descriptors |
| `exceptions.py` | Question-specific exceptions |
| `question_registry.py` | Factory & registry interface |

## Template System

Each question type has Jinja2 templates in `templates/{question_type}/`:
- `answering_instructions.jinja` - How to answer the question
- `question_presentation.jinja` - How the question is presented

Templates are managed by `TemplateManager` singleton and rendered via `QuestionBasePromptsMixin`.

## Validation Pipeline

```
1. Raw LLM response
   ↓
2. _validate_answer() called
   ↓
3. Response validator processes it
   ↓
4. Pydantic model validates structure
   ↓
5. If invalid, fix() attempts repair
   ↓
6. Returns validated dictionary
```

Each question type has a `ResponseValidator` (subclass of `ResponseValidatorABC`) that:
- Implements `_base_validate()` for Pydantic validation
- Implements `fix()` for automatic repair of common issues
- Implements `_post_process()` for final normalization

## Integration with Other Modules

### With Surveys
```python
question.to_survey()  # Creates Survey with single question
# Questions referenced by question_name in survey results
```

### With Scenarios
```python
question.render(scenario_dict)  # Substitutes Jinja2 variables
# Supports nested references: {{ scenario.variable }}
```

### With Models/Agents
```python
question.by(model).run()  # Creates Jobs → executes → returns Results
```

### With Results
```python
results.select(question_name)  # Access answers by question_name
```

## Creating a Question

```python
from edsl import QuestionFreeText

q = QuestionFreeText(
    question_name="greeting",
    question_text="What is your favorite greeting?"
)

# With scenario templating
q = QuestionFreeText(
    question_name="opinion",
    question_text="What do you think about {{ topic }}?"
)
q.render({"topic": "climate change"})
```

## Descriptor Pattern

Custom descriptors validate attributes at assignment:
- `QuestionNameDescriptor` - Validates Python identifier
- `QuestionTextDescriptor` - Validates string
- `QuestionOptionsDescriptor` - Validates list of options
- `IntegerDescriptor`, `NumericalOrNoneDescriptor` - Type validation

## Creating Custom Question Types

1. Subclass `QuestionBase`
2. Define required attributes:
   ```python
   question_type = "custom_type"
   _response_model = CustomResponse
   response_validator_class = CustomValidator
   ```
3. Implement `__init__()` with required parameters
4. Add templates: `templates/custom_type/*.jinja`
5. Create Pydantic response model and validator

## Method Chaining

```python
question
  .render(scenario)    # Returns new Question with substituted values
  .by(model)           # Returns Jobs
  .run()               # Returns Results
```

## Registry

The `Question` factory class provides:
- `Question.available()` - List all registered types
- `Question(question_type=..., ...)` - Create by type name
- `QuestionBase.from_dict(dict)` - Deserialize to correct subclass
