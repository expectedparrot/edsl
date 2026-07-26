"""
DirectAnswerRegistry - Client-side registry for direct answer functions.

Handles tasks that can be answered without LLM calls:
- Agent-level: Agent has `answer_question_directly(self, question, scenario)` method
- Question-level: `QuestionFunctional` with `func(scenario, agent_traits)`

Functions cannot be serialized to Redis/SQLite storage, so they stay in memory
on the client. The registry maps task_id -> callable for local execution.
"""

from dataclasses import dataclass
from typing import Any
import inspect


@dataclass
class DirectAnswerEntry:
    """Registry entry for a direct answer callable."""

    task_id: str
    execution_type: str  # "agent_direct" or "functional"
    agent: Any  # EDSL Agent object (has the method)
    question: Any  # EDSL Question object
    scenario: Any  # EDSL Scenario object
    job_id: str | None = None
    interview_id: str | None = None


class DirectAnswerRegistry:
    """
    Client-side registry of direct answer functions.

    Functions cannot be serialized, so they stay in memory on the client.
    The registry maps task_id -> DirectAnswerEntry for local execution.

    Task status flow for direct answer tasks:
        PENDING -> READY -> COMPLETED  (skip rendering and queuing)

    vs LLM tasks:
        PENDING -> READY -> RENDERING -> QUEUED -> RUNNING -> COMPLETED
    """

    def __init__(self, job_service: Any | None = None):
        self._entries: dict[str, DirectAnswerEntry] = {}
        self._job_service = job_service

    def register(self, task_id: str, entry: DirectAnswerEntry) -> None:
        """Register a task for direct answering."""
        self._entries[task_id] = entry

    def has_entry(self, task_id: str) -> bool:
        """Check if task has direct answer registered."""
        return task_id in self._entries

    def get_entry(self, task_id: str) -> DirectAnswerEntry | None:
        """Get the entry for a task."""
        return self._entries.get(task_id)

    async def execute(self, task_id: str) -> dict:
        """
        Execute a direct answer task.

        Returns dict with:
            - answer: The answer value
            - comment: Comment about the answer
            - cached: Always False for direct answers
            - input_tokens: Always 0 for direct answers
            - output_tokens: Always 0 for direct answers

        Raises:
            ValueError: If task_id not found or unknown execution type
        """
        entry = self._entries.get(task_id)
        if not entry:
            raise ValueError(f"No direct answer entry for task {task_id}")

        if entry.execution_type == "agent_direct":
            return await self._maybe_await(self._execute_agent_direct(entry))
        elif entry.execution_type == "functional":
            return await self._maybe_await(self._execute_functional(entry))
        else:
            raise ValueError(f"Unknown execution type: {entry.execution_type}")

    @staticmethod
    async def _maybe_await(value):
        if inspect.isawaitable(value):
            return await value
        return value

    async def _execute_agent_direct(self, entry: DirectAnswerEntry) -> dict:
        """
        Execute agent-level direct answering.

        The agent has an `answer_question_directly(question, scenario)` method
        that returns either the answer directly or a dict with "answer" and
        optional "comment" keys.
        """
        result = await self._maybe_await(
            entry.agent.answer_question_directly(entry.question, entry.scenario)
        )
        # Handle dicts with answer and comment keys - this is used for humanize
        # to turn responses into results
        if isinstance(result, dict) and "answer" in result:
            return {
                "answer": result["answer"],
                "comment": result.get("comment"),
                "cached": False,
                "input_tokens": 0,
                "output_tokens": 0,
            }
        return {
            "answer": result,
            "comment": "Direct answer from agent method",
            "cached": False,
            "input_tokens": 0,
            "output_tokens": 0,
        }

    async def _execute_functional(self, entry: DirectAnswerEntry) -> dict:
        """
        Execute question-level functional answering.

        QuestionFunctional has an `answer_question_directly(scenario, agent_traits)`
        method that computes the answer using a provided function.
        """
        # Get agent traits if agent exists
        agent_traits = None
        if entry.agent:
            if hasattr(entry.agent, "traits"):
                agent_traits = entry.agent.traits
            elif hasattr(entry.agent, "_traits"):
                agent_traits = entry.agent._traits

        current_answers = {}
        if self._job_service and entry.job_id and entry.interview_id:
            current_answers = self._job_service._gather_current_answers(
                entry.job_id, entry.interview_id
            )

        kwargs = {"scenario": entry.scenario, "agent_traits": agent_traits}
        signature = inspect.signature(entry.question.answer_question_directly)
        if "current_answers" in signature.parameters:
            kwargs["current_answers"] = current_answers

        # QuestionFunctional.answer_question_directly returns a dict
        result = await self._maybe_await(
            entry.question.answer_question_directly(**kwargs)
        )

        # Handle both dict and direct value returns
        if isinstance(result, dict):
            return {
                "answer": result.get("answer"),
                "comment": result.get("comment", "Functional question result"),
                "cached": False,
                # Preserve any token/cost metadata the question reported (e.g.
                # QuestionImageGeneration prices each generated image); most
                # functional questions omit these and default to 0.
                "input_tokens": result.get("input_tokens", 0),
                "output_tokens": result.get("output_tokens", 0),
                **{
                    key: value
                    for key, value in result.items()
                    if key
                    not in {
                        "answer",
                        "comment",
                        "cached",
                        "input_tokens",
                        "output_tokens",
                    }
                },
            }
        else:
            # Direct value return
            return {
                "answer": result,
                "comment": "Functional question result",
                "cached": False,
                "input_tokens": 0,
                "output_tokens": 0,
            }

    def remove(self, task_id: str) -> None:
        """Remove entry after execution."""
        self._entries.pop(task_id, None)

    def clear(self) -> None:
        """Clear all entries."""
        self._entries.clear()

    def __len__(self) -> int:
        """Number of registered entries."""
        return len(self._entries)

    def get_task_ids(self) -> list[str]:
        """Get all registered task IDs."""
        return list(self._entries.keys())


def detect_execution_type(agent: Any, question: Any) -> str:
    """
    Detect how a task should be executed.

    Args:
        agent: EDSL Agent object
        question: EDSL Question object

    Returns:
        "functional" - QuestionFunctional (question handles it)
        "agent_direct" - Agent with direct answering method
        "llm" - Standard LLM execution (default)
    """
    direct = getattr(agent, "answer_question_directly", None) if agent else None

    # An agent replaying recorded answers can mark itself authoritative for
    # specific question names by tagging its direct-answering method with
    # stored_answer_question_names. Those names take priority over the
    # question's own answer_question_directly, so a question type that can
    # answer itself replays the stored value instead of re-executing. Opt-in:
    # agents that don't set the attribute keep the original precedence.
    stored = getattr(direct, "stored_answer_question_names", None)
    if stored and getattr(question, "question_name", None) in stored:
        return "agent_direct"

    # Check question-level first (QuestionFunctional)
    # These have answer_question_directly on the question itself
    if hasattr(question, "answer_question_directly"):
        return "functional"

    # Check agent-level direct answering
    # These have answer_question_directly on the agent
    if direct is not None:
        return "agent_direct"

    # Default to LLM execution
    return "llm"
