from __future__ import annotations
from dataclasses import dataclass


@dataclass
class QuestionTokenEstimate:
    """Token count breakdown for a single question estimation.

    All token fields are optional — None means "use the estimated value" (relevant for
    token_overrides, where only the fields you set are applied). In the detail
    Dataset, None is rendered as 0 for consistency.

    billable=False marks questions answered locally (compute, functional) where no LLM
    call is made and cost is zero, but answer_tokens is still estimated so downstream
    memory calculations are accurate.
    """

    input_tokens: int | None = None  # base prompt (user + system prompt)
    file_tokens: int | None = None  # from FileStore objects in the scenario
    memory_tokens: int | None = None  # from prior question answers (memory plan)
    answer_tokens: int | None = None  # the answer field in the model response
    comment_tokens: int | None = None  # the comment field (0 for free_text, etc.)
    thinking_tokens: int | None = None  # internal reasoning tokens; charged at output rate
    billable: bool = True  # False for compute/functional — tokens tracked but cost is zero

    @property
    def total_input_tokens(self) -> int:
        return (
            (self.input_tokens or 0)
            + (self.file_tokens or 0)
            + (self.memory_tokens or 0)
        )

    @property
    def total_output_tokens(self) -> int:
        return (
            (self.answer_tokens or 0)
            + (self.comment_tokens or 0)
            + (self.thinking_tokens or 0)
        )

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    def merge(self, override: "QuestionTokenEstimate") -> "QuestionTokenEstimate":
        """Return a new QuestionTokenEstimate with non-None fields from override applied."""
        return QuestionTokenEstimate(
            input_tokens=(
                override.input_tokens
                if override.input_tokens is not None
                else self.input_tokens
            ),
            file_tokens=(
                override.file_tokens
                if override.file_tokens is not None
                else self.file_tokens
            ),
            memory_tokens=(
                override.memory_tokens
                if override.memory_tokens is not None
                else self.memory_tokens
            ),
            answer_tokens=(
                override.answer_tokens
                if override.answer_tokens is not None
                else self.answer_tokens
            ),
            comment_tokens=(
                override.comment_tokens
                if override.comment_tokens is not None
                else self.comment_tokens
            ),
            thinking_tokens=(
                override.thinking_tokens
                if override.thinking_tokens is not None
                else self.thinking_tokens
            ),
            billable=self.billable,  # non-billable status cannot be overridden
        )

    def to_detail_row(self) -> dict:
        """Return a flat dict for use in the detail Dataset, with None rendered as 0."""
        return {
            "input_tokens": self.input_tokens or 0,
            "file_tokens": self.file_tokens or 0,
            "memory_tokens": self.memory_tokens or 0,
            "answer_tokens": self.answer_tokens or 0,
            "comment_tokens": self.comment_tokens or 0,
            "thinking_tokens": self.thinking_tokens or 0,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "billable": self.billable,
        }
