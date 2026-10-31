"""Execution context used to resolve backend-neutral state operations."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StepContext:
    answers: dict[str, Any]
    interview_id: str
    scope: str | None = None
    agent_traits: dict[str, Any] | None = None
    run_context: dict[str, Any] | None = None
