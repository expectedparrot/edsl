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


@dataclass
class DirectAnswerEntry:
    """Registry entry for a direct answer callable."""

    task_id: str
    execution_type: str  # "agent_direct" or "functional"
    agent: Any  # EDSL Agent object (has the method)
    question: Any  # EDSL Question object
    scenario: Any  # EDSL Scenario object


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

    def __init__(self):
        self._entries: dict[str, DirectAnswerEntry] = {}

    def register(self, task_id: str, entry: DirectAnswerEntry) -> None:
        """Register a task for direct answering."""
        self._entries[task_id] = entry

    def has_entry(self, task_id: str) -> bool:
        """Check if task has direct answer registered."""
        return task_id in self._entries

    def get_entry(self, task_id: str) -> DirectAnswerEntry | None:
        """Get the entry for a task."""
        return self._entries.get(task_id)

    def execute(self, task_id: str) -> dict:
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
            return self._execute_agent_direct(entry)
        elif entry.execution_type == "functional":
            return self._execute_functional(entry)
        else:
            raise ValueError(f"Unknown execution type: {entry.execution_type}")

    def _execute_agent_direct(self, entry: DirectAnswerEntry) -> dict:
        """
        Execute agent-level direct answering.

        The agent has an `answer_question_directly(question, scenario)` method
        that returns the answer directly without LLM involvement.
        """
        answer = entry.agent.answer_question_directly(entry.question, entry.scenario)
        return {
            "answer": answer,
            "comment": "Direct answer from agent method",
            "cached": False,
            "input_tokens": 0,
            "output_tokens": 0,
        }

    def _execute_functional(self, entry: DirectAnswerEntry) -> dict:
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

        # QuestionFunctional.answer_question_directly returns a dict
        result = entry.question.answer_question_directly(
            scenario=entry.scenario, agent_traits=agent_traits
        )

        # Handle both dict and direct value returns
        if isinstance(result, dict):
            return {
                "answer": result.get("answer"),
                "comment": result.get("comment", "Functional question result"),
                "cached": False,
                "input_tokens": 0,
                "output_tokens": 0,
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
    # Check question-level first (QuestionFunctional)
    # These have answer_question_directly on the question itself
    if hasattr(question, "answer_question_directly"):
        return "functional"

    # Check agent-level direct answering
    # These have answer_question_directly on the agent
    if agent and hasattr(agent, "answer_question_directly"):
        return "agent_direct"

    # Default to LLM execution
    return "llm"
