from __future__ import annotations
from typing import Callable, TYPE_CHECKING

from .question_token_estimate import QuestionTokenEstimate
from .cost_estimation_constants import EDSL_DEFAULT_CHARS_PER_TOKEN

if TYPE_CHECKING:
    from ...questions.question_base import QuestionBase
    from ...language_models.language_model import LanguageModel


# ------------------------------------------------------------------
# Helpers


def _estimate_input_tokens(
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
    """For question types answered locally with no LLM call (compute, functional)."""

    def __init__(self, chars_per_token: int = EDSL_DEFAULT_CHARS_PER_TOKEN):
        self.chars_per_token = chars_per_token

    def __call__(
        self,
        question: "QuestionBase",
        prompts: dict,
        model: "LanguageModel" | None = None,
    ) -> QuestionTokenEstimate:
        return QuestionTokenEstimate(
            input_tokens=0,
            answer_tokens=0,
            comment_tokens=0,
        )

    def __repr__(self) -> str:
        return "ZeroCostEstimator"


class FreeTextStyleEstimator:
    """For free-form answer types where the output is open-ended text.

    No comment field — all output is the answer.
    Used for: free_text, extract, list, interview, markdown, edsl_object, dict,
              pydantic, file_upload, demand.
    """

    DEFAULT_OUTPUT_RATIO = 0.75

    def __init__(
        self,
        output_ratio: float = DEFAULT_OUTPUT_RATIO,
        chars_per_token: int = EDSL_DEFAULT_CHARS_PER_TOKEN,
    ):
        self.output_ratio = output_ratio
        self.chars_per_token = chars_per_token

    def __call__(
        self,
        question: "QuestionBase",
        prompts: dict,
        model: "LanguageModel" | None = None,
    ) -> QuestionTokenEstimate:
        input_tokens = _estimate_input_tokens(prompts, self.chars_per_token)
        answer_tokens = max(1, int(input_tokens * self.output_ratio))
        return QuestionTokenEstimate(
            input_tokens=input_tokens,
            answer_tokens=answer_tokens,
            comment_tokens=0,
        )

    def __repr__(self) -> str:
        return f"FreeTextStyleEstimator(output_ratio={self.output_ratio})"


class StructuredAnswerEstimator:
    """For question types with a structured answer (one of N options) plus an optional comment.

    Answer tokens are estimated from the actual option text; comment tokens use a
    configurable ratio of the input.

    Used for: multiple_choice, yes_no, likert_five, dropdown, linear_scale, numerical,
              rank, top_k, budget, checkbox, multiple_choice_with_other, matrix.
    """

    DEFAULT_COMMENT_RATIO = 0.3

    def __init__(
        self,
        comment_ratio: float = DEFAULT_COMMENT_RATIO,
        chars_per_token: int = EDSL_DEFAULT_CHARS_PER_TOKEN,
    ):
        self.comment_ratio = comment_ratio
        self.chars_per_token = chars_per_token

    def __call__(
        self,
        question: "QuestionBase",
        prompts: dict,
        model: "LanguageModel" | None = None,
    ) -> QuestionTokenEstimate:
        input_tokens = _estimate_input_tokens(prompts, self.chars_per_token)
        answer_tokens = _avg_option_tokens(question, self.chars_per_token)
        comment_tokens = max(0, int(input_tokens * self.comment_ratio))
        return QuestionTokenEstimate(
            input_tokens=input_tokens,
            answer_tokens=answer_tokens,
            comment_tokens=comment_tokens,
        )

    def __repr__(self) -> str:
        return f"StructuredAnswerEstimator(comment_ratio={self.comment_ratio})"


class ThinkingEstimator:
    """For question_type='thinking'.

    Uses model.parameters['budget_tokens'] as a conservative upper bound for
    thinking_tokens. Emits a warning if budget_tokens is not set.
    """

    def __init__(self, chars_per_token: int = EDSL_DEFAULT_CHARS_PER_TOKEN):
        self.chars_per_token = chars_per_token

    def __call__(
        self,
        question: "QuestionBase",
        prompts: dict,
        model: "LanguageModel" | None = None,
    ) -> tuple[QuestionTokenEstimate, list[str]]:
        input_tokens = _estimate_input_tokens(prompts, self.chars_per_token)
        answer_tokens = max(1, int(input_tokens * 0.75))

        thinking_tokens = None
        warnings = []

        if model is not None:
            budget = getattr(model, "parameters", {}).get("budget_tokens")
            if budget is not None:
                thinking_tokens = int(budget)
            else:
                warnings.append(
                    f"Thinking question '{question.question_name}': budget_tokens not set on model "
                    f"'{getattr(model, 'model', 'unknown')}' — thinking_tokens not estimated."
                )

        return (
            QuestionTokenEstimate(
                input_tokens=input_tokens,
                answer_tokens=answer_tokens,
                comment_tokens=0,
                thinking_tokens=thinking_tokens or 0,
            ),
            warnings,
        )

    def __repr__(self) -> str:
        return "ThinkingEstimator"


class DefaultEstimator:
    """Fallback for unknown question types. Emits a warning."""

    DEFAULT_OUTPUT_RATIO = 0.75

    def __init__(self, chars_per_token: int = EDSL_DEFAULT_CHARS_PER_TOKEN):
        self.chars_per_token = chars_per_token

    def __call__(
        self,
        question: "QuestionBase",
        prompts: dict,
        model: "LanguageModel" | None = None,
    ) -> QuestionTokenEstimate:
        input_tokens = _estimate_input_tokens(prompts, self.chars_per_token)
        return QuestionTokenEstimate(
            input_tokens=input_tokens,
            answer_tokens=max(1, int(input_tokens * self.DEFAULT_OUTPUT_RATIO)),
            comment_tokens=0,
        )

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
        # free-form output
        "free_text": FreeTextStyleEstimator(output_ratio=0.75, chars_per_token=c),
        "extract": FreeTextStyleEstimator(output_ratio=0.5, chars_per_token=c),
        "list": FreeTextStyleEstimator(output_ratio=0.5, chars_per_token=c),
        "interview": FreeTextStyleEstimator(output_ratio=0.75, chars_per_token=c),
        "markdown": FreeTextStyleEstimator(output_ratio=0.75, chars_per_token=c),
        "edsl_object": FreeTextStyleEstimator(output_ratio=0.5, chars_per_token=c),
        "dict": FreeTextStyleEstimator(output_ratio=0.5, chars_per_token=c),
        "pydantic": FreeTextStyleEstimator(output_ratio=0.5, chars_per_token=c),
        "file_upload": FreeTextStyleEstimator(output_ratio=0.1, chars_per_token=c),
        "demand": FreeTextStyleEstimator(output_ratio=0.5, chars_per_token=c),
        # structured answer + comment
        "multiple_choice": StructuredAnswerEstimator(
            comment_ratio=0.3, chars_per_token=c
        ),
        "yes_no": StructuredAnswerEstimator(comment_ratio=0.3, chars_per_token=c),
        "likert_five": StructuredAnswerEstimator(comment_ratio=0.3, chars_per_token=c),
        "dropdown": StructuredAnswerEstimator(comment_ratio=0.3, chars_per_token=c),
        "linear_scale": StructuredAnswerEstimator(comment_ratio=0.3, chars_per_token=c),
        "numerical": StructuredAnswerEstimator(comment_ratio=0.3, chars_per_token=c),
        "rank": StructuredAnswerEstimator(comment_ratio=0.3, chars_per_token=c),
        "top_k": StructuredAnswerEstimator(comment_ratio=0.3, chars_per_token=c),
        "budget": StructuredAnswerEstimator(comment_ratio=0.3, chars_per_token=c),
        "checkbox": StructuredAnswerEstimator(comment_ratio=0.3, chars_per_token=c),
        "multiple_choice_with_other": StructuredAnswerEstimator(
            comment_ratio=0.3, chars_per_token=c
        ),
        "matrix": StructuredAnswerEstimator(comment_ratio=0.0, chars_per_token=c),
        # thinking
        "thinking": ThinkingEstimator(chars_per_token=c),
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
            qtype: est.chars_per_token
            for qtype, est in self._registry.items()
            if hasattr(est, "chars_per_token")
            and est.chars_per_token != self.chars_per_token
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

        if isinstance(estimator, ThinkingEstimator):
            result, think_warnings = estimator(question, prompts, model)
            return result, warnings + think_warnings

        return estimator(question, prompts, model), warnings

    def estimator_name_for(self, question_type: str) -> str:
        estimator = self._registry.get(question_type, _DEFAULT_ESTIMATOR)
        return repr(estimator)
