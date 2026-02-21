from __future__ import annotations
from typing import Optional, Union
from .question_multiple_choice import (
    QuestionMultipleChoice,
    MultipleChoiceResponseValidator,
)
from .exceptions import QuestionAnswerValidationError
from .decorators import inject_exception


class AttentionCheckResponseValidator(MultipleChoiceResponseValidator):
    """Validator for attention check responses.

    Extends the multiple choice validator to additionally verify that the
    selected answer matches the required correct_option.
    """

    required_params = ["question_options", "use_code", "correct_option"]

    def fix(self, response, verbose=False):
        """Attempt to fix an invalid attention check response.

        First applies the standard multiple choice fix strategies, then
        checks if the fixed answer matches the correct_option.
        """
        fixed = super().fix(response, verbose=verbose)

        # After the standard MC fix, verify the answer matches correct_option
        answer = fixed.get("answer")
        if answer is not None and answer != self.correct_option:
            if verbose:
                print(
                    f"Answer '{answer}' does not match required "
                    f"correct_option '{self.correct_option}'"
                )
            # Return the original response unchanged — validation will fail,
            # causing the question to be re-asked.
            return response

        return fixed

    def _post_process(self, edsl_answer_dict):
        """Check that the validated answer matches the required correct_option.

        This hook is called after Pydantic validation succeeds, so it will
        reject answers that are valid multiple-choice selections but not the
        correct attention-check answer.
        """
        answer = edsl_answer_dict.get("answer")
        if answer != self.correct_option:
            raise QuestionAnswerValidationError(
                message=(
                    f"Answer '{answer}' does not match the required option "
                    f"'{self.correct_option}'. The respondent must select "
                    f"'{self.correct_option}' to proceed."
                ),
                data=edsl_answer_dict,
            )
        return edsl_answer_dict

    valid_examples = [
        (
            {"answer": "Blue"},
            {
                "question_options": ["Red", "Blue", "Green"],
                "correct_option": "Blue",
            },
        )
    ]

    invalid_examples = [
        (
            {"answer": "Red"},
            {
                "question_options": ["Red", "Blue", "Green"],
                "correct_option": "Blue",
            },
            "Answer does not match the required option",
        ),
        (
            {"answer": None},
            {
                "question_options": ["Red", "Blue", "Green"],
                "correct_option": "Blue",
            },
            "Answer must not be null",
        ),
    ]


class QuestionAttentionCheck(QuestionMultipleChoice):
    """A question that requires the respondent to select a specific option to proceed.

    QuestionAttentionCheck is a subclass of QuestionMultipleChoice that enforces
    selection of a particular "correct" option. In human surveys this is used as
    an attention check — the respondent must demonstrate they are reading the
    question by picking the designated answer. If the wrong option is selected
    the answer is treated as invalid and the question is re-asked.

    Key Features:
    - Presents a fixed set of options (inherited from QuestionMultipleChoice)
    - Enforces that one specific ``correct_option`` must be chosen
    - Invalid selections cause the question to be re-administered
    - Useful for quality control in AI-agent surveys

    Examples:
        Basic usage:

        ```python
        q = QuestionAttentionCheck(
            question_name="attention_1",
            question_text="Please select 'Blue' to continue.",
            question_options=["Red", "Blue", "Green", "Yellow"],
            correct_option="Blue",
        )
        ```
    """

    question_type = "attention_check"
    response_validator_class = AttentionCheckResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_options: Union[list[str], list[list], list[float], list[int]],
        correct_option: str,
        include_comment: bool = True,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
    ):
        """Initialize a new attention check question.

        Parameters
        ----------
        question_name : str
            The name of the question, used as an identifier.
        question_text : str
            The text of the question to be asked.
        question_options : list
            The list of options the respondent can select from.
        correct_option : str
            The option that must be selected for the answer to be valid.
            Must be one of the values in ``question_options``.
        include_comment : bool, default=True
            Whether to include a comment field in the response.
        answering_instructions : Optional[str], default=None
            Custom instructions for how the model should answer.
        question_presentation : Optional[str], default=None
            Custom template for how the question is presented.

        Raises
        ------
        ValueError
            If ``correct_option`` is not in ``question_options``.

        Examples
        --------
        >>> q = QuestionAttentionCheck(
        ...     question_name="attn",
        ...     question_text="Select 'B' to proceed.",
        ...     question_options=["A", "B", "C"],
        ...     correct_option="B",
        ... )
        >>> q.correct_option
        'B'
        """
        if correct_option not in question_options:
            raise ValueError(
                f"correct_option '{correct_option}' must be one of "
                f"the question_options {question_options}"
            )

        super().__init__(
            question_name=question_name,
            question_text=question_text,
            question_options=question_options,
            use_code=False,
            include_comment=include_comment,
            answering_instructions=answering_instructions,
            question_presentation=question_presentation,
        )
        self._correct_option = correct_option

    @property
    def correct_option(self) -> str:
        """Return the correct option that must be selected."""
        return self._correct_option

    ################
    # Example
    ################
    @classmethod
    @inject_exception
    def example(cls, include_comment: bool = True) -> QuestionAttentionCheck:
        """Return an example of an attention check question."""
        return cls(
            question_name="attention_check",
            question_text="To demonstrate you are paying attention, please select 'Blue'.",
            question_options=["Red", "Blue", "Green", "Yellow"],
            correct_option="Blue",
            include_comment=include_comment,
        )


def main():
    """Create an example attention check question and demonstrate its functionality."""
    q = QuestionAttentionCheck.example()
    q.question_text
    q.question_options
    q.question_name
    q.correct_option
    # validate a correct answer
    q._validate_answer({"answer": "Blue", "comment": "I selected the correct one"})
    # simulate answer
    q._simulate_answer()
    q._simulate_answer(human_readable=False)
    # serialization (inherits from QuestionBase)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q

    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
