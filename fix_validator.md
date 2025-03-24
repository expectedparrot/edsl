# Question Validator Refactoring Guide

## Refactoring Progress

- [x] question_free_text.py
- [x] question_list.py
- [x] question_numerical.py  
- [x] question_check_box.py
- [x] question_budget.py
- [x] question_multiple_choice.py
- [x] question_dict.py
- [x] question_extract.py
- [ ] question_functional.py (skipped per request)
- [x] question_matrix.py
- [x] question_rank.py

The goal of this refactoring is to move the validation logic from ResponseValidatorABC child classes to Pydantic models, which provides better type safety, clearer validation errors, and more robust validation overall.

## Step 1: Create Pydantic Models with Proper Validation

For each question type, implement the following changes:

1. Create a base Pydantic model for the question type (e.g., `NumericalResponse`, `CheckboxResponse`)
   - Define all required fields and their types
   - Add proper docstrings with examples
   - Include type annotations for all fields

2. If the question has constraints (min/max values, selection counts, etc.):
   - Create a more specific model by extending the base model
   - Implement constraints using Pydantic's `model_validator` (mode='after')
   - For permissive modes, create a separate model or conditionally skip validation

3. Use QuestionAnswerValidationError for all validation errors:
   ```python
   validation_error = ValidationError.from_exception_data(
       title='ModelName',
       line_errors=[{
           'type': 'value_error',
           'loc': ('field_name',),
           'msg': 'Human-readable error message',
           'input': invalid_value,
           'ctx': {'error': 'Error context'}
       }]
   )
   raise QuestionAnswerValidationError(
       message=f"Detailed error message",
       data=self.model_dump(),
       model=self.__class__,
       pydantic_error=validation_error
   )
   ```

4. Update the create_response_model function to use the new Pydantic models

## Step 2: Update the ResponseValidator

1. Keep the ResponseValidator class but simplify it:
   - The `_check_constraints` method can often be removed or simplified
   - Improve the `fix()` method to handle different error cases
   - Ensure the error messages are clear and detailed

2. Fix method should attempt multiple strategies to recover from invalid responses:
   - Convert types (e.g., string to list)
   - Extract values from text (e.g., find numbers in text)
   - Parse structured formats (e.g., comma-separated values)
   - For each attempt, validate with the Pydantic model before returning

## Step 3: Add Comprehensive Documentation

1. Add detailed docstrings to all components:
   - Main class
   - Pydantic models
   - ResponseValidator class
   - Helper functions
   - All methods

2. Include examples in docstrings that demonstrate:
   - Valid usage patterns
   - Common error cases and how they're handled
   - Edge cases (boundaries, empty values, etc.)
   - How the validator fixes invalid responses

3. Use doctests to verify functionality:
   ```python
   """
   Examples:
       >>> # Valid response
       >>> response = Model(answer=42)
       >>> response.answer
       42
       
       >>> # Invalid response
       >>> try:
       ...     Model(answer="not a number")
       ... except Exception as e:
       ...     print("Validation error occurred")
       Validation error occurred
   """
   ```

## Step 4: Testing

1. Run the doctest command to check that your changes work:
   ```
   python -m pytest --doctest-modules edsl/questions/your_question_file.py -v
   ```

2. Fix any issues that arise:
   - Error messages might not match expected patterns
   - Exception types might be different
   - Type conversion might behave differently

3. Common fixes:
   - Use more general patterns in exception tests: `any(x in str(e) for x in ["Error1", "Error2"])`
   - Avoid using `self_check()` in doctests as it might depend on environment
   - Ensure all examples use appropriate values for the constraints

## Step 5: Implementation Tips

1. For constraint validation:
   - Put validation in the Pydantic model, not in the validator
   - Use explicit error messages that explain what constraint was violated
   - Include both the constraint value and the actual value in error messages

2. For fixing invalid responses:
   - Try multiple approaches in order of likelihood
   - Log verbose output when verbose=True
   - Always preserve comments and other metadata when fixing

3. For numeric validation:
   - Handle both integers and floats
   - Watch for edge cases like zero, negative values
   - Consider parsing numbers from strings with regex

4. For list/checkbox validation:
   - Validate both the items and the count constraints
   - Handle common formats like comma-separated values
   - Consider both code values (indices) and text values (labels)

## Common Patterns

### Base Model Structure
```python
class BaseResponse(BaseModel):
    """Base model with docstrings and examples."""
    answer: RequiredType  # Define proper type
    comment: Optional[str] = None
    generated_tokens: Optional[Any] = None
```

### Constraint Validation
```python
@model_validator(mode='after')
def validate_constraints(self):
    """Validate that answer meets constraints."""
    if constraint_violated:
        # Create validation error and raise QuestionAnswerValidationError
    return self
```

### Fix Method
```python
def fix(self, response, verbose=False):
    """Try multiple approaches to fix invalid responses."""
    # 1. Try parsing from answer field
    # 2. Try parsing from generated_tokens
    # 3. Try multiple formats
    # For each attempt, validate with model
    return fixed_response
```
