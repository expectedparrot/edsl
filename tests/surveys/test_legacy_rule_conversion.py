"""Legacy rule conversion must only replace actual question references (#2658)."""

import warnings

import pytest

from edsl import Model, QuestionFreeText, Survey
from edsl.surveys.base import EndOfSurvey
from edsl.surveys.rules import Rule


@pytest.mark.parametrize(
    "expression, expected, answers",
    [
        ("q10 == 'yes'", "{{ q10.answer }} == 'yes'", {"q10": "yes"}),
        ("q10.answer == 'yes'", "{{ q10.answer }} == 'yes'", {"q10": "yes"}),
        (
            "q1 == 'no' and q10 == 'yes'",
            "{{ q1.answer }} == 'no' and {{ q10.answer }} == 'yes'",
            {"q1": "no", "q10": "yes"},
        ),
        (
            "q1 == 'yes' and q1.answer == 'yes'",
            "{{ q1.answer }} == 'yes' and {{ q1.answer }} == 'yes'",
            {"q1": "yes"},
        ),
        ("q1 == 'q1'", "{{ q1.answer }} == 'q1'", {"q1": "q1"}),
        (
            'q10 == "q1.answer" # q1 and q10.answer',
            '{{ q10.answer }} == "q1.answer" # q1 and q10.answer',
            {"q10": "q1.answer"},
        ),
        (
            '("é" == "é" and\n q10 == "yes")',
            '("é" == "é" and\n {{ q10.answer }} == "yes")',
            {"q10": "yes"},
        ),
        (
            "q10.answer['q1'] == 'yes'",
            "{{ q10.answer }}['q1'] == 'yes'",
            {"q10": {"q1": "yes"}},
        ),
        (
            "choice == 'yes' and choice(['yes']) == 'yes'",
            "{{ choice.answer }} == 'yes' and choice(['yes']) == 'yes'",
            {"choice": "yes"},
        ),
    ],
)
@pytest.mark.parametrize("reverse_names", [False, True])
def test_conversion_preserves_expression(expression, expected, answers, reverse_names):
    names = ["q1", "q10", "answer", "r", "choice"]
    if reverse_names:
        names.reverse()
    with pytest.warns(UserWarning, match="old syntax"):
        rule = Rule(5, expression, 6, dict.fromkeys(names, 0), priority=0)
    assert rule.expression == expected
    assert rule._prior_question_is_in_expression() == set(answers)
    assert rule.evaluate(answers) is True
    restored = Rule.from_dict(rule.to_dict())
    assert restored.expression == expected
    assert restored.evaluate(answers) is True


@pytest.mark.parametrize("name", ["r", "u", "e", "ue", "rue", "T"])
def test_default_rules_preserve_true(name):
    question = QuestionFreeText(question_name=name, question_text="Hi?")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        survey = Survey([question])
    assert not [warning for warning in caught if "old syntax" in str(warning.message)]
    rule = list(survey.rule_collection)[0]
    assert rule.expression == "True"
    assert rule.evaluate({name: "yes"}) is True
    assert len(survey.by(Model("test")).prompts().to_dicts()) == 1


@pytest.mark.parametrize(
    "expression",
    ["True", "'q1' == 'q1'", "choice(['q1']) == 'q1'", "randint(0, 0) == 0"],
)
def test_expressions_without_question_references_are_unchanged(expression):
    names = {"q1": 0, "r": 0, "choice": 0}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        rule = Rule(0, expression, 1, names, priority=0)
    assert not caught
    assert rule.expression == expression
    assert rule.evaluate({name: "irrelevant" for name in names}) is True


def test_explicit_jinja_rule_is_unchanged():
    expression = "{{ q10.answer }} == 'q1'"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        rule = Rule(1, expression, 2, {"q1": 0, "q10": 1}, priority=0)
    assert not caught
    assert rule.expression == expression
    assert rule.evaluate({"q1": "no", "q10": "q1"}) is True


def test_skip_rule_uses_q10_answer():
    questions = [
        QuestionFreeText(question_name=f"q{i}", question_text=f"Question {i}?")
        for i in range(12)
    ]
    with pytest.warns(UserWarning, match="old syntax"):
        survey = Survey(questions).add_skip_rule("q11", "q10 == 'yes'")
    assert list(survey.rule_collection)[-1].expression == "{{ q10.answer }} == 'yes'"
    for candidate in (survey, Survey.from_dict(survey.to_dict())):
        assert (
            candidate.next_question("q10", {"q1.answer": "no", "q10.answer": "yes"})
            == EndOfSurvey
        )
        assert (
            candidate.next_question(
                "q10", {"q1.answer": "yes", "q10.answer": "no"}
            ).question_name
            == "q11"
        )
