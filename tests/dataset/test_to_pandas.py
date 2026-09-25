"""Pandas export must preserve structured answers unless strings are requested."""

import json
import sys

import pytest

from edsl import Dataset, Model, QuestionDict, QuestionList, QuestionMatrix, Survey
from edsl.base.exceptions import MissingOptionalDependencyError


pd = pytest.importorskip("pandas")


@pytest.mark.parametrize(
    "options", [{}, {"lists_as_strings": False}, {"lists_as_strings": True}]
)
@pytest.mark.parametrize("remove_prefix", [False, True])
def test_structured_values(options, remove_prefix):
    values = [["red", "blue"], {"colors": ["red", "blue"]}, [], {}, None]
    dataset = Dataset([{"answer.colors": values}, {"scenario.index": list(range(5))}])

    frame = dataset.to_pandas(remove_prefix=remove_prefix, **options)

    assert list(frame.columns) == (
        ["colors", "index"] if remove_prefix else ["answer.colors", "scenario.index"]
    )
    exported = frame.iloc[:, 0].tolist()
    expected = (
        [str(value) for value in values[:-1]]
        if options.get("lists_as_strings")
        else values[:-1]
    )
    assert exported[:-1] == expected
    assert pd.isna(exported[-1])
    assert frame.iloc[:, 1].tolist() == list(range(5))
    assert dataset.to_list()[0][0] == values[0]


def test_default_export_preserves_literal_strings():
    values = ["001", "NA", "", "True", "['red']", '{"red": 1}']
    frame = Dataset([{"answer.text": values}]).to_pandas()
    assert frame["answer.text"].tolist() == values


@pytest.mark.parametrize("lists_as_strings", [False, True])
@pytest.mark.parametrize(
    "data, columns", [([], []), ([{"answer.colors": []}], ["answer.colors"])]
)
def test_empty_export(lists_as_strings, data, columns):
    frame = Dataset(data).to_pandas(lists_as_strings=lists_as_strings)
    assert frame.empty
    assert list(frame.columns) == columns


def test_removing_prefixes_preserves_columns_with_same_name():
    dataset = Dataset([{"answer.value": [[1, 2]]}, {"scenario.value": [{"key": 3}]}])
    frame = dataset.to_pandas(remove_prefix=True)
    assert list(frame.columns) == ["value", "value"]
    assert frame.iloc[0, 0] == [1, 2]
    assert frame.iloc[0, 1] == {"key": 3}


@pytest.mark.parametrize("lists_as_strings", [False, True])
def test_missing_pandas_reports_optional_dependency(monkeypatch, lists_as_strings):
    monkeypatch.setitem(sys.modules, "pandas", None)
    with pytest.raises(MissingOptionalDependencyError, match="file-formats"):
        Dataset([{"answer.colors": [["red"]]}]).to_pandas(
            lists_as_strings=lists_as_strings
        )


@pytest.fixture(scope="module")
def structured_results():
    questions = [
        QuestionList(question_name="colors", question_text="Name two colors."),
        QuestionDict(
            question_name="profile",
            question_text="Give your name and age.",
            answer_keys=["name", "age"],
            value_types=["str", "int"],
        ),
        QuestionMatrix(
            question_name="ratings",
            question_text="Rate the colors.",
            question_items=["red", "blue"],
            question_options=[1, 2, 3],
        ),
    ]
    answers = {
        "colors": ["red", "blue"],
        "profile": {"name": "Ada", "age": 30},
        "ratings": {"red": 1, "blue": 3},
    }
    model = Model(
        "test",
        canned_response={name: json.dumps(value) for name, value in answers.items()},
    )
    results = (
        Survey(questions)
        .by(model)
        .run(disable_remote_inference=True, disable_remote_cache=True, cache=False)
    )
    return results, answers


@pytest.mark.parametrize(
    "options", [{}, {"lists_as_strings": False}, {"lists_as_strings": True}]
)
def test_results_export_preserves_question_answers(structured_results, options):
    results, answers = structured_results
    frame = results.to_pandas(**options)
    selected = results.select("answer.*").to_pandas(**options)
    for name, answer in answers.items():
        expected = str(answer) if options.get("lists_as_strings") else answer
        assert frame[f"answer.{name}"].iloc[0] == expected
        assert selected[f"answer.{name}"].iloc[0] == expected
        assert results.select(name).to_list()[0] == answer
