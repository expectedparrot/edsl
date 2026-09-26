from __future__ import annotations
from dataclasses import dataclass


@dataclass
class TokenOverride:
    """Partial token override for a question, optionally scoped to a service/model.

    Fields left as None are not overridden — the estimator's computed value is used.

    Scope:
        service: inference service name to match (None = all services)
        model:   model name to match (None = all models)

    When multiple overrides match the same question, the most specific one wins:
    service+model > service-only or model-only > global (neither set).

    Args:
        answer_tokens:   override for the answer field token count
        comment_tokens:  override for the comment field token count
        thinking_tokens: override for the thinking/reasoning token count
        note:            shown in the estimate description; auto-populated by
                         calibrate_from_results, or set manually for documentation
        service:         inference service to match (e.g. "openai", "google")
        model:           model name to match (e.g. "gemini-3.5-flash")
    """

    answer_tokens: int | None = None
    comment_tokens: int | None = None
    thinking_tokens: int | None = None
    note: str | None = None
    service: str | None = None
    model: str | None = None

    def matches(self, service: str, model: str) -> bool:
        return (self.service is None or self.service == service) and (
            self.model is None or self.model == model
        )

    def specificity(self) -> int:
        return (self.service is not None) + (self.model is not None)

    def describe(self) -> str:
        parts = []
        if self.answer_tokens is not None:
            parts.append(f"answer_tokens={self.answer_tokens}")
        if self.comment_tokens is not None:
            parts.append(f"comment_tokens={self.comment_tokens}")
        if self.thinking_tokens is not None:
            parts.append(f"thinking_tokens={self.thinking_tokens}")
        scope = [s for s in (self.service, self.model) if s is not None]
        base = ", ".join(parts) if parts else "no fields set"
        suffix = f" [{', '.join(scope)}]" if scope else ""
        if self.note:
            return f"{base}{suffix} — {self.note}"
        return f"{base}{suffix}"
