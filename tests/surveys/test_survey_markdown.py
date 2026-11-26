import json

import pytest
from click.testing import CliRunner

from edsl import QuestionFreeText, QuestionMultipleChoice, Survey
from edsl.__main__ import app
from edsl.questions.question_base import QuestionBase
from edsl.questions.register_questions_meta import RegisterQuestionsMeta


@pytest.fixture
def coffee():
    return Survey(
        [
            QuestionMultipleChoice(
                question_name="drinks",
                question_text="Do you drink coffee?",
                question_options=["Yes", "No"],
            ),
            QuestionFreeText(question_name="brew", question_text="Favorite brew?"),
            QuestionFreeText(
                question_name="source", question_text="Where do you get coffee?"
            ),
        ]
    )


@pytest.mark.parametrize(
    "cls",
    RegisterQuestionsMeta.get_registered_classes().values(),
    ids=lambda cls: cls.__name__,
)
def test_registered_question_markdown(cls):
    q = cls.example()
    snippet = q.to_markdown(number=1)
    heading, answer = snippet.split("\n\n", 1)
    assert heading.startswith(f"**1. [{q.question_name}] “")
    assert heading.endswith(f"”** ({q.question_type})")
    assert answer.strip()
    assert q._markdown_hint or cls._markdown_answer is not QuestionBase._markdown_answer
    assert snippet in Survey([q]).to_markdown(style="questionnaire")


def test_cli_raw_markdown_and_default_json(tmp_path, coffee):
    survey = coffee.add_skip_rule("brew", "{{ drinks.answer }} != 'Yes'")
    expected = """# Survey

**1. [drinks] “Do you drink coffee?”** (multiple_choice)

○ Yes{br}
○ No → Go to question 3

**2. [brew] “Favorite brew?”** (free_text)

*Free-text response*

**3. [source] “Where do you get coffee?”** (free_text)

*Free-text response*""".format(
        br="  "
    )
    assert survey.to_markdown(style="questionnaire") == expected
    assert "| question_name " in survey.to_markdown()
    runner = CliRunner()
    package = tmp_path / "survey.ep"
    survey.git.save(package)
    serialized = tmp_path / "survey.json"
    serialized.write_text(json.dumps(survey.to_dict()))
    for path in (package, serialized):
        result = runner.invoke(app, ["surveys", "show", str(path), "--markdown"])
        assert result.exit_code == 0, result.output
        assert result.output == expected + "\n"
        result = runner.invoke(app, ["surveys", "show", str(path)])
        assert json.loads(result.output)["status"] == "ok"
    result = runner.invoke(
        app, ["surveys", "show", str(tmp_path / "missing.ep"), "--markdown"]
    )
    assert result.exit_code != 0 and json.loads(result.output)["status"] == "error"


def test_routing_stop_and_competing_conditions(coffee):
    coffee.add_stop_rule("drinks", "{{ drinks.answer }} == 'No'")
    assert "○ No → End survey" in coffee.to_markdown(style="questionnaire")
    coffee.add_rule("drinks", "{{ drinks.answer }} == 'Yes'", "source")
    coffee.add_skip_rule("brew", "{{ drinks.answer }} != 'Yes'")
    rendered = coffee.to_markdown(style="questionnaire")
    assert rendered.index("Go to question 3") < rendered.index("End survey")
    assert "Skip this question if the answer to question 1 is not “Yes”." in rendered
    assert "○ No →" not in rendered


def test_display_dynamic_options_and_labels():
    from edsl import QuestionLinearScale, QuestionRank

    q = QuestionRank(
        question_name="rank",
        question_text="Rank these.",
        question_options="{{ colors.answer }}",
    )
    assert "Rank all options" in q.to_markdown()
    assert "{{ colors.answer }}" in q.to_markdown()
    assert "○ 1 — I hate it" in QuestionLinearScale.example().to_markdown()


def test_matrix_rows_write_in_and_bounds():
    from edsl import (
        QuestionBudget,
        QuestionMatrixWithText,
        QuestionNumericalRange,
        QuestionCheckBoxWithOther,
    )

    assert (
        "Support (with a text response)"
        in QuestionMatrixWithText.example().to_markdown()
    )
    checkboxes = QuestionCheckBoxWithOther.example().to_markdown()
    assert "Select 1 to 3" in checkboxes and "☐ Other (write in)" in checkboxes
    assert "Allocate a total of 100" in QuestionBudget.example().to_markdown()
    assert "0 to 1000" in QuestionNumericalRange.example().to_markdown()


def test_preserves_compound_rule_and_authored_templates(coffee):
    expression = "{{ drinks.answer }} == 'Yes' and {{ brew.answer }} != 'espresso'"
    coffee.add_stop_rule("brew", expression)
    assert expression in coffee.to_markdown(style="questionnaire")
    prompt = QuestionFreeText(
        question_name="followup", question_text="Why {{ first_choice.answer }}?"
    )
    assert "{{ first_choice.answer }}" in prompt.to_markdown()


def test_probabilistic_choice_describes_elicited_answer():
    question = QuestionMultipleChoice(
        question_name="drink",
        question_text="What will you drink?",
        question_options=["Coffee", "Tea"],
        probabilistic_response={"representation": "categorical"},
    )
    assert "Allocate probabilities totaling 1." in question.to_markdown()


def test_standalone_question_keeps_name_case_and_type_after_full_prompt():
    question = QuestionFreeText(question_name="AGE", question_text="What is your age?\n\nUse years.")
    assert question.to_markdown() == (
        "**[AGE] “What is your age?**\n\nUse years.” (free_text)\n\n*Free-text response*"
    )


def test_empty_questionnaire():
    assert Survey().to_markdown(style="questionnaire") == "# Survey"
