"""Regression coverage for budget repair using only the local test model."""

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
    assert sum(answer) == 100


def test_labeled_budget_string_repairs_through_local_job_runner():
    question = QuestionBudget(
        question_name="revenue_split",
        question_text="Allocate revenue.",
        question_options=["Product revenue %", "Advertising revenue %"],
        budget_sum=100,
    )
    model = Model(
        "test",
        canned_response="[Product revenue %: 50, Advertising revenue %: 50]",
    )

    results = question.by(model).run(
        disable_remote_inference=True,
        disable_remote_cache=True,
        cache=False,
    )

    assert results.select("answer.revenue_split").to_list() == [[50.0, 50.0]]
