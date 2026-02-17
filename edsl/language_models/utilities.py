import asyncio
from typing import Any, Optional, List
from ..base import InferenceServiceType
from ..surveys import Survey

from .language_model import LanguageModel


def create_survey(num_questions: int, chained: bool = True, take_scenario=False):
    from ..questions import QuestionFreeText

    survey = Survey()
    for i in range(num_questions):
        if take_scenario:
            q = QuestionFreeText(
                question_text=f"XX{i}XX and {{scenario_value }}",
                question_name=f"question_{i}",
            )
        else:
            q = QuestionFreeText(
                question_text=f"XX{i}XX", question_name=f"question_{i}"
            )
        survey.add_question(q)
        if i > 0 and chained:
            survey.add_targeted_memory(f"question_{i}", f"question_{i-1}")
    return survey


def create_language_model(
    exception: Exception, fail_at_number: int, never_ending=False
):
    """Create a test model that fails at a specific question number.

    Uses parameters that survive serialization/deserialization, so the
    behavior works in both local and remote Runner execution.
    """
    from .model import Model

    def factory():
        return Model(
            "test",
            canned_response="SPAM!",
            fail_at_number=fail_at_number,
            never_ending=never_ending,
        )

    return factory
