from __future__ import annotations
from typing import Optional

from .descriptors import QuestionOptionsDescriptor, OptionLabelDescriptor
from .question_multiple_choice import (
    QuestionMultipleChoice,
    MultipleChoiceResponseValidator,
)
from .decorators import inject_exception


class LinearScaleResponseValidator(MultipleChoiceResponseValidator):
    """Validator for linear scale responses."""

    required_params = ["question_options", "use_code", "option_labels"]

    def fix(self, response, verbose=False):
        """
        Attempt to fix an invalid linear scale response.

        This extends the MultipleChoiceResponseValidator fix method to additionally
        check if the answer is one of the option labels instead of the expected integer value.

        Parameters:
            response: The invalid response to fix
            verbose: Whether to print debug information

        Returns:
            A fixed response dict if possible, otherwise the original response
        """
        if verbose:
            print(f"Starting fix with response: {response}")
            print(f"Option labels: {self.option_labels}")
            print(f"Question options: {self.question_options}")

        # First check if the response is already valid with an integer answer
        try:
            # Try to validate the original response
            self.response_model.model_validate(response)
            # If successful, the response is already valid
            if verbose:
                print("Response is already valid, returning as is")
            return response
        except Exception as e:
            # Response is invalid, proceed with fixing
            if verbose:
                print(f"Response validation failed: {e}")
            pass

        # Don't attempt to fix None values
        if response.get("answer") is None:
            if verbose:
                print("Not attempting to fix None answer value")
            return response

        # Get the response text to analyze
        response_text = str(response.get("answer", ""))
        if not response_text:
            response_text = str(response.get("generated_tokens", ""))

        if verbose:
            print(f"Analyzing response text: '{response_text}'")

        # Try to convert a numeric string to an integer
        try:
            numeric_value = int(response_text.strip())
            if numeric_value in self.question_options:
                proposed_data = {
                    "answer": numeric_value,
                    "comment": response.get("comment"),
                    "generated_tokens": response.get("generated_tokens"),
                }
                if verbose:
                    print(
                        f"Converted string '{response_text}' to integer {numeric_value}"
                    )
                return proposed_data
        except (ValueError, TypeError):
            # Not a valid number, continue with label matching
            if verbose:
                print(f"'{response_text}' is not a valid number, trying label matching")
            pass

        # Strategy: Check if the answer is one of the option labels
        response_lower = response_text.lower().strip()

        # Create a reverse mapping from label to option
        label_to_option = {}
        for option, label in self.option_labels.items():
            if label:  # Make sure the label is not None
                label_to_option[str(label).lower().strip()] = option

        if verbose:
            print(f"Label to option mapping: {label_to_option}")

        # Try exact matches first
        for label, option in label_to_option.items():
            if response_lower == label:
                if verbose:
                    print(
                        f"Exact match found: '{label}' corresponds to option {option}"
                    )

                proposed_data = {
                    "answer": option,
                    "comment": response.get("comment"),
                    "generated_tokens": response.get("generated_tokens"),
                }

                try:
                    # Validate the fixed answer
                    self.response_model.model_validate(proposed_data)
                    if verbose:
                        print(f"Fixed answer using exact label match: {option}")
                    return proposed_data
                except Exception as e:
                    if verbose:
                        print(f"Validation failed for exact label match: {e}")

        # Try partial matches next by calculating the best match score
        best_match = None
        best_score = 0
        best_option = None

        for label, option in label_to_option.items():
            score = 0
            match_type = None

            # Calculate match score - higher is better
            # Check for substring match (highest priority)
            if label in response_lower:
                score += 100
                match_type = f"Label '{label}' is in response '{response_lower}'"
            elif response_lower in label:
                score += 75
                match_type = f"Response '{response_lower}' is in label '{label}'"

            # Word overlap (medium priority)
            label_words = set(label.split())
            response_words = set(response_lower.split())
            common_words = label_words.intersection(response_words)

            if common_words:
                score += 50 * len(common_words)
                match_type = f"Common words: {common_words}"

            # Character matching for similar words (lowest priority)
            # For example "love" should match with "Love it" but not with "Hate it"
            for resp_word in response_words:
                for label_word in label_words:
                    if resp_word in label_word or label_word in resp_word:
                        # Calculate similarity
                        longer = max(len(resp_word), len(label_word))
                        shorter = min(len(resp_word), len(label_word))
                        if longer > 0:
                            similarity = shorter / longer
                            score += 25 * similarity
                            if not match_type:
                                match_type = (
                                    f"Word similarity: '{resp_word}' and '{label_word}'"
                                )

            # Special case for love/hate/neutral sentiment words
            if "love" in response_lower and "love" in label:
                score += 200  # Strong boost for matching sentiment
            elif "hate" in response_lower and "hate" in label:
                score += 200  # Strong boost for matching sentiment
            elif "neutral" in response_lower and "neutral" in label:
                score += 200  # Strong boost for matching sentiment

            # Track the best match
            if score > best_score:
                best_score = score
                best_match = label
                best_option = option

            if verbose:
                print(
                    f"Match score for '{label}' -> {option}: {score} ({match_type if match_type else 'No specific match'})"
                )

        # If we found a good match, use it
        if best_score > 0:
            if verbose:
                print(
                    f"Best partial match: '{best_match}' corresponds to option {best_option} (score: {best_score})"
                )

            proposed_data = {
                "answer": best_option,
                "comment": response.get("comment"),
                "generated_tokens": response.get("generated_tokens"),
            }

            try:
                # Validate the fixed answer
                self.response_model.model_validate(proposed_data)
                if verbose:
                    print(f"Fixed answer using best partial match: {best_option}")
                return proposed_data
            except Exception as e:
                if verbose:
                    print(f"Validation failed for best partial match: {e}")

        # Fall back to parent class fix method for other cases
        if verbose:
            print("No label matches found, falling back to parent class fix method")
        return super().fix(response, verbose)


class QuestionLinearScale(QuestionMultipleChoice):
    """This question prompts the agent to respond to a statement on a linear scale."""

    question_type = "linear_scale"
    option_labels: Optional[dict[int, str]] = OptionLabelDescriptor()
    question_options = QuestionOptionsDescriptor(linear_scale=True)
    response_validator_class = LinearScaleResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_options: list[int],
        option_labels: Optional[dict[int, str]] = None,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
        include_comment: Optional[bool] = True,
    ):
        """Instantiate a new QuestionLinearScale.

        :param question_name: The name of the question.
        :param question_text: The text of the question.
        :param question_options: The options the respondent should select from.
        :param option_labels: Maps question_options to labels.
        :param instructions: Instructions for the question. If not provided, the default instructions are used. To view them, run `QuestionLinearScale.default_instructions`.
        """
        super().__init__(
            question_name=question_name,
            question_text=question_text,
            question_options=question_options,
            use_code=False,  # question linear scale will have its own code
            include_comment=include_comment,
        )
        self.question_options = question_options
        if isinstance(option_labels, str):
            self.option_labels = option_labels
        else:
            self.option_labels = (
                {int(k): v for k, v in option_labels.items()} if option_labels else {}
            )
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation

    ################
    # Helpful
    ################
    @classmethod
    @inject_exception
    def example(cls, include_comment: bool = True) -> QuestionLinearScale:
        """Return an example of a linear scale question."""
        return cls(
            question_text="How much do you like ice cream?",
            question_options=[1, 2, 3, 4, 5],
            question_name="ice_cream",
            option_labels={1: "I hate it", 5: "I love it"},
            include_comment=include_comment,
        )


def main():
    """Create an example of a linear scale question and demonstrate its functionality."""
    from edsl.questions import QuestionLinearScale

    q = QuestionLinearScale.example()
    q.question_text
    q.question_options
    q.question_name
    # validate an answer
    q._validate_answer({"answer": 3, "comment": "I like custard"})
    # translate answer code
    q._translate_answer_code_to_answer(3, {})
    # simulate answer
    q._simulate_answer()
    q._simulate_answer(human_readable=False)
    q._validate_answer(q._simulate_answer(human_readable=False))
    # Test with a label-based answer
    test_label_answer = {"answer": "I love it", "comment": "It's the best!"}
    fixed_answer = q.response_validator.fix(test_label_answer, verbose=True)
    print(f"Fixed label-based answer: {fixed_answer}")
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q

    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
