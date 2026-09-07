import json

import pytest

from edsl import QuestionMultipleChoice, Survey


@pytest.mark.parametrize("source_kind", ["text", "file", "rows"])
def test_jsonl_preserves_pinned_options_and_draw_behavior(source_kind, tmp_path):
    question = QuestionMultipleChoice(
        question_name="pick",
        question_text="Pick one.",
        question_options=["A", "Fixed", "B", "Other"],
    )
    survey = Survey(
        [question],
        questions_to_randomize=["pick"],
        options_to_pin={"pick": ["Fixed", "Other"]},
    )
    if source_kind == "file":
        source = tmp_path / "survey.jsonl"
        survey.to_jsonl(source)
    elif source_kind == "rows":
        source = survey.to_jsonl_rows()
    else:
        source = survey.to_jsonl()

    restored = Survey.from_jsonl(source)

    assert restored.options_to_pin == survey.options_to_pin
    assert restored.questions_to_randomize == ["pick"]
    for _ in range(5):
        options = restored.draw().questions[0].question_options
        assert options[1] == "Fixed"
        assert options[3] == "Other"
        assert {options[0], options[2]} == {"A", "B"}
    assert survey.questions[0].question_options == ["A", "Fixed", "B", "Other"]


def test_jsonl_without_pins_retains_legacy_defaults():
    question = QuestionMultipleChoice.example()
    survey = Survey([question], questions_to_randomize=[question.question_name])
    text = survey.to_jsonl()

    assert "options_to_pin" not in json.loads(text.splitlines()[0])
    restored = Survey.from_jsonl(text)
    assert restored.options_to_pin == {}
    assert restored.questions_to_randomize == survey.questions_to_randomize
