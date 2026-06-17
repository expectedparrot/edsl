from __future__ import annotations
from typing import Callable, TYPE_CHECKING

from .question_token_estimate import QuestionTokenEstimate
from .cost_estimation_constants import (
    EDSL_DEFAULT_CHARS_PER_TOKEN,
    TokenAmount,
    TokenRatio,
    _resolve_token_spec,
)

if TYPE_CHECKING:
    from ...questions.question_base import QuestionBase
    from ...language_models.language_model import LanguageModel


# ------------------------------------------------------------------
# Helpers


def _estimate_prompt_tokens(
    prompts: dict, chars_per_token: int = EDSL_DEFAULT_CHARS_PER_TOKEN
) -> int:
    user_prompt = str(prompts.get("user_prompt", ""))
    system_prompt = str(prompts.get("system_prompt", ""))
    return max(1, (len(user_prompt) + len(system_prompt)) // chars_per_token)


def _avg_option_tokens(
    question, chars_per_token: int = EDSL_DEFAULT_CHARS_PER_TOKEN
) -> int:
    options = getattr(question, "question_options", None)
    if not options:
        return 5
    avg_chars = sum(len(str(o)) for o in options) / len(options)
    return max(1, int(avg_chars / chars_per_token))


# ------------------------------------------------------------------
# Per-type estimator callables


class ZeroCostEstimator:
    """For question types answered locally with no LLM call (compute, functional).

    Cost is zero (billable=False) but answer_tokens is estimated so downstream
    questions that include this answer in memory get an accurate token count.
    """

    def __init__(
        self,
        answer: TokenAmount | TokenRatio = TokenAmount(20),
        chars_per_token: int = EDSL_DEFAULT_CHARS_PER_TOKEN,
    ):
        self.answer = answer
        self.chars_per_token = chars_per_token

    def __call__(
        self,
        question: "QuestionBase",
        prompts: dict,
        model: "LanguageModel" | None = None,
    ) -> QuestionTokenEstimate:
        prompt_tokens = _estimate_prompt_tokens(prompts, self.chars_per_token)
        answer_tokens = max(0, _resolve_token_spec(self.answer, prompt_tokens))
        return QuestionTokenEstimate(
            prompt_tokens=prompt_tokens,
            answer_tokens=answer_tokens,
            comment_tokens=0,
            billable=False,
        )

    def describe(self) -> str:
        return "No LLM call — answered locally (zero cost)"

    def __repr__(self) -> str:
        return f"ZeroCostEstimator(answer={self.answer})"


class InterviewEstimator:
    """Cost estimator for QuestionInterview.

    A single QuestionInterview runs as 2*T model calls (one interviewer decision +
    one respondent reply per turn). The transcript is included in every call and
    grows by one exchange each turn, so input tokens accumulate non-linearly.

    Parameters
    ----------
    default_turns:
        Expected number of turns. Capped at the question's max_turns if lower.
        Because input cost grows with the square of turns (each turn re-reads the
        full transcript), overestimating turns is much more expensive than it looks —
        estimating 10 turns when 6 actually run overcounts transcript tokens by 3×,
        not 1.67×. Set this to a typical observed turn count rather than max_turns.
    interviewer_output_tokens:
        Tokens per interviewer response. The interviewer emits a small JSON object
        (done/acknowledgment/question), so this is much smaller than a free-text reply.
    respondent_output_tokens:
        Tokens per respondent reply. Free-form prose — typically much larger than
        the interviewer output.
    avg_utterance_tokens:
        Tokens in the interviewer utterance appended to the transcript each turn.
        This text appears in both the interviewer prompt (as part of the growing
        transcript on the *next* turn) and the respondent prompt (as the latest
        interviewer utterance). Kept separate from respondent_output_tokens because
        it is a distinct message in the transcript.
    interviewer_overhead_tokens:
        Fixed token overhead in _build_interviewer_user_prompt beyond question_text
        and interview_guide: the turn-index line and the JSON-format instructions.
    respondent_overhead_tokens:
        Fixed token overhead in _build_respondent_user_prompt beyond question_text,
        interview_guide, and memory: the closing instruction line.
    interviewer_system_tokens:
        Tokens in the fixed interviewer_system_prompt class attribute on
        InvigilatorInterview (the "You are an expert qualitative interviewer…" string).
    """

    def __init__(
        self,
        default_turns: int = 5,
        interviewer_output_tokens: int = 50,
        respondent_output_tokens: int = 100,
        avg_utterance_tokens: int = 30,
        interviewer_overhead_tokens: int = 60,
        respondent_overhead_tokens: int = 60,
        interviewer_system_tokens: int = 40,
        chars_per_token: int = EDSL_DEFAULT_CHARS_PER_TOKEN,
    ):
        self.default_turns = default_turns
        self.interviewer_output_tokens = interviewer_output_tokens
        self.respondent_output_tokens = respondent_output_tokens
        self.avg_utterance_tokens = avg_utterance_tokens
        self.interviewer_overhead_tokens = interviewer_overhead_tokens
        self.respondent_overhead_tokens = respondent_overhead_tokens
        self.interviewer_system_tokens = interviewer_system_tokens
        self.chars_per_token = chars_per_token

    def _effective_turns(self, question: "QuestionBase") -> int:
        max_turns = getattr(question, "max_turns", self.default_turns)
        return max(1, min(self.default_turns, max_turns))

    def __call__(
        self,
        question: "QuestionBase",
        prompts: dict,
        model: "LanguageModel | None" = None,
    ) -> QuestionTokenEstimate:
        T = self._effective_turns(question)
        Q = max(1, len(getattr(question, "question_text", "")) // self.chars_per_token)
        G = max(
            1, len(getattr(question, "interview_guide", "")) // self.chars_per_token
        )

        # Fixed cost per turn: both calls receive question_text + interview_guide,
        # plus their respective system/overhead tokens and the latest utterance.
        fixed_per_turn = (
            2 * (Q + G)
            + self.interviewer_overhead_tokens
            + self.respondent_overhead_tokens
            + self.interviewer_system_tokens
            + self.avg_utterance_tokens  # latest utterance in the respondent prompt
        )
        # Each turn re-reads the full transcript accumulated so far. At turn k both
        # calls see k prior exchanges, so total transcript tokens = T*(T-1)*exchange_size.
        transcript_growth = (
            T * (T - 1) * (self.avg_utterance_tokens + self.respondent_output_tokens)
        )

        prompt_tokens = T * fixed_per_turn + transcript_growth
        # Each turn produces one interviewer JSON blob and one respondent reply.
        answer_tokens = T * (
            self.interviewer_output_tokens + self.respondent_output_tokens
        )

        return QuestionTokenEstimate(
            prompt_tokens=prompt_tokens,
            answer_tokens=answer_tokens,
            comment_tokens=0,
        )

    def memory_multiplier(self, question: "QuestionBase") -> int:
        """Memory appears in every respondent call, so multiply by expected turns."""
        return self._effective_turns(question)

    def describe(self) -> str:
        return (
            f"Turn-based interview: estimates {self.default_turns} turns. "
            f"Each turn makes two model calls (interviewer + respondent). "
            f"Input cost rises with each turn because the full transcript is included in every call. "
            f"Output estimated at ~{self.interviewer_output_tokens} tokens/turn (interviewer) "
            f"and ~{self.respondent_output_tokens} tokens/turn (respondent)."
        )

    def __repr__(self) -> str:
        return (
            f"InterviewEstimator(default_turns={self.default_turns}, "
            f"interviewer_output_tokens={self.interviewer_output_tokens}, "
            f"respondent_output_tokens={self.respondent_output_tokens})"
        )


class FreeTextStyleEstimator:
    """For free-form answer types where the output is open-ended text.

    No comment field — all output is the answer. Output defaults to TokenRatio(1.0)
    (output ≈ input) since output length is unknown for these types.

    Used for: free_text, extract, list, markdown, edsl_object, dict,
              pydantic, file_upload.
    """

    def __init__(
        self,
        output: TokenAmount | TokenRatio = TokenRatio(1.0),
        chars_per_token: int = EDSL_DEFAULT_CHARS_PER_TOKEN,
    ):
        self.output = output
        self.chars_per_token = chars_per_token

    def __call__(
        self,
        question: "QuestionBase",
        prompts: dict,
        model: "LanguageModel" | None = None,
    ) -> QuestionTokenEstimate:
        prompt_tokens = _estimate_prompt_tokens(prompts, self.chars_per_token)
        answer_tokens = max(1, _resolve_token_spec(self.output, prompt_tokens))
        return QuestionTokenEstimate(
            prompt_tokens=prompt_tokens,
            answer_tokens=answer_tokens,
            comment_tokens=0,
        )

    def describe(self) -> str:
        if isinstance(self.output, TokenAmount):
            return f"Output fixed at {self.output.value} tokens"
        pct = int(self.output.value * 100)
        return f"Output estimated at {pct}% of prompt tokens"

    def __repr__(self) -> str:
        return f"FreeTextStyleEstimator(output={self.output})"


class StructuredAnswerEstimator:
    """For question types with a structured answer (one of N options) plus an optional comment.

    Answer tokens are estimated from the actual option text; comment tokens are a
    configurable flat amount or ratio.

    Used for: multiple_choice, yes_no, likert_five, dropdown, linear_scale, numerical,
              rank, top_k, budget, checkbox, multiple_choice_with_other.
    """

    def __init__(
        self,
        comment: TokenAmount | TokenRatio = TokenAmount(60),
        chars_per_token: int = EDSL_DEFAULT_CHARS_PER_TOKEN,
    ):
        self.comment = comment
        self.chars_per_token = chars_per_token

    def __call__(
        self,
        question: "QuestionBase",
        prompts: dict,
        model: "LanguageModel" | None = None,
    ) -> QuestionTokenEstimate:
        prompt_tokens = _estimate_prompt_tokens(prompts, self.chars_per_token)
        answer_tokens = _avg_option_tokens(question, self.chars_per_token)
        comment_tokens = max(0, _resolve_token_spec(self.comment, prompt_tokens))
        return QuestionTokenEstimate(
            prompt_tokens=prompt_tokens,
            answer_tokens=answer_tokens,
            comment_tokens=comment_tokens,
        )

    def describe(self) -> str:
        if isinstance(self.comment, TokenAmount):
            comment_str = f"{self.comment.value} comment tokens"
        else:
            comment_str = (
                f"{int(self.comment.value * 100)}% of prompt tokens for comment"
            )
        return f"Answer from option text length + {comment_str}"

    def __repr__(self) -> str:
        return f"StructuredAnswerEstimator(comment={self.comment})"


class DemandEstimator:
    """For demand questions — answer is a compact bracket list of quantities, one per price point.

    Answer tokens scale by number of prices (~1 token per value in the list).
    Comment tokens are flat (same rationale as StructuredAnswerEstimator).
    """

    def __init__(
        self,
        tokens_per_price: int = 1,
        comment: TokenAmount | TokenRatio = TokenAmount(60),
        chars_per_token: int = EDSL_DEFAULT_CHARS_PER_TOKEN,
    ):
        self.tokens_per_price = tokens_per_price
        self.comment = comment
        self.chars_per_token = chars_per_token

    def __call__(
        self,
        question: "QuestionBase",
        prompts: dict,
        model: "LanguageModel" | None = None,
    ) -> QuestionTokenEstimate:
        prompt_tokens = _estimate_prompt_tokens(prompts, self.chars_per_token)
        n_prices = len(getattr(question, "prices", []))
        answer_tokens = max(1, n_prices * self.tokens_per_price)
        comment_tokens = max(0, _resolve_token_spec(self.comment, prompt_tokens))
        return QuestionTokenEstimate(
            prompt_tokens=prompt_tokens,
            answer_tokens=answer_tokens,
            comment_tokens=comment_tokens,
        )

    def describe(self) -> str:
        if isinstance(self.comment, TokenAmount):
            comment_str = f"{self.comment.value} comment tokens"
        else:
            comment_str = (
                f"{int(self.comment.value * 100)}% of prompt tokens for comment"
            )
        return f"Answer scales with price point count ({self.tokens_per_price} token/price) + {comment_str}"

    def __repr__(self) -> str:
        return f"DemandEstimator(tokens_per_price={self.tokens_per_price}, comment={self.comment})"


class MatrixEstimator:
    """For matrix questions — scales comment tokens by number of rows (question_items).

    Answer tokens come from average option text length (same as StructuredAnswerEstimator).
    Comment tokens are estimated as tokens_per_item * n_items, since a respondent
    commenting on a matrix is likely to say something about each row.
    """

    def __init__(
        self,
        tokens_per_item: int = 20,
        chars_per_token: int = EDSL_DEFAULT_CHARS_PER_TOKEN,
    ):
        self.tokens_per_item = tokens_per_item
        self.chars_per_token = chars_per_token

    def __call__(
        self,
        question: "QuestionBase",
        prompts: dict,
        model: "LanguageModel" | None = None,
    ) -> QuestionTokenEstimate:
        prompt_tokens = _estimate_prompt_tokens(prompts, self.chars_per_token)
        n_items = len(getattr(question, "question_items", []))
        answer_tokens = _avg_option_tokens(question, self.chars_per_token)
        comment_tokens = n_items * self.tokens_per_item
        return QuestionTokenEstimate(
            prompt_tokens=prompt_tokens,
            answer_tokens=answer_tokens,
            comment_tokens=comment_tokens,
        )

    def describe(self) -> str:
        return (
            f"Answer from option text + {self.tokens_per_item} comment tokens per row"
        )

    def __repr__(self) -> str:
        return f"MatrixEstimator(tokens_per_item={self.tokens_per_item})"


class DefaultEstimator:
    """Fallback for unknown question types. Emits a warning."""

    def __init__(self, chars_per_token: int = EDSL_DEFAULT_CHARS_PER_TOKEN):
        self.chars_per_token = chars_per_token

    def __call__(
        self,
        question: "QuestionBase",
        prompts: dict,
        model: "LanguageModel" | None = None,
    ) -> QuestionTokenEstimate:
        prompt_tokens = _estimate_prompt_tokens(prompts, self.chars_per_token)
        return QuestionTokenEstimate(
            prompt_tokens=prompt_tokens,
            answer_tokens=max(1, _resolve_token_spec(TokenRatio(1.0), prompt_tokens)),
            comment_tokens=0,
        )

    def describe(self) -> str:
        return "Unknown question type — output estimated at 100% of prompt tokens (fallback)"

    def __repr__(self) -> str:
        return "DefaultEstimator"


# ------------------------------------------------------------------
# Default registry


def _build_default_registry(chars_per_token: int) -> dict[str, object]:
    c = chars_per_token
    return {
        # zero cost
        "compute": ZeroCostEstimator(chars_per_token=c),
        "functional": ZeroCostEstimator(chars_per_token=c),
        # free-form output — output length is unknown; TokenRatio(1.0) (output ≈ input) is an
        # honest conservative default. interview is the exception: format is fixed by the template.
        "free_text": FreeTextStyleEstimator(output=TokenRatio(1.0), chars_per_token=c),
        "extract": FreeTextStyleEstimator(output=TokenRatio(1.0), chars_per_token=c),
        "list": FreeTextStyleEstimator(output=TokenRatio(1.0), chars_per_token=c),
        "interview": InterviewEstimator(chars_per_token=c),
        "markdown": FreeTextStyleEstimator(output=TokenRatio(1.0), chars_per_token=c),
        "edsl_object": FreeTextStyleEstimator(
            output=TokenRatio(1.0), chars_per_token=c
        ),
        "dict": FreeTextStyleEstimator(output=TokenRatio(1.0), chars_per_token=c),
        "pydantic": FreeTextStyleEstimator(output=TokenRatio(1.0), chars_per_token=c),
        "file_upload": FreeTextStyleEstimator(
            output=TokenRatio(1.0), chars_per_token=c
        ),
        # structured answer + comment
        "multiple_choice": StructuredAnswerEstimator(chars_per_token=c),
        "yes_no": StructuredAnswerEstimator(chars_per_token=c),
        "likert_five": StructuredAnswerEstimator(chars_per_token=c),
        "dropdown": StructuredAnswerEstimator(chars_per_token=c),
        "linear_scale": StructuredAnswerEstimator(chars_per_token=c),
        "numerical": StructuredAnswerEstimator(chars_per_token=c),
        "rank": StructuredAnswerEstimator(chars_per_token=c),
        "top_k": StructuredAnswerEstimator(chars_per_token=c),
        "budget": StructuredAnswerEstimator(chars_per_token=c),
        "checkbox": StructuredAnswerEstimator(chars_per_token=c),
        "multiple_choice_with_other": StructuredAnswerEstimator(chars_per_token=c),
        "matrix": MatrixEstimator(chars_per_token=c),
        "demand": DemandEstimator(chars_per_token=c),
        # thinking — QuestionThinking is free-text; thinking_question() wrappers preserve original type
        "thinking": FreeTextStyleEstimator(output=TokenRatio(0.75), chars_per_token=c),
    }


DEFAULT_ESTIMATORS: dict[str, object] = _build_default_registry(
    EDSL_DEFAULT_CHARS_PER_TOKEN
)

_DEFAULT_ESTIMATOR = DefaultEstimator()


# ------------------------------------------------------------------
# QuestionEstimator — the public class


class QuestionEstimator:
    """Dispatches estimation to a per-question-type callable.

    Args:
        overrides: dict mapping question_type -> estimator callable.
                   Merged over DEFAULT_ESTIMATORS; only the types you specify are changed.
    """

    def __init__(
        self,
        overrides: dict[str, Callable] | None = None,
        chars_per_token: int = EDSL_DEFAULT_CHARS_PER_TOKEN,
    ):
        self.chars_per_token = chars_per_token
        self._registry = _build_default_registry(chars_per_token)
        if overrides:
            self._registry.update(overrides)

    @property
    def chars_per_token_overrides(self) -> dict[str, int]:
        return {
            qtype: estimator.chars_per_token
            for qtype, estimator in self._registry.items()
            if hasattr(estimator, "chars_per_token")
            and estimator.chars_per_token != self.chars_per_token
        }

    def estimate(
        self,
        question: "QuestionBase",
        prompts: dict,
        model: "LanguageModel" | None = None,
    ) -> tuple[QuestionTokenEstimate, list[str]]:
        """Return (QuestionTokenEstimate, warnings) for the given question."""
        estimator = self._registry.get(question.question_type, _DEFAULT_ESTIMATOR)

        is_default = question.question_type not in self._registry
        warnings = []
        if is_default:
            warnings.append(
                f"Question '{question.question_name}' (type '{question.question_type}'): "
                f"no estimator registered — using DefaultEstimator."
            )

        return estimator(question, prompts, model), warnings

    def estimator_name_for(self, question_type: str) -> str:
        estimator = self._registry.get(question_type, _DEFAULT_ESTIMATOR)
        return repr(estimator)

    def description_for(self, question_type: str) -> str:
        estimator = self._registry.get(question_type, _DEFAULT_ESTIMATOR)
        return estimator.describe()
