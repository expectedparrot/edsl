import copy

import pytest

from edsl import QuestionFreeText, QuestionMultipleChoice, Stem, literal
from edsl.prompts import Prompt
from edsl.sharedstate import current
from edsl.stem import StemError


def test_literal_template_syntax_survives_final_question_prompt_rendering():
    question = QuestionFreeText(
        question_name="value",
        question_text=Stem(
            "Value: {value}", value=literal("{{ 7 * 7 }}")
        ),
    )

    rendered_question = question.render({})
    final_prompt = Prompt(rendered_question.question_text).render({})

    assert str(final_prompt) == "Value: {{ 7 * 7 }}"


def test_deepcopy_preserves_lowered_stem_and_question_read_metadata():
    first = QuestionFreeText(question_name="first", question_text="First?")
    followup = QuestionMultipleChoice(
        question_name="followup",
        question_text=Stem("Thanks {name}; use {{{{ braces }}}}", name=first.answer),
        question_options=["A", "B"],
    )

    copied_stem = copy.deepcopy(followup.question_text)
    drawn = followup.draw(random_seed=1)

    assert str(copied_stem) == str(followup.question_text)
    assert copied_stem._stem_question_reads == ("first",)
    assert drawn.question_text._stem_question_reads == ("first",)
    assert str(Prompt(drawn.question_text).render({"first": {"answer": "Ada"}})) == (
        "Thanks Ada; use {{ braces }}"
    )


def test_interview_id_context_is_rejected_until_prompt_runtime_supplies_it():
    with pytest.raises(StemError, match="current.interview_id is not available"):
        Stem("Run {run_id}", run_id=current.interview_id)


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_literal_rejects_non_finite_floats(value):
    with pytest.raises(ValueError, match="must be finite"):
        literal(value)
