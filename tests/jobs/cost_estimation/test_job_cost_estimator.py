import pytest
from edsl.jobs import Jobs
from edsl.language_models import Model
from edsl.questions import QuestionFreeText, QuestionMultipleChoice
from edsl.questions.question_functional import QuestionFunctional
from edsl.surveys import Survey
from edsl.jobs.cost_estimation.job_cost_estimator import JobCostEstimator
from edsl.jobs.cost_estimation.question_token_estimate import QuestionTokenEstimate


# Price lookup that avoids live network calls. One USD buys one token for both
# input and output, so cost_usd == total_tokens — easy to reason about in tests.
PRICE_LOOKUP = {
    ("test", "test"): {
        "input": {
            "service": "test",
            "model": "test",
            "mode": "regular",
            "token_type": "input",
            "service_stated_token_qty": 1,
            "service_stated_token_price": 1,
            "one_usd_buys": 1,
        },
        "output": {
            "service": "test",
            "model": "test",
            "mode": "regular",
            "token_type": "output",
            "service_stated_token_qty": 1,
            "service_stated_token_price": 1,
            "one_usd_buys": 1,
        },
    }
}


def make_job(*questions):
    m = Model("test", canned_response="SPAM!")
    s = Survey(questions=list(questions))
    return Jobs(survey=s, models=[m])


# ------------------------------------------------------------------


class TestBasicEstimate:
    """Single-question job produces one row with a positive cost."""

    def test_one_row_per_question(self):
        job = make_job(
            QuestionFreeText(question_name="q0", question_text="What is your name?")
        )
        result = JobCostEstimator().estimate_cost(job, price_lookup=PRICE_LOOKUP)
        assert result.num_questions == 1

    def test_cost_is_positive_for_billable_question(self):
        job = make_job(
            QuestionFreeText(question_name="q0", question_text="What is your name?")
        )
        result = JobCostEstimator().estimate_cost(job, price_lookup=PRICE_LOOKUP)
        assert result.total_cost_usd > 0

    def test_row_has_expected_columns(self):
        job = make_job(
            QuestionFreeText(question_name="q0", question_text="What is your name?")
        )
        result = JobCostEstimator().estimate_cost(job, price_lookup=PRICE_LOOKUP)
        row = result._rows[0]
        for col in [
            "question_name",
            "model",
            "inference_service",
            "estimator_used",
            "reach_probability",
            "prompt_tokens",
            "answer_tokens",
            "cost_usd",
            "billable",
        ]:
            assert col in row, f"Missing column: {col}"


class TestBillable:
    """Functional questions have tokens (for memory) but zero cost."""

    def test_functional_cost_is_zero(self):
        func = lambda scenario, agent, model: 42  # noqa: E731
        q = QuestionFunctional(question_name="q0", question_text="Compute something.", func=func)
        result = JobCostEstimator().estimate_cost(make_job(q), price_lookup=PRICE_LOOKUP)
        assert result._rows[0]["cost_usd"] == 0.0

    def test_functional_tokens_still_estimated(self):
        """Tokens are tracked even when cost is zero — downstream memory needs them."""
        func = lambda scenario, agent, model: 42  # noqa: E731
        q = QuestionFunctional(question_name="q0", question_text="Compute something.", func=func)
        result = JobCostEstimator().estimate_cost(make_job(q), price_lookup=PRICE_LOOKUP)
        row = result._rows[0]
        assert row["total_input_tokens"] > 0 or row["answer_tokens"] > 0


class TestTokenOverrides:
    """token_overrides replaces only the specified fields; others come from the estimator."""

    def test_override_answer_tokens(self):
        q = QuestionFreeText(question_name="q0", question_text="What is your name?")
        override = {"q0": QuestionTokenEstimate(answer_tokens=9999)}
        result = JobCostEstimator().estimate_cost(
            make_job(q), token_overrides=override, price_lookup=PRICE_LOOKUP
        )
        assert result._rows[0]["answer_tokens"] == 9999

    def test_non_overridden_fields_unchanged(self):
        q = QuestionFreeText(question_name="q0", question_text="What is your name?")
        baseline = JobCostEstimator().estimate_cost(
            make_job(q), price_lookup=PRICE_LOOKUP
        )
        override = {"q0": QuestionTokenEstimate(answer_tokens=9999)}
        overridden = JobCostEstimator().estimate_cost(
            make_job(q), token_overrides=override, price_lookup=PRICE_LOOKUP
        )
        # prompt_tokens should be the same — only answer_tokens was overridden
        assert (
            baseline._rows[0]["prompt_tokens"] == overridden._rows[0]["prompt_tokens"]
        )


class TestBranchWeights:
    """branch_weights adjusts reach probabilities and changes which warning is emitted."""

    def test_no_branch_weights_emits_linear_warning(self):
        job = make_job(QuestionFreeText(question_name="q0", question_text="Hello?"))
        result = JobCostEstimator().estimate_cost(job, price_lookup=PRICE_LOOKUP)
        assert any(
            "skip logic" in w.lower() or "linear" in w.lower() for w in result.warnings
        )

    def test_branch_weights_emits_expected_cost_warning(self):
        q0 = QuestionFreeText(question_name="q0", question_text="Q0?")
        q1 = QuestionFreeText(question_name="q1", question_text="Q1?")
        result = JobCostEstimator().estimate_cost(
            make_job(q0, q1),
            branch_weights={("q0", "q1"): 0.5},
            price_lookup=PRICE_LOOKUP,
        )
        assert any(
            "branch_weights" in w.lower() or "reach" in w.lower()
            for w in result.warnings
        )

    def test_skipped_question_has_lower_reach(self):
        q0 = QuestionFreeText(question_name="q0", question_text="Q0?")
        q1 = QuestionFreeText(question_name="q1", question_text="Q1?")
        q2 = QuestionFreeText(question_name="q2", question_text="Q2?")
        result = JobCostEstimator().estimate_cost(
            make_job(q0, q1, q2),
            branch_weights={("q0", "q2"): 1.0},
            price_lookup=PRICE_LOOKUP,
        )
        rows = {r["question_name"]: r for r in result._rows}
        assert rows["q1"]["reach_probability"] == 0.0


class TestMemory:
    """Questions that include prior answers in their prompt get memory_tokens > 0."""

    def test_memory_tokens_added_for_downstream_question(self):
        q0 = QuestionFreeText(question_name="q0", question_text="What is your name?")
        q1 = QuestionFreeText(
            question_name="q1", question_text="Why did you say {{ q0.answer }}?"
        )
        s = Survey(questions=[q0, q1]).add_targeted_memory("q1", "q0")
        m = Model("test", canned_response="SPAM!")
        job = Jobs(survey=s, models=[m])
        result = JobCostEstimator().estimate_cost(job, price_lookup=PRICE_LOOKUP)
        rows = {r["question_name"]: r for r in result._rows}
        assert rows["q1"]["memory_tokens"] > 0


class TestAssumptions:
    """assumptions dict reflects the configuration used for the estimate."""

    def test_chars_per_token_in_assumptions(self):
        job = make_job(QuestionFreeText(question_name="q0", question_text="Hello?"))
        result = JobCostEstimator(chars_per_token=8).estimate_cost(
            job, price_lookup=PRICE_LOOKUP
        )
        assert result.assumptions["chars_per_token"] == 8

    def test_token_overrides_listed_in_assumptions(self):
        q = QuestionFreeText(question_name="q0", question_text="Hello?")
        override = {"q0": QuestionTokenEstimate(answer_tokens=50)}
        result = JobCostEstimator().estimate_cost(
            make_job(q), token_overrides=override, price_lookup=PRICE_LOOKUP
        )
        assert "q0" in result.assumptions["token_overrides_applied"]

    def test_branch_weights_flag_in_assumptions(self):
        q0 = QuestionFreeText(question_name="q0", question_text="Q0?")
        q1 = QuestionFreeText(question_name="q1", question_text="Q1?")
        result = JobCostEstimator().estimate_cost(
            make_job(q0, q1),
            branch_weights={("q0", "q1"): 0.5},
            price_lookup=PRICE_LOOKUP,
        )
        assert result.assumptions["branch_weights_applied"] is True
