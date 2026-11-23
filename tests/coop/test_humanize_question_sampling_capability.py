import pytest

from edsl import QuestionFreeText, Survey
from edsl.coop.coop import Coop
from edsl.coop.exceptions import CoopValueError


def test_humanize_rejects_question_sampling_until_supported():
    survey = Survey(
        [
            QuestionFreeText(question_name="q1", question_text="First?"),
            QuestionFreeText(question_name="q2", question_text="Second?"),
        ]
    ).sample_questions(["q1", "q2"], sample_size=1)

    coop = Coop.__new__(Coop)
    with pytest.raises(
        CoopValueError, match="Humanize does not yet support question sampling"
    ):
        coop.create_human_survey(survey)
