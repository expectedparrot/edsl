from types import SimpleNamespace
from edsl.jobs.cost_estimation.question_estimators import (
    ZeroCostEstimator,
    FreeTextStyleEstimator,
    StructuredAnswerEstimator,
    DemandEstimator,
    MatrixEstimator,
    DefaultEstimator,
)
from edsl.jobs.cost_estimation.cost_estimation_constants import TokenAmount, TokenRatio


# ------------------------------------------------------------------
# Fixtures


def make_prompts(user="", system=""):
    return {"user_prompt": user, "system_prompt": system}


def make_question(options=None, prices=None, items=None):
    """Minimal question stand-in with only the attributes estimators read."""
    q = SimpleNamespace()
    if options is not None:
        q.question_options = options
    if prices is not None:
        q.prices = prices
    if items is not None:
        q.question_items = items
    return q


# ------------------------------------------------------------------
# ZeroCostEstimator


class TestZeroCostEstimator:
    """For compute/functional questions — no LLM call, so cost is zero but tokens are tracked for memory."""

    def test_billable_is_false(self):
        result = ZeroCostEstimator()(make_question(), make_prompts())
        assert result.billable is False

    def test_answer_tokens_positive(self):
        result = ZeroCostEstimator()(make_question(), make_prompts(user="x" * 100))
        assert result.answer_tokens > 0

    def test_comment_tokens_zero(self):
        result = ZeroCostEstimator()(make_question(), make_prompts(user="x" * 100))
        assert result.comment_tokens == 0

    def test_answer_token_amount(self):
        """Fixed answer spec ignores prompt length."""
        result = ZeroCostEstimator(answer=TokenAmount(42))(
            make_question(), make_prompts(user="x" * 400)
        )
        assert result.answer_tokens == 42

    def test_answer_token_ratio(self):
        """Ratio answer spec scales with prompt length."""
        # 400 chars / 4 chars_per_token = 100 prompt tokens; ratio 0.5 → 50
        result = ZeroCostEstimator(answer=TokenRatio(0.5))(
            make_question(), make_prompts(user="x" * 400)
        )
        assert result.answer_tokens == 50


# ------------------------------------------------------------------
# FreeTextStyleEstimator


class TestFreeTextStyleEstimator:
    """For open-ended answer types — all output goes into answer_tokens, no comment field."""

    def test_comment_tokens_zero(self):
        result = FreeTextStyleEstimator()(make_question(), make_prompts(user="x" * 100))
        assert result.comment_tokens == 0

    def test_ratio_output_scales_with_prompt(self):
        # 400 chars / 4 = 100 prompt tokens; ratio 1.0 → answer ≈ 100
        result = FreeTextStyleEstimator(output=TokenRatio(1.0))(
            make_question(), make_prompts(user="x" * 400)
        )
        assert result.answer_tokens == result.prompt_tokens

    def test_fixed_output_ignores_prompt(self):
        result = FreeTextStyleEstimator(output=TokenAmount(500))(
            make_question(), make_prompts(user="x" * 400)
        )
        assert result.answer_tokens == 500

    def test_answer_tokens_at_least_one(self):
        """Even with a tiny prompt and small ratio, answer_tokens is >= 1."""
        result = FreeTextStyleEstimator(output=TokenRatio(0.001))(
            make_question(), make_prompts(user="x")
        )
        assert result.answer_tokens >= 1


# ------------------------------------------------------------------
# StructuredAnswerEstimator


class TestStructuredAnswerEstimator:
    """For questions with a fixed set of options — answer comes from option text length, comment is flat."""

    def test_answer_tokens_from_options(self):
        # options average 8 chars each; 8 / 4 chars_per_token = 2 tokens
        q = make_question(options=["Option A", "Option B"])
        result = StructuredAnswerEstimator()(q, make_prompts())
        assert result.answer_tokens == 2

    def test_answer_tokens_fallback_when_no_options(self):
        """Falls back to 5 tokens when the question has no options."""
        result = StructuredAnswerEstimator()(make_question(), make_prompts())
        assert result.answer_tokens == 5

    def test_comment_tokens_default(self):
        """Default comment is TokenAmount(60) — 60 tokens regardless of prompt length."""
        result = StructuredAnswerEstimator()(
            make_question(), make_prompts(user="x" * 400)
        )
        assert result.comment_tokens == 60

    def test_comment_token_amount_override(self):
        result = StructuredAnswerEstimator(comment=TokenAmount(10))(
            make_question(), make_prompts(user="x" * 400)
        )
        assert result.comment_tokens == 10

    def test_comment_token_ratio_override(self):
        # 400 chars / 4 = 100 prompt tokens; ratio 0.5 → 50 comment tokens
        result = StructuredAnswerEstimator(comment=TokenRatio(0.5))(
            make_question(), make_prompts(user="x" * 400)
        )
        assert result.comment_tokens == 50


# ------------------------------------------------------------------
# DemandEstimator


class TestDemandEstimator:
    """For demand questions — answer scales with number of price points."""

    def test_answer_tokens_scale_with_prices(self):
        q = make_question(prices=[1.0, 2.0, 3.0])
        result = DemandEstimator()(q, make_prompts())
        assert result.answer_tokens == 3

    def test_answer_tokens_at_least_one_when_empty(self):
        q = make_question(prices=[])
        result = DemandEstimator()(q, make_prompts())
        assert result.answer_tokens >= 1

    def test_tokens_per_price_scales(self):
        q = make_question(prices=[1.0, 2.0])
        result = DemandEstimator(tokens_per_price=3)(q, make_prompts())
        assert result.answer_tokens == 6

    def test_comment_tokens_default(self):
        q = make_question(prices=[1.0])
        result = DemandEstimator()(q, make_prompts(user="x" * 400))
        assert result.comment_tokens == 60


# ------------------------------------------------------------------
# MatrixEstimator


class TestMatrixEstimator:
    """For matrix questions — comment scales with number of rows, answer comes from option text."""

    def test_comment_scales_with_items(self):
        q = make_question(items=["Row A", "Row B", "Row C"], options=["Yes", "No"])
        result = MatrixEstimator()(q, make_prompts())
        assert result.comment_tokens == 3 * 20

    def test_comment_zero_when_no_items(self):
        q = make_question(items=[], options=["Yes", "No"])
        result = MatrixEstimator()(q, make_prompts())
        assert result.comment_tokens == 0

    def test_tokens_per_item_scales(self):
        q = make_question(items=["Row A", "Row B"], options=["Yes", "No"])
        result = MatrixEstimator(tokens_per_item=5)(q, make_prompts())
        assert result.comment_tokens == 2 * 5

    def test_answer_tokens_from_options(self):
        # "Yes"=3, "No"=2 → avg 2.5 chars → int(2.5/4) = 0 → max(1, 0) = 1
        q = make_question(items=["Row A"], options=["Yes", "No"])
        result = MatrixEstimator()(q, make_prompts())
        assert result.answer_tokens >= 1


# ------------------------------------------------------------------
# DefaultEstimator


class TestDefaultEstimator:
    """Fallback for unregistered question types — answer ≈ prompt length."""

    def test_answer_tokens_match_prompt(self):
        # 400 chars / 4 = 100 prompt tokens; ratio 1.0 → answer = 100
        result = DefaultEstimator()(make_question(), make_prompts(user="x" * 400))
        assert result.answer_tokens == result.prompt_tokens

    def test_comment_tokens_zero(self):
        result = DefaultEstimator()(make_question(), make_prompts(user="x" * 100))
        assert result.comment_tokens == 0

    def test_answer_tokens_at_least_one(self):
        result = DefaultEstimator()(make_question(), make_prompts(user="x"))
        assert result.answer_tokens >= 1
