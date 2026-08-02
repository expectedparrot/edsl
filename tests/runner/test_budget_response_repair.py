"""Regression coverage for budget repair using only the local test model."""

import pytest

from edsl import Model, QuestionBudget


def test_budget_rounding_repair_runs_through_local_job_runner():
    question = QuestionBudget(
        question_name="allocation",
        question_text="Allocate 100 points.",
        question_options=["A", "B", "C", "D"],
        budget_sum=100,
    )
    model = Model("test", canned_response="[33.3, 33.3, 33.3, 0]")

    results = question.by(model).run(
        disable_remote_inference=True,
        disable_remote_cache=True,
        cache=False,
    )

    answer = results.select("answer.allocation").to_list()[0]
    assert [list(row) for row in answer] == [["A"], ["B"], ["C"], ["D"]]
    allocations = [next(iter(row.values())) for row in answer]
    assert sum(allocations) == 100
    assert allocations == pytest.approx([33.4, 33.3, 33.3, 0])
