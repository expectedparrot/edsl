import json
import math

import pytest

from edsl import Question, QuestionDistribution, Survey
from edsl.questions import QuestionBase
from edsl.questions.exceptions import (
    QuestionAnswerValidationError,
    QuestionCreationValidationError,
)


def make(**kwargs):
    return QuestionDistribution("forecast", "Predict the outcome.", **kwargs)


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({"question_options": ["a", "b", "c"]}, ("a", "b", "c")),
        ({"bins": ["[0,10)", "[10, Inf]"], "min_value": 0}, ("[0,10)", "[10,Inf)")),
        ({"bins": ["(-Infinity,0)", "[0,Inf)"]}, ("(-Inf,0)", "[0,Inf)")),
        ({"bins": ["[0,10]", "(10,20]"]}, ("[0,10]", "(10,20]")),
        ({"bins": ["[-0.0, 1e1]", "(10.00,20]"]}, ("[0,10]", "(10,20]")),
        (
            {"min_value": 0, "max_value": 25, "bucket_size": 10},
            ("[0,10)", "[10,20)", "[20,25]"),
        ),
        (
            {"min_value": 0, "max_value": 0.3, "bucket_size": 0.1},
            ("[0,0.1)", "[0.1,0.2)", "[0.2,0.3]"),
        ),
        ({"min_value": -10, "max_value": 10, "bucket_size": 10}, ("[-10,0)", "[0,10]")),
        ({"min_value": 0, "max_value": 10, "bucket_size": 20}, ("[0,10]",)),
        ({"bins": ["(-Inf,Inf)"]}, ("(-Inf,Inf)",)),
    ],
)
def test_construction_and_round_trip(kwargs, expected):
    q = make(**kwargs)
    assert q.answer_keys == expected
    serialized = json.loads(json.dumps(q.to_dict(), allow_nan=False))
    restored = QuestionBase.from_dict(serialized)
    assert restored == q
    assert restored.answer_keys == expected
    assert q.render({}).answer_keys == expected
    assert not ({"bins", "bucket_size"} <= serialized.keys())
    assert "answer_keys" not in serialized
    assert q.resolved_bins == (None if "question_options" in kwargs else expected)


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"question_options": []},
        {"question_options": "abc"},
        {"question_options": ["a", "a"]},
        {"question_options": ["a", " a"]},
        {"question_options": ["a", 1]},
        {"question_options": ["{{ a }}"]},
        {"question_options": ["{% x %}"]},
        {"question_options": [""]},
        {"question_options": ["a"], "min_value": 0},
        {"question_options": ["a"], "bins": ["[0,1]"]},
        {"bins": []},
        {"bins": ["[0,1]"], "bucket_size": 1},
        {"bins": ["[0,10)", "[11,20]"]},
        {"bins": ["[0,10]", "[10,20]"]},
        {"bins": ["[0,10)", "(10,20]"]},
        {"bins": ["[10,20)", "[0,10]"]},
        {"bins": ["[0,10)", "[5,20]"]},
        {"bins": ["[0,0]"]},
        {"bins": ["[10,0]"]},
        {"bins": ["(0,10]"]},
        {"bins": ["[0,10)"]},
        {"bins": ["[0,NaN]"]},
        {"bins": ["[0,1+2]"]},
        {"bins": ["[0,{{ x }}]"]},
        {"bins": ["[Inf,Inf]"]},
        {"bins": ["[0,10]"], "max_value": 20},
        {"bins": ["[0,10]"], "min_value": "0"},
        {"min_value": 0, "max_value": 10},
        {"min_value": 0, "max_value": 10, "bucket_size": 0},
        {"min_value": 0, "max_value": 10, "bucket_size": -1},
        {"min_value": 10, "max_value": 10, "bucket_size": 1},
        {"min_value": 0, "max_value": math.inf, "bucket_size": 1},
        {"min_value": False, "max_value": 10, "bucket_size": 1},
        {"min_value": 0, "max_value": 10, "bucket_size": math.nan},
        {"min_value": 0, "max_value": 1001, "bucket_size": 1},
        {"question_options": [str(i) for i in range(1001)]},
    ],
)
def test_invalid_construction(kwargs):
    with pytest.raises(QuestionCreationValidationError):
        make(**kwargs)


@pytest.mark.parametrize("tolerance", [-1, 0.01, math.nan, math.inf, True, "0.001"])
def test_invalid_tolerance(tolerance):
    with pytest.raises(QuestionCreationValidationError):
        make(question_options=["a"], tolerance=tolerance)


@pytest.mark.parametrize(
    "answer",
    [
        {"a": 0.2, "b": 0.8},
        {"a": 0.2, "b": 0.2, "c": 0.6, "d": 0},
        {"a": -0.1, "b": 0.5, "c": 0.6},
        {"a": 1.1, "b": 0, "c": 0},
        {"a": True, "b": 0, "c": 0},
        {"a": "0.2", "b": 0.2, "c": 0.6},
        {"a": None, "b": 0.2, "c": 0.8},
        {"a": math.nan, "b": 0, "c": 1},
        {"a": math.inf, "b": 0, "c": 0},
        {"a": 20, "b": 20, "c": 60},
        {"a": 0.2, "b": 0.2, "c": 0.5},
        [0.2, 0.2, 0.6],
        [{"a": 0.2}, {"b": 0.2}, {"c": 0.6}],
        None,
    ],
)
def test_invalid_answers(answer):
    with pytest.raises(QuestionAnswerValidationError):
        QuestionDistribution.example()._validate_answer({"answer": answer})


def test_order_tolerance_and_no_repair():
    q = QuestionDistribution.example()
    answer = q._validate_answer({"answer": {"c": 0.6000001, "b": 0.2, "a": 0.2}})[
        "answer"
    ]
    assert list(answer) == ["a", "b", "c"]
    assert answer["c"] == 0.6000001
    assert math.fsum(answer.values()) != 1
    with pytest.raises(QuestionAnswerValidationError, match="sum to 1"):
        q._validate_answer({"answer": {"a": 0.2, "b": 0.2, "c": 0.60001}})
    assert make(question_options=["a"], tolerance=0)._validate_answer(
        {"answer": {"a": 1}}
    )["answer"] == {"a": 1}


@pytest.mark.parametrize(
    "raw",
    [
        '{"a":0.1,"a":0.2,"b":0.2,"c":0.6}',
        '{"a":"0.2","b":0.2,"c":0.6}',
        '{"a":0.2,"b":0.2,"c":0.5}',
        '{"a":0.2,"b":0.2,"c":NaN}',
        "{'a':0.2,'b':0.2,'c':0.6}",
    ],
)
def test_original_json_cannot_be_silently_repaired(raw):
    # The generic parser may already have repaired/discarded invalid content.
    with pytest.raises(QuestionAnswerValidationError):
        QuestionDistribution.example()._validate_answer(
            {
                "answer": {"a": 0.2, "b": 0.2, "c": 0.6},
                "generated_tokens": raw,
            }
        )


def test_multiline_json_and_comments():
    raw = '```json\n{\n"c":0.6,\n"a":0.2,\n"b":0.2\n}\n```\nCOMMENT: Explanation.'
    result = QuestionDistribution.example()._validate_answer(
        {"answer": {}, "generated_tokens": raw}
    )
    assert result["answer"] == {"a": 0.2, "b": 0.2, "c": 0.6}
    assert result["comment"] == "Explanation."


def test_configuration_is_not_mutated_through_public_properties():
    options = ["a", "b"]
    q = make(question_options=options)
    options.append("c")
    q.question_options.append("c")
    assert q.answer_keys == ("a", "b")
    with pytest.raises(AttributeError):
        q.answer_keys = ("c",)
    with pytest.raises(AttributeError):
        q.bucket_size = 4


def test_registration_prompts_html_and_randomization():
    q = Question(
        "distribution",
        question_name="x",
        question_text="Predict.",
        bins=["[0,10)", "[10,Inf]"],
    )
    assert isinstance(q, QuestionDistribution)
    prompt = q.prompt_preview().text
    assert "[10,Inf)" in prompt and "not a density height" in prompt
    assert "sum must be 1" in prompt
    q.include_comment = False
    assert "COMMENT:" not in q.prompt_preview().text
    html = make(question_options=['<script>alert("x")</script>']).question_html_content
    assert "&lt;script&gt;" in html and '<script>alert("x")' not in html
    with pytest.raises(Exception, match="does not support option randomization"):
        Survey([q], questions_to_randomize=["x"])


@pytest.mark.parametrize("kwargs", [
    {"question_options": ["a", 'b "quoted"', "c"]},
    {"bins": ["[0,10)", "[10, Inf]"]},
    {"min_value": 0, "max_value": 25, "bucket_size": 10},
])
def test_human_readable_describes_complete_probability_allocation(kwargs):
    question = make(tolerance=0.00001, **kwargs)
    text = question.human_readable()
    assert text.startswith("Question Type: distribution\nQuestion: Predict the outcome.")
    assert "Allocate probability across every outcome" in text
    assert "JSON object mapping every exact label" in text
    assert "including zero-probability outcomes" in text
    assert "from 0 to 1, not percentages" in text
    assert f"sum to 1 within a tolerance of {question.tolerance}" in text
    assert "Please name the option you choose" not in text
    for key in question.answer_keys:
        assert json.dumps(key, ensure_ascii=False) in text.splitlines()
    assert ("not a density height" in text) == (question.resolved_bins is not None)


def test_explicit_infinite_bounds_use_strict_json():
    q = make(bins=["(-Inf,Inf)"], min_value=-math.inf, max_value=math.inf)
    data = json.loads(json.dumps(q.to_dict(), allow_nan=False))
    assert data["min_value"] == "-Inf" and data["max_value"] == "Inf"
    assert QuestionBase.from_dict(data).resolved_bins == ("(-Inf,Inf)",)


def test_response_schema_exposes_required_probabilities():
    schema = QuestionDistribution.example().response_model.model_json_schema()[
        "properties"
    ]["answer"]
    assert schema["required"] == ["a", "b", "c"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["a"]["maximum"] == 1


def test_extreme_endpoints_remain_compact_and_roundtrip():
    q = make(bins=["[-1e1000000,0)", "[0,1.00e1000000]"])
    assert q.answer_keys == ("[-1e1000000,0)", "[0,1e1000000]")
    assert q.duplicate() == q


def test_public_repr_and_randomization_rejection():
    q = make(bins=["[0,Inf)"])
    assert eval(str(q), {"Question": Question}) == q
    assert q.question_options == ["[0,Inf)"]
    with pytest.raises(QuestionCreationValidationError, match="randomization"):
        q.draw()
