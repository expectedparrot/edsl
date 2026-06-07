import pytest
from edsl.jobs import Jobs
from edsl.language_models import Model
from edsl.questions import QuestionFreeText
from edsl.questions.question_compute import QuestionCompute
from edsl.surveys import Survey
from edsl.jobs.cost_estimation.job_cost_estimator import JobCostEstimator
from edsl.jobs.cost_estimation.question_token_estimate import QuestionTokenEstimate
from edsl.jobs.cost_estimation.token_override import TokenOverride


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

    def test_compute_cost_is_zero(self):
        q = QuestionCompute(
            question_name="q0",
            question_text="Your lucky number is {{ [1,2,3,4,5,6,7,8,9,10] | random }}.",
        )
        result = JobCostEstimator().estimate_cost(
            make_job(q), price_lookup=PRICE_LOOKUP
        )
        assert result._rows[0]["cost_usd"] == 0.0

    def test_compute_tokens_still_estimated(self):
        """Tokens are tracked even when cost is zero — downstream memory needs them."""
        q = QuestionCompute(
            question_name="q0",
            question_text="Your lucky number is {{ [1,2,3,4,5,6,7,8,9,10] | random }}.",
        )
        result = JobCostEstimator().estimate_cost(
            make_job(q), price_lookup=PRICE_LOOKUP
        )
        row = result._rows[0]
        assert row["total_input_tokens"] > 0 or row["answer_tokens"] > 0


class TestTokenOverrides:
    """token_overrides replaces only the specified fields; others come from the estimator."""

    def test_override_answer_tokens(self):
        q = QuestionFreeText(question_name="q0", question_text="What is your name?")
        override = {"q0": TokenOverride(answer_tokens=9999)}
        result = JobCostEstimator().estimate_cost(
            make_job(q), token_overrides=override, price_lookup=PRICE_LOOKUP
        )
        assert result._rows[0]["answer_tokens"] == 9999

    def test_non_overridden_fields_unchanged(self):
        q = QuestionFreeText(question_name="q0", question_text="What is your name?")
        baseline = JobCostEstimator().estimate_cost(
            make_job(q), price_lookup=PRICE_LOOKUP
        )
        override = {"q0": TokenOverride(answer_tokens=9999)}
        overridden = JobCostEstimator().estimate_cost(
            make_job(q), token_overrides=override, price_lookup=PRICE_LOOKUP
        )
        assert (
            baseline._rows[0]["prompt_tokens"] == overridden._rows[0]["prompt_tokens"]
        )

    def test_override_description_reflects_override(self):
        q = QuestionFreeText(question_name="q0", question_text="What is your name?")
        override = {"q0": TokenOverride(answer_tokens=50)}
        result = JobCostEstimator().estimate_cost(
            make_job(q), token_overrides=override, price_lookup=PRICE_LOOKUP
        )
        assert result._rows[0]["override_description"] == "answer_tokens=50"

    def test_override_description_lists_all_set_fields(self):
        q = QuestionFreeText(question_name="q0", question_text="What is your name?")
        override = {"q0": TokenOverride(answer_tokens=50, comment_tokens=10)}
        result = JobCostEstimator().estimate_cost(
            make_job(q), token_overrides=override, price_lookup=PRICE_LOOKUP
        )
        assert (
            result._rows[0]["override_description"]
            == "answer_tokens=50, comment_tokens=10"
        )

    def test_override_note_appears_in_description(self):
        q = QuestionFreeText(question_name="q0", question_text="What is your name?")
        override = {"q0": TokenOverride(answer_tokens=50, note="from pilot")}
        result = JobCostEstimator().estimate_cost(
            make_job(q), token_overrides=override, price_lookup=PRICE_LOOKUP
        )
        assert "from pilot" in result._rows[0]["override_description"]

    def test_non_overridden_question_keeps_estimator_description(self):
        q0 = QuestionFreeText(question_name="q0", question_text="What is your name?")
        q1 = QuestionFreeText(
            question_name="q1", question_text="What is your favorite color?"
        )
        override = {"q0": TokenOverride(answer_tokens=50)}
        result = JobCostEstimator().estimate_cost(
            make_job(q0, q1), token_overrides=override, price_lookup=PRICE_LOOKUP
        )
        rows = {r["question_name"]: r for r in result._rows}
        assert rows["q0"]["override_description"] == "answer_tokens=50"
        assert not rows["q1"]["override_description"]

    def test_specific_model_override_wins_over_global(self):
        # make_job uses service="test", model="test"
        q = QuestionFreeText(question_name="q0", question_text="What is your name?")
        override = {
            "q0": [
                TokenOverride(answer_tokens=100),  # global
                TokenOverride(
                    answer_tokens=999, service="test", model="test"
                ),  # specific
            ]
        }
        result = JobCostEstimator().estimate_cost(
            make_job(q), token_overrides=override, price_lookup=PRICE_LOOKUP
        )
        assert result._rows[0]["answer_tokens"] == 999

    def test_global_override_applies_when_no_specific_match(self):
        q = QuestionFreeText(question_name="q0", question_text="What is your name?")
        override = {
            "q0": [
                TokenOverride(answer_tokens=100),  # global
                TokenOverride(
                    answer_tokens=999, service="other", model="other"
                ),  # non-matching
            ]
        }
        result = JobCostEstimator().estimate_cost(
            make_job(q), token_overrides=override, price_lookup=PRICE_LOOKUP
        )
        assert result._rows[0]["answer_tokens"] == 100

    def test_no_match_leaves_estimate_unchanged(self):
        q = QuestionFreeText(question_name="q0", question_text="What is your name?")
        baseline = JobCostEstimator().estimate_cost(
            make_job(q), price_lookup=PRICE_LOOKUP
        )
        override = {
            "q0": TokenOverride(answer_tokens=999, service="other", model="other")
        }
        result = JobCostEstimator().estimate_cost(
            make_job(q), token_overrides=override, price_lookup=PRICE_LOOKUP
        )
        assert result._rows[0]["answer_tokens"] == baseline._rows[0]["answer_tokens"]


class TestBranchWeights:
    """branch_weights adjusts reach probabilities and changes which warning is emitted."""

    def test_skip_logic_survey_without_branch_weights_warns(self):
        q0 = QuestionFreeText(question_name="q0", question_text="Q0?")
        q1 = QuestionFreeText(question_name="q1", question_text="Q1?")
        q2 = QuestionFreeText(question_name="q2", question_text="Q2?")
        s = Survey(questions=[q0, q1, q2]).add_rule(
            "q0", "{{ q0.answer }} == 'yes'", "q2"
        )
        m = Model("test", canned_response="SPAM!")
        job = Jobs(survey=s, models=[m])
        result = JobCostEstimator().estimate_cost(job, price_lookup=PRICE_LOOKUP)
        assert any("skip logic" in w.lower() for w in result.warnings)

    def test_linear_survey_without_branch_weights_no_skip_warning(self):
        job = make_job(QuestionFreeText(question_name="q0", question_text="Hello?"))
        result = JobCostEstimator().estimate_cost(job, price_lookup=PRICE_LOOKUP)
        assert not any("skip logic" in w.lower() for w in result.warnings)

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

    def test_memory_tokens_weighted_by_reach_of_prior_question(self):
        # When branch_weights give a prior question reach < 1, its contribution
        # to downstream memory should scale linearly with that reach.
        #
        # Survey: q0 --(50% skip)--> q2; default path q0->q1->q2.
        # q1 reach = 0.5. q2 has memory of q1, pinned to 1000 output tokens.
        # Expected memory contribution from q1: int(0.5 * 1000) = 500.
        q0 = QuestionFreeText(question_name="q0", question_text="Q0?")
        q1 = QuestionFreeText(question_name="q1", question_text="Q1?")
        q2 = QuestionFreeText(question_name="q2", question_text="Q2?")
        s = (
            Survey(questions=[q0, q1, q2])
            .add_rule("q0", "True", "q2")  # creates the skip rule
            .add_targeted_memory("q2", "q1")
        )
        m = Model("test", canned_response="SPAM!")
        job = Jobs(survey=s, models=[m])
        overrides = {
            "q1": TokenOverride(answer_tokens=1000, comment_tokens=0, thinking_tokens=0)
        }
        result = JobCostEstimator().estimate_cost(
            job,
            token_overrides=overrides,
            branch_weights={("q0", "q2"): 0.5},
            price_lookup=PRICE_LOOKUP,
        )
        rows = {r["question_name"]: r for r in result._rows}
        assert rows["q1"]["reach_probability"] == 0.5
        assert rows["q2"]["memory_tokens"] == 500
