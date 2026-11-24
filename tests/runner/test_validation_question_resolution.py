"""The question an answer is validated against must match the one prompted."""

import pytest

from edsl import Cache, Model, QuestionDemand, QuestionList, Scenario, Survey
from edsl.runner.question_resolution import resolve_question_data


def _run(survey, scenario, canned):
    model = Model("test")
    model.canned_response = canned
    return (
        survey.by(scenario)
        .by(model)
        .run(
            disable_remote_inference=True,
            disable_remote_cache=True,
            cache=Cache(),
            print_exceptions=False,
        )
    )


def test_demand_prices_piped_from_a_prior_list_answer():
    survey = Survey(
        [
            QuestionList(
                question_name="price_grid",
                question_text="Give three prices.",
                max_list_items=3,
            ),
            QuestionDemand(
                question_name="demand",
                question_text="How many would you buy?",
                prices="{{ price_grid.answer }}",
            ),
        ]
    )
    results = _run(
        survey,
        Scenario(),
        {"price_grid": "[1, 2, 3]", "demand": "[5, 3, 1]"},
    )

    assert results.select("answer.demand").to_list() == [
        [{"$1.00": 5.0}, {"$2.00": 3.0}, {"$3.00": 1.0}]
    ]


def test_demand_prices_given_as_text_are_coerced_to_numbers():
    survey = Survey(
        [
            QuestionDemand(
                question_name="demand",
                question_text="How many would you buy?",
                prices="{{ scenario.prices }}",
            )
        ]
    )
    results = _run(
        survey, Scenario({"prices": ["1", "2.5", "3"]}), {"demand": "[5, 3, 1]"}
    )

    assert results.select("answer.demand").to_list() == [
        [{"$1.00": 5.0}, {"$2.50": 3.0}, {"$3.00": 1.0}]
    ]


def test_unresolved_demand_prices_raise_a_clear_error():
    with pytest.raises(ValueError, match="must resolve to a list of numbers"):
        resolve_question_data(
            {"question_name": "demand", "prices": "{{ price_grid.answer }}"},
            answer_dict={},
            scenario=None,
        )
    with pytest.raises(ValueError, match="must resolve to a list of numbers"):
        resolve_question_data(
            {"question_name": "demand", "prices": "{{ scenario.prices }}"},
            answer_dict={},
            scenario={"prices": ["$1", "$2"]},
        )


def test_applies_option_permutation_item_seed_and_numeric_bounds():
    question_data = {
        "question_name": "q",
        "question_options": ["a", "b", "{{ pick.answer }}"],
        "question_items": ["x", "y", "z"],
        "randomize_items": True,
        "min_value": "{{ scenario.low }}",
    }

    resolved = resolve_question_data(
        question_data,
        answer_dict={"pick": "c"},
        scenario={"low": 2},
        option_permutation=["{{ pick.answer }}", "b", "a"],
        item_randomization_seed=7,
    )

    assert resolved["question_options"] == ["c", "b", "a"]
    assert sorted(resolved["question_items"]) == ["x", "y", "z"]
    assert resolved["question_items"] == resolve_question_data(
        question_data, {"pick": "c"}, {"low": 2}, item_randomization_seed=7
    )["question_items"]
    assert resolved["min_value"] == 2
    assert question_data["question_options"] == ["a", "b", "{{ pick.answer }}"]


def test_static_question_is_returned_unchanged():
    question_data = {"question_name": "q", "question_options": ["a", "b"]}

    assert resolve_question_data(question_data, {}, None) is question_data
