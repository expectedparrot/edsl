"""Opt-in live OpenAI integration test for scale direction randomization.

Run with OPENAI_API_KEY set:
    EDSL_RUN_LIVE_OPENAI_TEST=1 pytest -q tests/runner/test_scale_direction_randomization_live.py
"""

import os

import pytest

from edsl import Model, ModelList, QuestionLinearScale, Survey


@pytest.mark.skipif(
    os.environ.get("EDSL_RUN_LIVE_OPENAI_TEST") != "1",
    reason="Set EDSL_RUN_LIVE_OPENAI_TEST=1 to make live OpenAI calls.",
)
def test_scale_direction_randomization_with_live_openai():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or api_key == "a_fake_key":
        pytest.skip("Set a real OPENAI_API_KEY to make live OpenAI calls.")

    question = QuestionLinearScale(
        question_name="satisfaction",
        question_text="How satisfied are you with the service?",
        question_options=[1, 2, 3, 4, 5],
        option_labels={1: "Very dissatisfied", 5: "Very satisfied"},
    )
    survey = Survey([question]).randomize_scale_direction("satisfaction")
    models = ModelList([Model("gpt-4o-mini"), Model("gpt-4o-mini")])

    results = survey.by(models).run(
        n=2,
        offload_execution=False,
        disable_remote_inference=True,
        use_api_proxy=False,
        cache=False,
        progress_bar=False,
        stop_on_exception=True,
    )

    rows = results.select(
        "answer.satisfaction",
        "question_options.satisfaction",
        "randomization.scale_directions",
        "randomization.scale_direction_assignment_id",
    ).to_list()
    assert len(rows) == 4
    for row in rows:
        answer = row["answer.satisfaction"]
        assert isinstance(answer, int) and 1 <= answer <= 5
        direction = row["randomization.scale_directions"]["satisfaction"]
        options = row["question_options.satisfaction"]
        expected_options = (
            [1, 2, 3, 4, 5] if direction == "forward" else [5, 4, 3, 2, 1]
        )
        assert options == expected_options

    directions_by_assignment = {}
    for row in rows:
        assignment_id = row["randomization.scale_direction_assignment_id"]
        direction = row["randomization.scale_directions"]["satisfaction"]
        directions_by_assignment.setdefault(assignment_id, set()).add(direction)
    assert len(directions_by_assignment) == 2
    assert all(len(directions) == 1 for directions in directions_by_assignment.values())
