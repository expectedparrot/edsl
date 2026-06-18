"""Unit tests for InterviewEstimator."""

from types import SimpleNamespace
from edsl.jobs.cost_estimation.question_estimators import InterviewEstimator
from edsl.jobs.cost_estimation.cost_estimation_constants import (
    EDSL_DEFAULT_CHARS_PER_TOKEN,
)

C = EDSL_DEFAULT_CHARS_PER_TOKEN  # 4 chars per token


# ------------------------------------------------------------------
# Fixtures


def make_question(
    question_text="Tell me about your experience.",
    interview_guide="Probe on satisfaction and details.",
    max_turns=10,
):
    return SimpleNamespace(
        question_type="interview",
        question_name="q0",
        question_text=question_text,
        interview_guide=interview_guide,
        max_turns=max_turns,
    )


# ------------------------------------------------------------------
# Baseline


class TestInterviewEstimatorBaseline:
    def test_answer_tokens_default_turns(self):
        est = InterviewEstimator(default_turns=5)
        result = est(make_question(), {})
        assert result.answer_tokens == 5 * (50 + 100)

    def test_billable(self):
        assert InterviewEstimator()(make_question(), {}).billable is True

    def test_none_per_turn_base_uses_fallback(self):
        est = InterviewEstimator(default_turns=5)
        assert (
            est(make_question(), {}, per_turn_base_tokens=None).prompt_tokens
            == est(make_question(), {}).prompt_tokens
        )


# ------------------------------------------------------------------
# per_turn_base_tokens (precomputed from invigilator prompt builders)


class TestInterviewEstimatorPerTurnBase:
    """When per_turn_base_tokens is supplied, the estimator uses it instead of the
    Q/G fallback. JobCostEstimator computes this from invigilator._rendered_question(),
    _build_respondent_system_prompt(), _build_interviewer_user_prompt(), and
    _build_respondent_user_prompt() so that agent persona and scenario text are
    captured from the actual prompt builders.
    """

    def test_per_turn_base_drives_prompt_tokens(self):
        """prompt_tokens = T * (base + avg_utterance) + transcript_growth."""
        est = InterviewEstimator(default_turns=5)
        base = 200

        result = est(make_question(), {}, per_turn_base_tokens=base)

        transcript_growth = (
            5 * 4 * (est.avg_utterance_tokens + est.respondent_output_tokens)
        )
        expected = 5 * (base + est.avg_utterance_tokens) + transcript_growth
        assert result.prompt_tokens == expected

    def test_per_turn_base_does_not_affect_answer_tokens(self):
        est = InterviewEstimator(default_turns=5)
        r_default = est(make_question(), {})
        r_custom = est(make_question(), {}, per_turn_base_tokens=999)
        assert r_default.answer_tokens == r_custom.answer_tokens

    def test_larger_base_gives_more_prompt_tokens(self):
        est = InterviewEstimator(default_turns=5)
        r_small = est(make_question(), {}, per_turn_base_tokens=50)
        r_large = est(make_question(), {}, per_turn_base_tokens=500)
        assert r_large.prompt_tokens > r_small.prompt_tokens

    def test_base_scales_linearly_with_turns(self):
        """Each extra turn adds one more copy of per_turn_base — linear growth."""
        base = 100
        est_3 = InterviewEstimator(default_turns=3)
        est_5 = InterviewEstimator(default_turns=5)

        # Isolate the base contribution by fixing transcript growth separately
        r3 = est_3(make_question(), {}, per_turn_base_tokens=base)
        r5 = est_5(make_question(), {}, per_turn_base_tokens=base)

        tg_3 = 3 * 2 * (est_3.avg_utterance_tokens + est_3.respondent_output_tokens)
        tg_5 = 5 * 4 * (est_5.avg_utterance_tokens + est_5.respondent_output_tokens)

        assert r3.prompt_tokens - tg_3 == 3 * (base + est_3.avg_utterance_tokens)
        assert r5.prompt_tokens - tg_5 == 5 * (base + est_5.avg_utterance_tokens)


# ------------------------------------------------------------------
# Fallback: Q/G from question text


class TestInterviewEstimatorFallback:
    """Without per_turn_base_tokens, the estimator reads Q and G from question_text
    and interview_guide. This path is used when calling the estimator standalone
    (e.g. QuestionEstimator.estimate, describe, tests).
    """

    def test_longer_question_text_increases_prompt_tokens(self):
        """Both calls receive question_text each turn, so delta = 2*T*(long_Q - short_Q)."""
        short_text = "x" * 40  # 10 tokens
        long_text = "x" * 200  # 50 tokens

        est = InterviewEstimator(default_turns=5)
        short_Q = max(1, len(short_text) // C)
        long_Q = max(1, len(long_text) // C)
        expected_delta = 5 * 2 * (long_Q - short_Q)

        r_short = est(make_question(question_text=short_text), {})
        r_long = est(make_question(question_text=long_text), {})

        assert r_long.prompt_tokens - r_short.prompt_tokens == expected_delta
