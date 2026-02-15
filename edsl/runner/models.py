"""
Data Models for the Job Execution System

Defines the core domain objects:
- Job: A complete unit of work (Survey + Scenarios + Agents + Models)
- Interview: One combination of scenario x agent x model
- Task: A single question to be answered within an interview
- Answer: The result of executing a task
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
import uuid


# =============================================================================
# Exceptions
# =============================================================================


class TaskExecutionError(Exception):
    """
    Raised when a task fails and stop_on_exception=True.

    Attributes:
        task_id: ID of the failed task
        job_id: ID of the job containing the task
        interview_id: ID of the interview containing the task
        error_type: Classification of the error
        error_message: Detailed error message
    """

    def __init__(
        self,
        task_id: str,
        job_id: str,
        interview_id: str,
        error_type: str,
        error_message: str,
    ):
        self.task_id = task_id
        self.job_id = job_id
        self.interview_id = interview_id
        self.error_type = error_type
        self.error_message = error_message
        super().__init__(f"Task {task_id} failed: [{error_type}] {error_message}")


# =============================================================================
# Enums
# =============================================================================


class JobState(Enum):
    """Job lifecycle states."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_FAILURES = "completed_with_failures"
    CANCELLED = "cancelled"


class InterviewState(Enum):
    """Interview lifecycle states."""

    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_FAILURES = "completed_with_failures"


class TaskStatus(Enum):
    """Task lifecycle states."""

    PENDING = "pending"  # Waiting for dependencies
    READY = "ready"  # Dependencies satisfied, awaiting rendering
    RENDERING = "rendering"  # Prompt being constructed
    QUEUED = "queued"  # In execution queue
    RUNNING = "running"  # Being executed
    COMPLETED = "completed"  # Successfully completed
    FAILED = "failed"  # Permanently failed
    SKIPPED = "skipped"  # Skipped due to skip logic
    BLOCKED = "blocked"  # Blocked by failed dependency
    RETRY_PENDING = "retry_pending"  # Awaiting retry


# =============================================================================
# Retry Policy
# =============================================================================


@dataclass
class RetryPolicy:
    """Configuration for retry behavior per error type."""

    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    retryable: bool = True

    def to_dict(self) -> dict:
        return {
            "max_attempts": self.max_attempts,
            "base_delay_seconds": self.base_delay_seconds,
            "retryable": self.retryable,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RetryPolicy":
        return cls(**data)


# Default retry policies by error type
DEFAULT_RETRY_POLICIES = {
    "network_timeout": RetryPolicy(
        max_attempts=3, base_delay_seconds=1.0, retryable=True
    ),
    "rate_limit": RetryPolicy(max_attempts=5, base_delay_seconds=2.0, retryable=True),
    "server_error": RetryPolicy(max_attempts=3, base_delay_seconds=1.0, retryable=True),
    "parse_error": RetryPolicy(max_attempts=2, base_delay_seconds=0.5, retryable=True),
    "render_error": RetryPolicy(max_attempts=2, base_delay_seconds=0.5, retryable=True),
    "content_policy": RetryPolicy(
        max_attempts=1, base_delay_seconds=0.0, retryable=False
    ),
    "invalid_request": RetryPolicy(
        max_attempts=1, base_delay_seconds=0.0, retryable=False
    ),
}


# =============================================================================
# Job Definition & Status
# =============================================================================


@dataclass
class JobDefinition:
    """
    Persistent - immutable after creation.

    Represents the complete definition of a job including all metadata
    and references to shared resources.
    """

    job_id: str
    user_id: str
    created_at: datetime
    total_interviews: int
    interview_ids: list[str]
    retry_policies: dict[str, RetryPolicy]
    dag: dict[str, set[str]]  # question_name -> set of dependency question_names

    # IDs of stored resources
    scenario_ids: list[str]
    agent_ids: list[str]
    model_ids: list[str]
    question_ids: list[str]

    # Iterations - number of times to run each interview
    n_iterations: int = 1

    def storage_key(self) -> str:
        return f"job:{self.job_id}:meta"

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "total_interviews": self.total_interviews,
            "interview_ids": self.interview_ids,
            "retry_policies": {k: v.to_dict() for k, v in self.retry_policies.items()},
            "dag": {k: list(v) for k, v in self.dag.items()},
            "scenario_ids": self.scenario_ids,
            "agent_ids": self.agent_ids,
            "model_ids": self.model_ids,
            "question_ids": self.question_ids,
            "n_iterations": self.n_iterations,
        }

    @classmethod
    def from_dict(cls, job_id: str, data: dict) -> "JobDefinition":
        return cls(
            job_id=job_id,
            user_id=data["user_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            total_interviews=data["total_interviews"],
            interview_ids=data["interview_ids"],
            retry_policies={
                k: RetryPolicy.from_dict(v) for k, v in data["retry_policies"].items()
            },
            dag={k: set(v) for k, v in data["dag"].items()},
            scenario_ids=data["scenario_ids"],
            agent_ids=data["agent_ids"],
            model_ids=data["model_ids"],
            question_ids=data["question_ids"],
            n_iterations=data.get("n_iterations", 1),
        )


@dataclass
class JobStatus:
    """
    Volatile - updated as interviews complete.

    Tracks the progress of a job.
    """

    job_id: str
    completed_interviews: int = 0
    failed_interviews: int = 0

    @property
    def finished_count(self) -> int:
        return self.completed_interviews + self.failed_interviews

    def is_done(self, total_interviews: int) -> bool:
        # Use >= for safety in case of race conditions causing over-counting
        return self.finished_count >= total_interviews

    def compute_state(self, total_interviews: int) -> JobState:
        if not self.is_done(total_interviews):
            return JobState.RUNNING
        if self.failed_interviews == 0:
            return JobState.COMPLETED
        return JobState.COMPLETED_WITH_FAILURES

    # Storage keys
    def _key(self, field_name: str) -> str:
        return f"job:{self.job_id}:{field_name}"

    @property
    def state_key(self) -> str:
        return self._key("state")

    @property
    def completed_interviews_key(self) -> str:
        return self._key("completed_interviews")

    @property
    def failed_interviews_key(self) -> str:
        return self._key("failed_interviews")


# =============================================================================
# Interview Definition & Status
# =============================================================================


@dataclass
class InterviewDefinition:
    """
    Persistent - immutable after creation.

    Represents one scenario x agent x model combination at a specific iteration.
    When n > 1, multiple interviews are created for each combination, each with
    a different iteration number (0, 1, 2, ..., n-1).
    """

    interview_id: str
    job_id: str
    scenario_id: str
    agent_id: str
    model_id: str
    total_tasks: int
    task_ids: list[str]
    iteration: int = 0  # Which iteration this interview represents (0-indexed)
    # Randomized question options per question (question_name -> permuted options list)
    # Only populated for questions in survey.questions_to_randomize
    question_option_permutations: dict[str, list] = field(default_factory=dict)

    def storage_key(self) -> str:
        return f"job:{self.job_id}:interview:{self.interview_id}"

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "agent_id": self.agent_id,
            "model_id": self.model_id,
            "total_tasks": self.total_tasks,
            "task_ids": self.task_ids,
            "iteration": self.iteration,
            "question_option_permutations": self.question_option_permutations,
        }

    @classmethod
    def from_dict(
        cls, interview_id: str, job_id: str, data: dict
    ) -> "InterviewDefinition":
        return cls(
            interview_id=interview_id,
            job_id=job_id,
            scenario_id=data["scenario_id"],
            agent_id=data["agent_id"],
            model_id=data["model_id"],
            total_tasks=data["total_tasks"],
            task_ids=data["task_ids"],
            iteration=data.get("iteration", 0),
            question_option_permutations=data.get("question_option_permutations", {}),
        )


@dataclass
class InterviewStatus:
    """
    Volatile - updated as tasks complete.

    Tracks the progress of an interview.
    """

    interview_id: str
    completed: int = 0
    skipped: int = 0
    failed: int = 0
    blocked: int = 0

    @property
    def finished_count(self) -> int:
        return self.completed + self.skipped + self.failed + self.blocked

    def is_done(self, total_tasks: int) -> bool:
        # Use >= for safety in case of race conditions causing over-counting
        return self.finished_count >= total_tasks

    def compute_state(self, total_tasks: int) -> InterviewState:
        if not self.is_done(total_tasks):
            return InterviewState.RUNNING
        if self.failed == 0 and self.blocked == 0:
            return InterviewState.COMPLETED
        return InterviewState.COMPLETED_WITH_FAILURES

    # Storage keys
    def _key(self, field_name: str) -> str:
        return f"interview:{self.interview_id}:{field_name}"

    @property
    def completed_key(self) -> str:
        return self._key("completed")

    @property
    def skipped_key(self) -> str:
        return self._key("skipped")

    @property
    def failed_key(self) -> str:
        return self._key("failed")

    @property
    def blocked_key(self) -> str:
        return self._key("blocked")

    @property
    def state_key(self) -> str:
        return self._key("state")


# =============================================================================
# Task Definition & State
# =============================================================================


@dataclass
class TaskDefinition:
    """
    Persistent - immutable after creation.

    Represents a single question to be answered.
    """

    task_id: str
    job_id: str
    interview_id: str
    scenario_id: str
    question_id: str
    question_name: str
    agent_id: str
    model_id: str
    depends_on: list[str]  # task_ids this task depends on
    dependents: list[str]  # task_ids that depend on this task
    iteration: int = 0  # Which iteration this task belongs to
    execution_type: str = "llm"  # "llm", "agent_direct", or "functional"

    def storage_key(self) -> str:
        return f"job:{self.job_id}:interview:{self.interview_id}:task:{self.task_id}"

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "question_id": self.question_id,
            "question_name": self.question_name,
            "agent_id": self.agent_id,
            "model_id": self.model_id,
            "depends_on": self.depends_on,
            "dependents": self.dependents,
            "iteration": self.iteration,
            "execution_type": self.execution_type,
        }

    @classmethod
    def from_dict(
        cls, task_id: str, job_id: str, interview_id: str, data: dict
    ) -> "TaskDefinition":
        return cls(
            task_id=task_id,
            job_id=job_id,
            interview_id=interview_id,
            scenario_id=data["scenario_id"],
            question_id=data["question_id"],
            question_name=data["question_name"],
            agent_id=data["agent_id"],
            model_id=data["model_id"],
            depends_on=data["depends_on"],
            dependents=data["dependents"],
            iteration=data.get("iteration", 0),
            execution_type=data.get("execution_type", "llm"),
        )


@dataclass
class TaskState:
    """
    Volatile - updated during execution.

    Tracks the current state of a task.
    """

    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    unmet_deps: int = 0
    attempts: dict[str, int] = field(default_factory=dict)
    last_error_type: str | None = None
    last_error_message: str | None = None
    next_retry: datetime | None = None

    # Storage keys
    def _key(self, field_name: str) -> str:
        return f"task:{self.task_id}:{field_name}"

    @property
    def status_key(self) -> str:
        return self._key("status")

    @property
    def unmet_deps_key(self) -> str:
        return self._key("unmet_deps")

    @property
    def attempts_key(self) -> str:
        return self._key("attempts")

    @property
    def last_error_key(self) -> str:
        return self._key("last_error")

    @property
    def next_retry_key(self) -> str:
        return self._key("next_retry")


# =============================================================================
# Answer
# =============================================================================


@dataclass
class Answer:
    """
    Immutable once written - stored in both persistent and volatile storage.

    Represents the result of executing a task, with all metadata needed
    to construct EDSL Result objects.
    """

    job_id: str
    interview_id: str
    question_name: str
    answer: Any  # The actual answer content
    created_at: datetime

    # Prompts used
    system_prompt: str | None = None
    user_prompt: str | None = None

    # Response metadata
    comment: str | None = None
    cached: bool = False
    input_tokens: int | None = None
    output_tokens: int | None = None
    raw_model_response: dict | None = None
    generated_tokens: str | None = None

    # Model info
    model_id: str | None = None

    # Pricing info (to match EDSL Result structure)
    input_price_per_million_tokens: float | None = None
    output_price_per_million_tokens: float | None = None

    # Cache and validation info
    cache_key: str | None = None
    validated: bool | None = None
    reasoning_summary: str | None = None

    def storage_key(self) -> str:
        return f"job:{self.job_id}:interview:{self.interview_id}:answer:{self.question_name}"

    @property
    def tokens_used(self) -> int | None:
        """Total tokens used (input + output)."""
        if self.input_tokens is None and self.output_tokens is None:
            return None
        return (self.input_tokens or 0) + (self.output_tokens or 0)

    def to_dict(self) -> dict:
        return {
            "answer": self.answer,
            "created_at": self.created_at.isoformat(),
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "comment": self.comment,
            "cached": self.cached,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "raw_model_response": self.raw_model_response,
            "generated_tokens": self.generated_tokens,
            "model_id": self.model_id,
            "input_price_per_million_tokens": self.input_price_per_million_tokens,
            "output_price_per_million_tokens": self.output_price_per_million_tokens,
            "cache_key": self.cache_key,
            "validated": self.validated,
            "reasoning_summary": self.reasoning_summary,
        }

    @classmethod
    def from_dict(
        cls, job_id: str, interview_id: str, question_name: str, data: dict
    ) -> "Answer":
        return cls(
            job_id=job_id,
            interview_id=interview_id,
            question_name=question_name,
            answer=data["answer"],
            created_at=datetime.fromisoformat(data["created_at"]),
            system_prompt=data.get("system_prompt"),
            user_prompt=data.get("user_prompt"),
            comment=data.get("comment"),
            cached=data.get("cached", False),
            input_tokens=data.get("input_tokens"),
            output_tokens=data.get("output_tokens"),
            raw_model_response=data.get("raw_model_response"),
            generated_tokens=data.get("generated_tokens"),
            model_id=data.get("model_id"),
            input_price_per_million_tokens=data.get("input_price_per_million_tokens"),
            output_price_per_million_tokens=data.get("output_price_per_million_tokens"),
            cache_key=data.get("cache_key"),
            validated=data.get("validated"),
            reasoning_summary=data.get("reasoning_summary"),
        )


# =============================================================================
# Utility Functions
# =============================================================================


def generate_id() -> str:
    """Generate a unique ID for jobs, interviews, tasks, etc."""
    return str(uuid.uuid4())
