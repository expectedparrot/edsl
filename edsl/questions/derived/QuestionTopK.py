from typing import Optional
from edsl.exceptions import QuestionCreationValidationError
from edsl.questions.QuestionCheckBox import QuestionCheckBox


class QuestionTopK(QuestionCheckBox):

    """QuestionTopK"""

    question_type = "top_k"

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_options: list[str],
        min_selections: int,
        max_selections: int,
        short_names_dict: Optional[dict[str, str]] = None,
        instructions: Optional[str] = None,
    ):
        super().__init__(
            question_name=question_name,
            question_text=question_text,
            question_options=question_options,
            short_names_dict=short_names_dict,
            min_selections=min_selections,
            max_selections=max_selections,
            instructions=instructions,
        )
        if min_selections != max_selections:
            raise QuestionCreationValidationError(
                "TopK questions must have min_selections == max_selections"
            )
        if min_selections < 1:
            raise QuestionCreationValidationError(
                "TopK questions must have min_selections > 0"
            )
