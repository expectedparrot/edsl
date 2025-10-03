# QuestionPydantic Implementation

## Overview

`QuestionPydantic` is a new question type for EDSL that allows users to specify arbitrary Pydantic models as response schemas for structured output from language models.

## Key Features

1. **Custom Pydantic Models**: Users can define any Pydantic model and use it as the expected response structure
2. **Automatic Schema Generation**: JSON schemas are automatically generated from Pydantic models
3. **Structured Output Support**: When using compatible services (e.g., OpenAI), the schema is passed to the LLM to constrain generation
4. **Post-hoc Validation**: For services without structured output, responses are validated against the schema
5. **Full Serialization**: Questions can be serialized/deserialized with dynamic model reconstruction

## Implementation Details

### Files Modified

1. **`edsl/questions/question_pydantic.py`** (new)
   - Main implementation of QuestionPydantic class
   - PydanticResponse and PydanticResponseValidator classes
   - Schema generation and validation logic

2. **`edsl/questions/__init__.py`**
   - Added QuestionPydantic to exports

3. **`edsl/questions/templates/pydantic/`** (new)
   - `answering_instructions.jinja`: Instructions for LLM responses
   - `question_presentation.jinja`: Question presentation template

4. **`edsl/invigilators/invigilators.py`**
   - Modified `async_get_agent_response()` to pass response schema to models (lines 300-303)

5. **`edsl/language_models/language_model.py`**
   - Added `response_schema` parameter support throughout the call chain
   - Modified `async_get_response()` and `_async_get_intended_model_call_outcome()`

6. **`edsl/inference_services/services/open_ai_service.py`**
   - Added structured output support using OpenAI's `json_schema` mode (lines 293-303)
   - Parameters include `response_format` with `type: "json_schema"` and `strict: true`

### Architecture Flow

```
User defines Pydantic model
    ↓
QuestionPydantic created with model
    ↓
JSON schema generated automatically
    ↓
Question executed with model
    ↓
InvigilatorAI passes schema to LanguageModel
    ↓
LanguageModel passes to InferenceService
    ↓
[If OpenAI] Schema sent as response_format parameter
    ↓
LLM generates structured response
    ↓
Response validated against Pydantic model
    ↓
Structured data returned to user
```

## Usage Examples

### Basic Usage

```python
from pydantic import BaseModel, Field
from edsl.questions import QuestionPydantic
from edsl.language_models import Model

class Person(BaseModel):
    name: str = Field(description="Full name")
    age: int = Field(description="Age in years", ge=0, le=150)
    occupation: str = Field(description="Job title")

q = QuestionPydantic(
    question_name="extract_person",
    question_text="Extract: Alice Johnson is a 28-year-old software engineer",
    pydantic_model=Person
)

results = q.by(Model('gpt-4o-mini')).run()
answer = results.select("answer.extract_person").first()
# Returns: {'name': 'Alice Johnson', 'age': 28, 'occupation': 'software engineer'}
```

### Complex Models

```python
class Product(BaseModel):
    name: str
    price: float = Field(gt=0)
    in_stock: bool
    categories: list[str]
    metadata: dict[str, str]

q = QuestionPydantic(
    question_name="extract_product",
    question_text="Extract product info from: Widget Pro costs $49.99...",
    pydantic_model=Product
)
```

## Technical Considerations

### OpenAI Strict Mode

- Schema includes `additionalProperties: false` for OpenAI compatibility
- `strict: true` mode ensures LLM output exactly matches schema
- Constraints (min/max) are respected in generated data

### Serialization

- Pydantic model classes cannot be directly serialized
- Solution: Store JSON schema, reconstruct dynamic model on deserialization
- `pydantic.create_model()` used to recreate models from schemas

### Validation

- Two-stage validation:
  1. Response wrapper (`PydanticResponse`) validation
  2. User's Pydantic model validation
- Detailed error messages on validation failure
- Automatic fixing of common issues (JSON string parsing)

## Testing

### Test Coverage

- 19 unit tests in `tests/questions/test_QuestionPydantic.py`
- Tests cover:
  - Construction and configuration
  - Schema generation
  - Validation (valid/invalid cases)
  - Serialization/deserialization
  - Answer simulation
  - Integration with models

### Live Testing

Successfully tested with OpenAI's `gpt-4o-mini` model:
- Structured output correctly generated
- Schema constraints respected
- Validation passed
- Correct data extraction from prompts

## Future Enhancements

1. **Extended Service Support**: Add structured output for other providers (Anthropic, Google, etc.)
2. **Schema Optimization**: Automatic schema simplification for better LLM compatibility
3. **Nested Models**: Better handling of complex nested Pydantic structures
4. **Type Hints**: Enhanced type hint support for lists, unions, optionals
5. **Schema Validation**: Pre-flight schema validation before sending to LLM

## Breaking Changes

None - this is a new feature with no impact on existing question types.

## Performance Considerations

- Schema generation is lightweight (cached in `data` property)
- No significant overhead compared to other question types
- Structured output may reduce token usage (more concise responses)

## Dependencies

- Requires `pydantic >= 2.0` (already in EDSL dependencies)
- Compatible with OpenAI models supporting structured output
- Falls back gracefully for other models

## Documentation

- See `examples/question_pydantic_demo.py` for comprehensive examples
- Inline documentation in `question_pydantic.py`
- Docstrings follow Google style guide

## Credits

Implemented as part of the EDSL framework enhancement to support modern LLM structured output capabilities.
