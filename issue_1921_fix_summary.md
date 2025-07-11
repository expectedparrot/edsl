# Fix for Issue #1921: Handle Linear Scale Label Responses

## Issue Description
Issue: https://github.com/expectedparrot/edsl/issues/1921

The issue was that language models sometimes return an option label instead of a numeric value when responding to a `QuestionLinearScale`. For example, if the scale had labels like `1: "I hate it"` and `5: "I love it"`, a model might respond with "I love it" instead of the expected integer value 5.

## Solution

We implemented a fix in the `QuestionLinearScale` class by:

1. Creating a custom response validator `LinearScaleResponseValidator` that extends `MultipleChoiceResponseValidator`
2. Adding label-to-option mapping functionality that handles:
   - Exact label matches (e.g., "Love it" → 5)
   - Partial label matches with intelligent scoring (e.g., "I love" → 5)
   - Case insensitivity (e.g., "HATE IT" → 1)
   - Contextual matching (e.g., "I would say I'm neutral about it" → 3)
   
3. Implementing a sophisticated scoring system that prioritizes:
   - Exact substring matches
   - Common words
   - Sentiment word matches (e.g., "love", "hate", "neutral")
   - Character similarity

4. Preserving existing functionality:
   - Valid integer answers remain unchanged
   - String numeric values are converted to integers
   - Fallback to parent behavior for non-matching labels

## Tests

We created comprehensive tests in `tests/questions/test_linear_scale_labels/test_labels.py` that verify:

1. Exact and partial label matching
2. Case insensitive matching
3. Contextual matching with surrounding words
4. Handling of valid integer answers
5. Conversion of numeric strings
6. Fallback behavior for non-matching labels

## Implementation Details

The core of the fix is the scoring system in the `fix` method of `LinearScaleResponseValidator`. When a non-numeric response is received, the method:

1. First tries to validate the response as-is or convert it to a number
2. If that fails, it creates a mapping from option labels to options
3. Checks for exact matches with the label text
4. If no exact match is found, it calculates similarity scores for each label:
   - 100 points for substring matches (label in response)
   - 75 points for inverse substring matches (response in label)
   - 50 points per matching word
   - 25 points weighted by character similarity ratio
   - 200 bonus points for matching sentiment words ("love", "hate", "neutral")
5. Uses the highest scoring match if above zero
6. Falls back to parent class behavior if no good match is found

This approach enables intelligent handling of a variety of responses while maintaining the original functionality.