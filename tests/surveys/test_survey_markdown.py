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
    flags = {"with_question_names": True, "with_question_types": True}
    snippet = q.to_markdown(number=1, **flags)
    heading, answer = snippet.split("\n\n", 1)
    assert heading.startswith(f"**1. [{q.question_name}] “")
    assert heading.endswith(f"”** ({q.question_type})")
    assert answer.strip()
    assert q._markdown_hint or cls._markdown_answer is not QuestionBase._markdown_answer
    assert snippet in Survey([q]).to_markdown(style="questionnaire", **flags)


def test_cli_raw_markdown_and_default_json(tmp_path, coffee):
    survey = coffee.add_skip_rule("brew", "{{ drinks.answer }} != 'Yes'")
    expected = """# Survey

**1. “Do you drink coffee?”**

○ Yes{br}
○ No → Go to question 3

**2. “Favorite brew?”**

*Free-text response*

**3. “Where do you get coffee?”**

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

    rows = QuestionMatrixWithText.example().to_markdown().splitlines()
    assert "Additional text" in next(row for row in rows if row.startswith("| Item"))
    assert "Free text" in next(row for row in rows if row.startswith("| Support"))
    assert "Free text" not in next(row for row in rows if row.startswith("| Speed"))
    checkboxes = QuestionCheckBoxWithOther.example().to_markdown()
    assert "Select 1 to 3" in checkboxes and "☐ Other ______" in checkboxes
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
    question = QuestionFreeText(
        question_name="AGE", question_text="What is your age?\n\nUse years."
    )
    assert question.to_markdown(with_question_names=True, with_question_types=True) == (
        "**[AGE] “What is your age?**\n\nUse years.” (free_text)\n\n*Free-text response*"
    )


def test_empty_questionnaire():
    assert Survey().to_markdown(style="questionnaire") == "# Survey"


@pytest.mark.parametrize("names", [False, True])
@pytest.mark.parametrize("types", [False, True])
def test_cli_heading_options(coffee, tmp_path, names, types):
    path = tmp_path / "coffee.json"
    path.write_text(json.dumps(coffee.to_dict()))
    flags = []
    if names:
        flags.append("--with-question-names")
    if types:
        flags.append("--with-question-types")
    result = CliRunner().invoke(
        app, ["surveys", "show", str(path), "--markdown", *flags]
    )
    assert result.exit_code == 0, result.output
    heading = result.output.splitlines()[2]
    assert ("[drinks]" in heading) == names
    assert ("(multiple_choice)" in heading) == types
    assert result.output.rstrip() == coffee.to_markdown(
        style="questionnaire", with_question_names=names, with_question_types=types
    )
    if flags:
        result = CliRunner().invoke(app, ["surveys", "show", str(path), *flags])
        assert result.exit_code == 2
        assert json.loads(result.output)["error"]["code"] == "USAGE_ERROR"


def test_matrix_table_labels_and_escaping():
    from edsl import QuestionMatrix, QuestionCheckboxMatrix

    q = QuestionMatrix(
        question_name="rating",
        question_text="Rate each item.",
        question_items=["Left | right", "Line one\nline two"],
        question_options=[1, 2],
        option_labels={1: "Low | lowest", 2: "High"},
    )
    grid = [line for line in q.to_markdown().splitlines() if line.startswith("|")]
    assert len(grid) == 4
    assert r"1 — Low \| lowest" in grid[0]
    assert r"Left \| right" in grid[2] and grid[2].count("○") == 2
    assert "Line one line two" in grid[3]
    checkbox_grid = QuestionCheckboxMatrix.example().to_markdown()
    assert "Select up to 2" in checkbox_grid
    assert (
        next(
            row for row in checkbox_grid.splitlines() if row.startswith("| Monday")
        ).count("☐")
        == 3
    )


def test_dynamic_matrix_keeps_unresolved_axes():
    from edsl import QuestionMatrix

    q = QuestionMatrix(
        question_name="rating",
        question_text="Rate each item.",
        question_items="{{ items }}",
        question_options={"from": "{{ choices }}", "add": ["Other"]},
    )
    md = q.to_markdown()
    assert "**Rows** — {{ items }}" in md
    assert "**Options** — {{ choices }}, Other" in md


def test_dropdown_preview_and_expansion_through_cli(tmp_path):
    from edsl import QuestionDropdown

    q = QuestionDropdown.example()
    survey = Survey([q])
    path = tmp_path / "dropdown.ep"
    survey.git.save(path)
    args = ["surveys", "show", str(path)]
    runner = CliRunner()
    for expanded in (False, True):
        flags = ["--expand-options"] if expanded else []
        result = runner.invoke(app, [*args, "--markdown", *flags])
        assert result.exit_code == 0, result.output
        visible = [
            line.removeprefix("· ").rstrip()
            for line in result.output.splitlines()
            if line.startswith("· ")
        ]
        assert visible == (q.question_options if expanded else q.question_options[:5])
        assert ("*61 more choices*" in result.output) == (not expanded)
        assert "Search returns up to 3 matches." in result.output
        assert result.output.rstrip() == survey.to_markdown(
            style="questionnaire", expand_options=expanded
        )
    result = runner.invoke(app, [*args, "--expand-options"])
    assert (
        result.exit_code == 2
        and json.loads(result.output)["error"]["code"] == "USAGE_ERROR"
    )


@pytest.mark.parametrize("size,footer", [(5, ""), (6, "*1 more choice*")])
def test_dropdown_preview_boundary(size, footer):
    from edsl import QuestionDropdown

    choices = [f"City {i}" for i in range(size)]
    q = QuestionDropdown("city", "Pick a city.", choices, top_k=1)
    preview = q.to_markdown()
    assert "Search returns up to 1 match." in preview
    assert [line for line in preview.splitlines() if "more choice" in line] == (
        [footer] if footer else []
    )


def test_fill_in_tables_show_authored_values_and_empty_answers():
    from edsl import QuestionBudget, QuestionDemand

    budget = QuestionBudget(
        "allocate",
        "How would you allocate your time?",
        ["Sleep", "Study | work"],
        24,
        remainder_option="Sleep",
    )
    demand = QuestionDemand("demand", "How many at each price?", [0, 1.50])
    for q, columns, rows in (
        (budget, ["Item", "Amount"], ["Sleep", r"Study \| work"]),
        (demand, ["Price", "Quantity"], ["0", "1.5"]),
    ):
        md = q.to_markdown()
        table = [line for line in md.splitlines() if line.startswith("| ")]
        assert [s.strip() for s in table[0].strip("|").split("|")] == columns
        assert len(table) == len(rows) + 2
        for value, row in zip(rows, table[2:]):
            assert row.startswith(f"| {value} ") and row.rstrip("| ").endswith(value)
    assert "24 across these items" in budget.to_markdown()
    assert "Any remainder goes to Sleep." in budget.to_markdown()


def test_rank_shows_choices_and_empty_positions():
    from edsl import QuestionRank

    md = QuestionRank.example().to_markdown()
    assert "**Choices** — Pizza, Pasta, Salad, Soup" in md
    assert [line.strip() for line in md.splitlines() if "choice ______" in line] == [
        "1st choice ______",
        "2nd choice ______",
    ]
    q = QuestionRank("rank", "Rank these.", [str(i) for i in range(22)])
    md = q.to_markdown()
    for ordinal in ("3rd", "4th", "11th", "12th", "13th", "21st", "22nd"):
        assert f"{ordinal} choice ______" in md


def test_multiple_choice_write_in_uses_authored_label_once():
    from edsl import QuestionMultipleChoiceWithOther

    md = QuestionMultipleChoiceWithOther.example().to_markdown()
    assert md.count("Other (please specify)") == 1
    assert "○ Other (please specify) ______" in md


def test_jinja_question_in_saved_markdown_preview(tmp_path):
    question = QuestionFreeText(
        "city",
        "Why {{ city_name | title }}? {% if count > 1 %}What changed?{% endif %}",
    )
    survey = Survey([question])
    package = tmp_path / "city.ep"
    survey.git.save(package)
    result = CliRunner().invoke(app, ["surveys", "show", str(package), "--markdown"])
    assert result.exit_code == 0, result.output
    assert (
        "**1. “Why `{{ city_name | title }}`? `{% if count > 1 %}`What changed?"
        "`{% endif %}`”**"
    ) in result.output
    assert "<< city_name | title >>" in survey.to_markdown()


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("A *city* called {{ city }}.", r"A \*city\* called `{{ city }}`."),
        ("{{ x['}}'] | default('`') }}", "``{{ x['}}'] | default('`') }}``"),
        ("{{ a }}{{ b }}", "`{{ a }}{{ b }}`"),
        ("A  {{- x -}}  B", "A  `{{- x -}}`  B"),
        (
            "{% raw %}{{ literal }}{% endraw %}",
            "`{% raw %}`{{ literal }}`{% endraw %}`",
        ),
        ("{# {{ hidden }} #}", "{# {{ hidden }} #}"),
        ("{{ first\n\n | title }}", "`{{ first   | title }}`"),
        ("Plain {{ unfinished", "Plain {{ unfinished"),
        ("An invalid {{ ] }}", r"An invalid {{ \] }}"),
    ],
)
def test_question_jinja_spans(source, expected):
    from edsl.questions.markdown_layout import question_text

    assert question_text(source) == expected
