from typing import Type, Optional
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
        k: int,
        short_names_dict: Optional[dict[str, str]] = None,
        instructions: Optional[str] = None,
    ):
        super().__init__(
            question_name=question_name,
            question_text=question_text,
            question_options=question_options,
            short_names=short_names_dict,
            min_selections=k,
            max_selections=k,
            instructions=instructions,
        )
        self.k = k
