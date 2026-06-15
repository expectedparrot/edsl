from types import SimpleNamespace
from edsl.jobs.cost_estimation.question_estimators import (
    QuestionEstimator,
    FreeTextStyleEstimator,
    StructuredAnswerEstimator,
    ZeroCostEstimator,
)
from edsl.jobs.cost_estimation.cost_estimation_constants import TokenAmount


# ------------------------------------------------------------------
# Fixtures


def make_prompts(user="", system=""):
    return {"user_prompt": user, "system_prompt": system}


def make_question(question_type, question_name="q0", options=None):
    q = SimpleNamespace(question_type=question_type, question_name=question_name)
    if options is not None:
        q.question_options = options
    return q


# ------------------------------------------------------------------
# Tests


class TestDispatch:
    """QuestionEstimator routes each question_type to the right estimator."""

    def test_registered_type_produces_no_warnings(self):
        estimator = QuestionEstimator()
        q = make_question("multiple_choice", options=["A", "B"])
        _, warnings = estimator.estimate(q, make_prompts())
        assert warnings == []

    def test_unregistered_type_uses_default_and_warns(self):
        """Unknown types fall through to DefaultEstimator and emit a warning."""
        estimator = QuestionEstimator()
        q = make_question("mystery_type")
        result, warnings = estimator.estimate(q, make_prompts(user="x" * 400))
        assert len(warnings) == 1
        assert "mystery_type" in warnings[0]
        assert "q0" in warnings[0]
        # DefaultEstimator: answer ≈ prompt
        assert result.answer_tokens == result.prompt_tokens

    def test_compute_is_not_billable(self):
        estimator = QuestionEstimator()
        result, _ = estimator.estimate(make_question("compute"), make_prompts())
        assert result.billable is False

    def test_functional_is_not_billable(self):
        estimator = QuestionEstimator()
        result, _ = estimator.estimate(make_question("functional"), make_prompts())
        assert result.billable is False

    def test_interview_uses_fixed_token_amount(self):
        """interview answer is always 500 tokens regardless of prompt length."""
        estimator = QuestionEstimator()
        result, _ = estimator.estimate(
            make_question("interview"), make_prompts(user="x" * 400)
        )
        assert result.answer_tokens == 500

    def test_free_text_answer_scales_with_prompt(self):
        # 400 chars / 4 = 100 prompt tokens; free_text uses TokenRatio(1.0)
        estimator = QuestionEstimator()
        result, _ = estimator.estimate(
            make_question("free_text"), make_prompts(user="x" * 400)
        )
        assert result.answer_tokens == result.prompt_tokens


class TestOverrides:
    """The overrides kwarg replaces specific types without touching the rest."""

    def test_override_replaces_target_type(self):
        custom = FreeTextStyleEstimator(output=TokenAmount(999))
        estimator = QuestionEstimator(overrides={"free_text": custom})
        result, _ = estimator.estimate(
            make_question("free_text"), make_prompts(user="x" * 400)
        )
        assert result.answer_tokens == 999

    def test_override_leaves_other_types_unchanged(self):
        custom = FreeTextStyleEstimator(output=TokenAmount(999))
        estimator = QuestionEstimator(overrides={"free_text": custom})
        result, _ = estimator.estimate(
            make_question("multiple_choice", options=["A", "B"]), make_prompts()
        )
        # multiple_choice is unaffected — uses StructuredAnswerEstimator defaults
        assert result.comment_tokens == 60


class TestCharsPerTokenOverrides:
    """chars_per_token_overrides only reports types that deviate from the top-level setting."""

    def test_no_overrides_by_default(self):
        estimator = QuestionEstimator(chars_per_token=4)
        assert estimator.chars_per_token_overrides == {}

    def test_reports_deviating_type(self):
        custom = ZeroCostEstimator(chars_per_token=8)
        estimator = QuestionEstimator(overrides={"compute": custom}, chars_per_token=4)
        overrides = estimator.chars_per_token_overrides
        assert "compute" in overrides
        assert overrides["compute"] == 8

    def test_matching_type_not_reported(self):
        custom = ZeroCostEstimator(chars_per_token=4)
        estimator = QuestionEstimator(overrides={"compute": custom}, chars_per_token=4)
        assert "compute" not in estimator.chars_per_token_overrides
