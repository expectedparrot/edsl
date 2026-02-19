"""
Store Classes for the Job Execution System

Each store handles CRUD operations for a specific domain object,
abstracting the storage protocol details.
"""

import logging
import time
from datetime import datetime
from typing import Any

from .storage import StorageProtocol

logger = logging.getLogger(__name__)
from .models import (
    JobDefinition,
    JobStatus,
    JobState,
    InterviewDefinition,
    InterviewStatus,
    InterviewState,
    TaskDefinition,
    TaskState,
    TaskStatus,
    Answer,
)


class JobStore:
    """Handles reading/writing job data."""

    def __init__(self, storage: StorageProtocol):
        self._storage = storage

    # Write operations

    def create(self, definition: JobDefinition) -> None:
        """Write definition (persistent) and initialize status (volatile)."""
        # Persistent - metadata
        self._storage.write_persistent(definition.storage_key(), definition.to_dict())

        # Volatile - initialize counters
        status = JobStatus(job_id=definition.job_id)
        self._storage.write_volatile(status.state_key, JobState.RUNNING.value)
        self._storage.write_volatile(status.completed_interviews_key, 0)
        self._storage.write_volatile(status.failed_interviews_key, 0)

    def write_scenario(self, job_id: str, scenario_id: str, scenario: dict) -> None:
        self._storage.write_persistent(f"job:{job_id}:scenario:{scenario_id}", scenario)

    def write_agent(self, job_id: str, agent_id: str, agent: dict) -> None:
        self._storage.write_persistent(f"job:{job_id}:agent:{agent_id}", agent)

    def write_model(self, job_id: str, model_id: str, model: dict) -> None:
        self._storage.write_persistent(f"job:{job_id}:model:{model_id}", model)

    def write_question(self, job_id: str, question_id: str, question: dict) -> None:
        self._storage.write_persistent(f"job:{job_id}:question:{question_id}", question)

    def write_survey(self, job_id: str, survey: dict) -> None:
        """Store the survey for skip logic evaluation."""
        self._storage.write_persistent(f"job:{job_id}:survey", survey)

    # Batch write operations

    def write_questions_batch(self, job_id: str, questions: dict[str, dict]) -> None:
        """Write multiple questions in a single batch operation."""
        if not questions:
            return
        items = {
            f"job:{job_id}:question:{q_id}": q_data
            for q_id, q_data in questions.items()
        }
        self._storage.batch_write_persistent(items)

    def write_scenarios_batch(self, job_id: str, scenarios: dict[str, dict]) -> None:
        """Write multiple scenarios in a single batch operation."""
        if not scenarios:
            return
        items = {
            f"job:{job_id}:scenario:{s_id}": s_data
            for s_id, s_data in scenarios.items()
        }
        self._storage.batch_write_persistent(items)

    def write_agents_batch(self, job_id: str, agents: dict[str, dict]) -> None:
        """Write multiple agents in a single batch operation."""
        if not agents:
            return
        items = {
            f"job:{job_id}:agent:{a_id}": a_data for a_id, a_data in agents.items()
        }
        self._storage.batch_write_persistent(items)

    def write_models_batch(self, job_id: str, models: dict[str, dict]) -> None:
        """Write multiple models in a single batch operation."""
        if not models:
            return
        items = {
            f"job:{job_id}:model:{m_id}": m_data for m_id, m_data in models.items()
        }
        self._storage.batch_write_persistent(items)

    def increment_completed_interviews(self, job_id: str) -> int:
        return self._storage.increment_volatile(f"job:{job_id}:completed_interviews")

    def increment_failed_interviews(self, job_id: str) -> int:
        return self._storage.increment_volatile(f"job:{job_id}:failed_interviews")

    def set_state(self, job_id: str, state: JobState) -> None:
        self._storage.write_volatile(f"job:{job_id}:state", state.value)

    # Read operations

    def get_definition(self, job_id: str) -> JobDefinition | None:
        data = self._storage.read_persistent(f"job:{job_id}:meta")
        if data is None:
            return None
        return JobDefinition.from_dict(job_id, data)

    def get_status(self, job_id: str) -> JobStatus:
        return JobStatus(
            job_id=job_id,
            completed_interviews=self._storage.read_volatile(
                f"job:{job_id}:completed_interviews"
            )
            or 0,
            failed_interviews=self._storage.read_volatile(
                f"job:{job_id}:failed_interviews"
            )
            or 0,
        )

    def get_state(self, job_id: str) -> JobState:
        value = self._storage.read_volatile(f"job:{job_id}:state")
        return JobState(value) if value else JobState.PENDING

    def get_scenario(self, job_id: str, scenario_id: str) -> dict | None:
        return self._storage.read_persistent(f"job:{job_id}:scenario:{scenario_id}")

    def get_agent(self, job_id: str, agent_id: str) -> dict | None:
        return self._storage.read_persistent(f"job:{job_id}:agent:{agent_id}")

    def get_model(self, job_id: str, model_id: str) -> dict | None:
        return self._storage.read_persistent(f"job:{job_id}:model:{model_id}")

    def get_question(self, job_id: str, question_id: str) -> dict | None:
        return self._storage.read_persistent(f"job:{job_id}:question:{question_id}")

    # Batch read operations

    def get_definitions_batch(
        self, job_ids: list[str]
    ) -> dict[str, JobDefinition | None]:
        """Get multiple job definitions in a single operation."""
        if not job_ids:
            return {}
        keys = [f"job:{job_id}:meta" for job_id in job_ids]
        values = self._storage.batch_read_persistent(keys)
        result = {}
        for job_id in job_ids:
            key = f"job:{job_id}:meta"
            data = values.get(key)
            if data:
                result[job_id] = JobDefinition.from_dict(job_id, data)
            else:
                result[job_id] = None
        return result

    def get_statuses_batch(self, job_ids: list[str]) -> dict[str, JobStatus]:
        """Get multiple job statuses in a single operation."""
        if not job_ids:
            return {}
        # Build keys for batch read
        keys = []
        for job_id in job_ids:
            keys.append(f"job:{job_id}:completed_interviews")
            keys.append(f"job:{job_id}:failed_interviews")

        values = self._storage.batch_read_volatile(keys)
        result = {}
        for job_id in job_ids:
            completed = values.get(f"job:{job_id}:completed_interviews") or 0
            failed = values.get(f"job:{job_id}:failed_interviews") or 0
            result[job_id] = JobStatus(
                job_id=job_id, completed_interviews=completed, failed_interviews=failed
            )
        return result

    def get_states_batch(self, job_ids: list[str]) -> dict[str, JobState]:
        """Get multiple job states in a single operation."""
        if not job_ids:
            return {}
        keys = [f"job:{job_id}:state" for job_id in job_ids]
        values = self._storage.batch_read_volatile(keys)
        result = {}
        for job_id in job_ids:
            key = f"job:{job_id}:state"
            value = values.get(key)
            result[job_id] = JobState(value) if value else JobState.PENDING
        return result

    def get_scenarios_batch(
        self, job_id: str, scenario_ids: list[str]
    ) -> dict[str, dict | None]:
        """Get multiple scenarios in a single operation."""
        if not scenario_ids:
            return {}
        keys = [f"job:{job_id}:scenario:{sid}" for sid in scenario_ids]
        values = self._storage.batch_read_persistent(keys)
        return {sid: values.get(f"job:{job_id}:scenario:{sid}") for sid in scenario_ids}

    def get_agents_batch(
        self, job_id: str, agent_ids: list[str]
    ) -> dict[str, dict | None]:
        """Get multiple agents in a single operation."""
        if not agent_ids:
            return {}
        keys = [f"job:{job_id}:agent:{aid}" for aid in agent_ids]
        values = self._storage.batch_read_persistent(keys)
        return {aid: values.get(f"job:{job_id}:agent:{aid}") for aid in agent_ids}

    def get_models_batch(
        self, job_id: str, model_ids: list[str]
    ) -> dict[str, dict | None]:
        """Get multiple models in a single operation."""
        if not model_ids:
            return {}
        keys = [f"job:{job_id}:model:{mid}" for mid in model_ids]
        values = self._storage.batch_read_persistent(keys)
        return {mid: values.get(f"job:{job_id}:model:{mid}") for mid in model_ids}

    def get_questions_batch(
        self, job_id: str, question_ids: list[str]
    ) -> dict[str, dict | None]:
        """Get multiple questions in a single operation."""
        if not question_ids:
            return {}
        keys = [f"job:{job_id}:question:{qid}" for qid in question_ids]
        values = self._storage.batch_read_persistent(keys)
        return {qid: values.get(f"job:{job_id}:question:{qid}") for qid in question_ids}

    def get_survey(self, job_id: str) -> dict | None:
        """Get the survey for skip logic evaluation."""
        return self._storage.read_persistent(f"job:{job_id}:survey")

    # Composite operations

    def mark_interview_completed(
        self, job_id: str, interview_id: str, had_failures: bool
    ) -> None:
        """
        Increment appropriate counter and update state if job is done.

        Uses a set to ensure each interview is only counted once, preventing
        race conditions when multiple tasks complete simultaneously.
        """
        # Use set add to atomically check and mark interview as counted
        # Returns True if interview was newly added (not already in set)
        set_key = f"job:{job_id}:counted_interviews"
        was_new = self._storage.add_to_set(set_key, interview_id)

        if not was_new:
            # Interview already counted, skip increment
            return

        if had_failures:
            self.increment_failed_interviews(job_id)
        else:
            self.increment_completed_interviews(job_id)

        self._maybe_finalize(job_id)

    def _maybe_finalize(self, job_id: str) -> None:
        """Check if job is done and update state accordingly."""
        definition = self.get_definition(job_id)
        if definition is None:
            return

        status = self.get_status(job_id)

        if status.is_done(definition.total_interviews):
            new_state = status.compute_state(definition.total_interviews)
            self.set_state(job_id, new_state)


class InterviewStore:
    """Handles reading/writing interview data."""

    def __init__(self, storage: StorageProtocol):
        self._storage = storage

    # Write operations

    def create(self, definition: InterviewDefinition) -> None:
        """Write definition (persistent) and initialize status (volatile)."""
        # Persistent
        self._storage.write_persistent(definition.storage_key(), definition.to_dict())

        # Volatile - initialize counters
        status = InterviewStatus(interview_id=definition.interview_id)
        self._storage.write_volatile(status.completed_key, 0)
        self._storage.write_volatile(status.skipped_key, 0)
        self._storage.write_volatile(status.failed_key, 0)
        self._storage.write_volatile(status.blocked_key, 0)
        self._storage.write_volatile(status.state_key, InterviewState.RUNNING.value)

    def create_batch(self, definitions: list[InterviewDefinition]) -> None:
        """
        Create multiple interviews in a single batch operation.

        Much more efficient than calling create() for each interview.
        Reduces ~6 storage operations per interview to ~2 batch operations total.
        """
        if not definitions:
            return

        t0 = time.time()

        # Collect all data for batch writes
        persistent_items = {}  # Interview definitions
        volatile_items = {}  # Interview counters and state

        for defn in definitions:
            # Persistent - interview definition
            persistent_items[defn.storage_key()] = defn.to_dict()

            # Volatile - initialize counters
            status = InterviewStatus(interview_id=defn.interview_id)
            volatile_items[status.completed_key] = 0
            volatile_items[status.skipped_key] = 0
            volatile_items[status.failed_key] = 0
            volatile_items[status.blocked_key] = 0
            volatile_items[status.state_key] = InterviewState.RUNNING.value

        prep_time = (time.time() - t0) * 1000

        # Execute batch writes (2 operations instead of 6 per interview)
        t1 = time.time()
        self._storage.batch_write_persistent(persistent_items)
        persistent_time = (time.time() - t1) * 1000

        t2 = time.time()
        self._storage.batch_write_volatile(volatile_items)
        volatile_time = (time.time() - t2) * 1000

        logger.info(
            f"[InterviewStore.create_batch] {len(definitions)} interviews: "
            f"prep={prep_time:.1f}ms, persistent={persistent_time:.1f}ms ({len(persistent_items)} keys), "
            f"volatile={volatile_time:.1f}ms ({len(volatile_items)} keys)"
        )

    def increment_completed(self, interview_id: str) -> int:
        return self._storage.increment_volatile(f"interview:{interview_id}:completed")

    def increment_skipped(self, interview_id: str) -> int:
        return self._storage.increment_volatile(f"interview:{interview_id}:skipped")

    def increment_failed(self, interview_id: str) -> int:
        return self._storage.increment_volatile(f"interview:{interview_id}:failed")

    def increment_blocked(self, interview_id: str) -> int:
        return self._storage.increment_volatile(f"interview:{interview_id}:blocked")

    def set_state(self, interview_id: str, state: InterviewState) -> None:
        self._storage.write_volatile(f"interview:{interview_id}:state", state.value)

    # Read operations

    def get_definition(
        self, job_id: str, interview_id: str
    ) -> InterviewDefinition | None:
        key = f"job:{job_id}:interview:{interview_id}"
        data = self._storage.read_persistent(key)
        if data is None:
            return None
        return InterviewDefinition.from_dict(interview_id, job_id, data)

    def get_status(self, interview_id: str) -> InterviewStatus:
        return InterviewStatus(
            interview_id=interview_id,
            completed=self._storage.read_volatile(f"interview:{interview_id}:completed")
            or 0,
            skipped=self._storage.read_volatile(f"interview:{interview_id}:skipped")
            or 0,
            failed=self._storage.read_volatile(f"interview:{interview_id}:failed") or 0,
            blocked=self._storage.read_volatile(f"interview:{interview_id}:blocked")
            or 0,
        )

    def get_state(self, interview_id: str) -> InterviewState:
        value = self._storage.read_volatile(f"interview:{interview_id}:state")
        return InterviewState(value) if value else InterviewState.RUNNING

    def get_states_batch(self, interview_ids: list[str]) -> dict[str, InterviewState]:
        """Get multiple interview states in a single operation."""
        if not interview_ids:
            return {}
        keys = [f"interview:{iid}:state" for iid in interview_ids]
        values = self._storage.batch_read_volatile(keys)
        result = {}
        for interview_id in interview_ids:
            key = f"interview:{interview_id}:state"
            value = values.get(key)
            result[interview_id] = (
                InterviewState(value) if value else InterviewState.RUNNING
            )
        return result

    # Batch operations

    def get_definitions_batch(
        self, job_id: str, interview_ids: list[str], _timing: dict | None = None
    ) -> dict[str, InterviewDefinition | None]:
        """Get multiple interview definitions in a single operation."""
        import time as _time

        if not interview_ids:
            return {}

        _t0 = _time.time()
        keys = [f"job:{job_id}:interview:{iid}" for iid in interview_ids]
        if _timing is not None:
            _timing["build_keys"] = (_time.time() - _t0) * 1000

        _t0 = _time.time()
        values = self._storage.batch_read_persistent(keys)
        if _timing is not None:
            _timing["db_call"] = (_time.time() - _t0) * 1000

        _t0 = _time.time()
        result = {}
        for interview_id in interview_ids:
            key = f"job:{job_id}:interview:{interview_id}"
            data = values.get(key)
            if data:
                result[interview_id] = InterviewDefinition.from_dict(
                    interview_id, job_id, data
                )
            else:
                result[interview_id] = None
        if _timing is not None:
            _timing["deserialize"] = (_time.time() - _t0) * 1000
            _timing["n"] = len(interview_ids)

        return result

    def get_statuses_batch(
        self, interview_ids: list[str]
    ) -> dict[str, InterviewStatus]:
        """Get multiple interview statuses in a single operation."""
        if not interview_ids:
            return {}
        # Build keys for batch read
        keys = []
        for interview_id in interview_ids:
            keys.append(f"interview:{interview_id}:completed")
            keys.append(f"interview:{interview_id}:skipped")
            keys.append(f"interview:{interview_id}:failed")
            keys.append(f"interview:{interview_id}:blocked")

        values = self._storage.batch_read_volatile(keys)
        result = {}
        for interview_id in interview_ids:
            completed = values.get(f"interview:{interview_id}:completed") or 0
            skipped = values.get(f"interview:{interview_id}:skipped") or 0
            failed = values.get(f"interview:{interview_id}:failed") or 0
            blocked = values.get(f"interview:{interview_id}:blocked") or 0
            result[interview_id] = InterviewStatus(
                interview_id=interview_id,
                completed=completed,
                skipped=skipped,
                failed=failed,
                blocked=blocked,
            )
        return result

    # Composite operations

    def mark_task_completed(self, job_id: str, interview_id: str) -> None:
        """Increment completed count and update state if done."""
        self.increment_completed(interview_id)
        self._maybe_finalize(job_id, interview_id)

    def mark_task_skipped(self, job_id: str, interview_id: str) -> None:
        self.increment_skipped(interview_id)
        self._maybe_finalize(job_id, interview_id)

    def mark_task_failed(self, job_id: str, interview_id: str) -> None:
        self.increment_failed(interview_id)
        self._maybe_finalize(job_id, interview_id)

    def mark_task_blocked(self, job_id: str, interview_id: str) -> None:
        self.increment_blocked(interview_id)
        self._maybe_finalize(job_id, interview_id)

    def _maybe_finalize(self, job_id: str, interview_id: str) -> None:
        """Check if interview is done and update state accordingly."""
        definition = self.get_definition(job_id, interview_id)
        if definition is None:
            return

        status = self.get_status(interview_id)

        if status.is_done(definition.total_tasks):
            new_state = status.compute_state(definition.total_tasks)
            self.set_state(interview_id, new_state)


class TaskStore:
    """Handles reading/writing task data."""

    # Class-level profiling for create_batch calls
    _batch_call_count = 0
    _batch_total_time_ms = 0.0
    _batch_total_tasks = 0

    @classmethod
    def reset_batch_stats(cls):
        cls._batch_call_count = 0
        cls._batch_total_time_ms = 0.0
        cls._batch_total_tasks = 0

    @classmethod
    def get_batch_stats(cls):
        return {
            "calls": cls._batch_call_count,
            "total_time_ms": cls._batch_total_time_ms,
            "total_tasks": cls._batch_total_tasks,
            "avg_time_per_call_ms": cls._batch_total_time_ms / cls._batch_call_count
            if cls._batch_call_count > 0
            else 0,
        }

    def __init__(self, storage: StorageProtocol):
        self._storage = storage

    # Write operations

    def create(self, definition: TaskDefinition) -> None:
        """Write definition (persistent) and initialize state (volatile)."""
        # Persistent
        self._storage.write_persistent(definition.storage_key(), definition.to_dict())

        # Task index for O(1) lookup: task_id -> (job_id, interview_id)
        self._storage.write_volatile(
            f"task:{definition.task_id}:location",
            {"job_id": definition.job_id, "interview_id": definition.interview_id},
        )

        # Volatile state
        initial_status = (
            TaskStatus.READY if len(definition.depends_on) == 0 else TaskStatus.PENDING
        )
        state = TaskState(
            task_id=definition.task_id, unmet_deps=len(definition.depends_on)
        )

        self._storage.write_volatile(state.status_key, initial_status.value)
        self._storage.write_volatile(state.unmet_deps_key, len(definition.depends_on))
        self._storage.write_volatile(state.attempts_key, {})

        # Add to ready set if no dependencies
        if initial_status == TaskStatus.READY:
            self._storage.add_to_set(
                f"job:{definition.job_id}:ready_tasks", definition.task_id
            )

    def create_batch(self, definitions: list[TaskDefinition]) -> None:
        """
        Create multiple tasks in a single batch operation.

        Much more efficient than calling create() for each task.
        Reduces ~5-6 storage operations per task to ~4 batch operations total.
        """
        if not definitions:
            return

        t0 = time.time()

        # Collect all data for batch writes
        persistent_items = {}  # Task definitions
        volatile_items = {}  # Task states (status, unmet_deps, attempts, location)
        ready_task_ids_by_job: dict[
            str, list[str]
        ] = {}  # job_id -> list of ready task_ids

        for defn in definitions:
            # Persistent - task definition
            persistent_items[defn.storage_key()] = defn.to_dict()

            # Volatile - task location index
            volatile_items[f"task:{defn.task_id}:location"] = {
                "job_id": defn.job_id,
                "interview_id": defn.interview_id,
            }

            # Volatile - task state
            initial_status = (
                TaskStatus.READY if len(defn.depends_on) == 0 else TaskStatus.PENDING
            )
            volatile_items[f"task:{defn.task_id}:status"] = initial_status.value
            volatile_items[f"task:{defn.task_id}:unmet_deps"] = len(defn.depends_on)
            volatile_items[f"task:{defn.task_id}:attempts"] = {}

            # Track ready tasks by job for batch add_to_set
            if initial_status == TaskStatus.READY:
                if defn.job_id not in ready_task_ids_by_job:
                    ready_task_ids_by_job[defn.job_id] = []
                ready_task_ids_by_job[defn.job_id].append(defn.task_id)

        prep_time = (time.time() - t0) * 1000

        # Execute batch writes (4 operations instead of 5-6 per task)
        t1 = time.time()
        self._storage.batch_write_persistent(persistent_items)
        persistent_time = (time.time() - t1) * 1000

        t2 = time.time()
        self._storage.batch_write_volatile(volatile_items)
        volatile_time = (time.time() - t2) * 1000

        # Batch add ready tasks to ready sets
        t3 = time.time()
        total_ready = 0
        for job_id, task_ids in ready_task_ids_by_job.items():
            self._storage.add_multiple_to_set(f"job:{job_id}:ready_tasks", task_ids)
            total_ready += len(task_ids)
        ready_set_time = (time.time() - t3) * 1000

        total_time = (time.time() - t0) * 1000

        # Track class-level stats
        TaskStore._batch_call_count += 1
        TaskStore._batch_total_time_ms += total_time
        TaskStore._batch_total_tasks += len(definitions)

        logger.info(
            f"[TaskStore.create_batch] {len(definitions)} tasks: "
            f"prep={prep_time:.1f}ms, persistent={persistent_time:.1f}ms ({len(persistent_items)} keys), "
            f"volatile={volatile_time:.1f}ms ({len(volatile_items)} keys), "
            f"ready_set={ready_set_time:.1f}ms ({total_ready} ready tasks)"
        )

    def set_status(self, task_id: str, status: TaskStatus) -> None:
        self._storage.write_volatile(f"task:{task_id}:status", status.value)

    def decrement_unmet_deps(self, task_id: str) -> int:
        """Returns new count after decrement."""
        return self._storage.increment_volatile(f"task:{task_id}:unmet_deps", -1)

    def increment_attempt(self, task_id: str, error_type: str) -> int:
        """Increment attempt count for a specific error type, return new count."""
        key = f"task:{task_id}:attempts"
        attempts = self._storage.read_volatile(key) or {}
        attempts[error_type] = attempts.get(error_type, 0) + 1
        self._storage.write_volatile(key, attempts)
        return attempts[error_type]

    def set_error(self, task_id: str, error_type: str, error_message: str) -> None:
        self._storage.write_volatile(
            f"task:{task_id}:last_error", {"type": error_type, "message": error_message}
        )

    def set_next_retry(self, task_id: str, retry_time: datetime) -> None:
        self._storage.write_volatile(
            f"task:{task_id}:next_retry", retry_time.isoformat()
        )

    # Read operations

    def get_definition(
        self, job_id: str, interview_id: str, task_id: str
    ) -> TaskDefinition | None:
        key = f"job:{job_id}:interview:{interview_id}:task:{task_id}"
        data = self._storage.read_persistent(key)
        if data is None:
            return None
        return TaskDefinition.from_dict(task_id, job_id, interview_id, data)

    def get_state(self, task_id: str) -> TaskState:
        last_error = self._storage.read_volatile(f"task:{task_id}:last_error")
        next_retry = self._storage.read_volatile(f"task:{task_id}:next_retry")

        status_value = self._storage.read_volatile(f"task:{task_id}:status")

        return TaskState(
            task_id=task_id,
            status=TaskStatus(status_value) if status_value else TaskStatus.PENDING,
            unmet_deps=self._storage.read_volatile(f"task:{task_id}:unmet_deps") or 0,
            attempts=self._storage.read_volatile(f"task:{task_id}:attempts") or {},
            last_error_type=last_error.get("type") if last_error else None,
            last_error_message=last_error.get("message") if last_error else None,
            next_retry=datetime.fromisoformat(next_retry) if next_retry else None,
        )

    def get_status(self, task_id: str) -> TaskStatus:
        value = self._storage.read_volatile(f"task:{task_id}:status")
        return TaskStatus(value) if value else TaskStatus.PENDING

    def get_statuses_batch(self, task_ids: list[str]) -> dict[str, TaskStatus]:
        """
        Get statuses for multiple tasks in a single batch operation.
        Much more efficient than calling get_status() for each task.
        Returns a dict mapping task_id to TaskStatus.
        """
        if not task_ids:
            return {}

        # Build keys for batch read
        keys = [f"task:{task_id}:status" for task_id in task_ids]

        # Batch read all statuses
        values = self._storage.batch_read_volatile(keys)

        # Build result dict
        result = {}
        for task_id in task_ids:
            key = f"task:{task_id}:status"
            value = values.get(key)
            result[task_id] = TaskStatus(value) if value else TaskStatus.PENDING
        return result

    def get_location(self, task_id: str) -> tuple[str, str]:
        """Get (job_id, interview_id) for a task. O(1) lookup."""
        location = self._storage.read_volatile(f"task:{task_id}:location")
        return location["job_id"], location["interview_id"]

    def get_locations_batch(self, task_ids: list[str]) -> dict[str, tuple[str, str]]:
        """Get (job_id, interview_id) for multiple tasks in a single operation."""
        if not task_ids:
            return {}
        keys = [f"task:{task_id}:location" for task_id in task_ids]
        values = self._storage.batch_read_volatile(keys)
        result = {}
        for task_id in task_ids:
            location = values.get(f"task:{task_id}:location")
            if location:
                result[task_id] = (location["job_id"], location["interview_id"])
        return result

    def get_definitions_batch(
        self,
        job_id: str,
        interview_id: str,
        task_ids: list[str],
        _timing: dict | None = None,
    ) -> dict[str, TaskDefinition | None]:
        """Get multiple task definitions in a single operation."""
        import time as _time

        if not task_ids:
            return {}

        _t0 = _time.time()
        keys = [f"job:{job_id}:interview:{interview_id}:task:{tid}" for tid in task_ids]
        if _timing is not None:
            _timing["build_keys"] = (_time.time() - _t0) * 1000

        _t0 = _time.time()
        values = self._storage.batch_read_persistent(keys)
        if _timing is not None:
            _timing["db_call"] = (_time.time() - _t0) * 1000

        _t0 = _time.time()
        result = {}
        for task_id in task_ids:
            key = f"job:{job_id}:interview:{interview_id}:task:{task_id}"
            data = values.get(key)
            if data:
                result[task_id] = TaskDefinition.from_dict(
                    task_id, job_id, interview_id, data
                )
            else:
                result[task_id] = None
        if _timing is not None:
            _timing["deserialize"] = (_time.time() - _t0) * 1000
            _timing["n"] = len(task_ids)

        return result

    def set_statuses_batch(self, task_ids: list[str], status: TaskStatus) -> None:
        """Set status for multiple tasks in a single operation."""
        if not task_ids:
            return
        items = {f"task:{task_id}:status": status.value for task_id in task_ids}
        self._storage.batch_write_volatile(items)

    # Ready task operations

    def pop_ready_task(self, job_id: str) -> str | None:
        """Atomically remove and return a ready task_id, or None if empty."""
        return self._storage.pop_from_set(f"job:{job_id}:ready_tasks")

    def pop_ready_tasks_batch(self, job_id: str, count: int) -> list[str]:
        """Atomically remove and return up to count ready task_ids."""
        return self._storage.pop_multiple_from_set(f"job:{job_id}:ready_tasks", count)

    def add_to_ready(self, job_id: str, task_id: str) -> None:
        self._storage.add_to_set(f"job:{job_id}:ready_tasks", task_id)

    def get_ready_count(self, job_id: str) -> int:
        """Get the number of ready tasks for a job."""
        return self._storage.set_size(f"job:{job_id}:ready_tasks")

    # Composite operations

    def mark_dependency_satisfied(self, job_id: str, task_id: str) -> bool:
        """
        Decrement unmet_deps. If now zero, mark ready and add to ready set.
        Returns True if task became ready.
        """
        new_count = self.decrement_unmet_deps(task_id)
        if new_count == 0:
            self.set_status(task_id, TaskStatus.READY)
            self.add_to_ready(job_id, task_id)
            return True
        return False


class AnswerStore:
    """Handles reading/writing answers - write-only, dual storage."""

    def __init__(self, storage: StorageProtocol):
        self._storage = storage

    # Write operations

    def store(self, answer: Answer) -> None:
        """Write to both persistent and volatile storage."""
        key = answer.storage_key()
        data = answer.to_dict()

        # Both stores - persistent for durability, volatile for fast reads
        self._storage.write_persistent(key, data)
        self._storage.write_volatile(key, data)

    # Read operations

    def get(self, job_id: str, interview_id: str, question_name: str) -> Answer | None:
        """Read from volatile first (fast), fall back to persistent."""
        key = f"job:{job_id}:interview:{interview_id}:answer:{question_name}"

        # Try volatile first
        data = self._storage.read_volatile(key)

        # Fall back to persistent
        if data is None:
            data = self._storage.read_persistent(key)

        if data is None:
            return None

        return Answer.from_dict(job_id, interview_id, question_name, data)

    def exists(self, job_id: str, interview_id: str, question_name: str) -> bool:
        """Quick check if answer exists (volatile only for speed)."""
        key = f"job:{job_id}:interview:{interview_id}:answer:{question_name}"
        return self._storage.read_volatile(key) is not None

    def get_for_interview(
        self, job_id: str, interview_id: str, question_names: list[str]
    ) -> dict[str, Answer]:
        """Batch read answers for an interview - used during prompt rendering."""
        if not question_names:
            return {}

        # Build keys for batch read
        keys = [
            f"job:{job_id}:interview:{interview_id}:answer:{qn}"
            for qn in question_names
        ]

        # Try volatile first (fast path)
        volatile_values = self._storage.batch_read_volatile(keys)

        results = {}
        missing_questions = []

        for question_name in question_names:
            key = f"job:{job_id}:interview:{interview_id}:answer:{question_name}"
            data = volatile_values.get(key)
            if data is not None:
                results[question_name] = Answer.from_dict(
                    job_id, interview_id, question_name, data
                )
            else:
                missing_questions.append(question_name)

        # Fall back to persistent for missing keys
        if missing_questions:
            missing_keys = [
                f"job:{job_id}:interview:{interview_id}:answer:{qn}"
                for qn in missing_questions
            ]
            persistent_values = self._storage.batch_read_persistent(missing_keys)
            for question_name in missing_questions:
                key = f"job:{job_id}:interview:{interview_id}:answer:{question_name}"
                data = persistent_values.get(key)
                if data is not None:
                    results[question_name] = Answer.from_dict(
                        job_id, interview_id, question_name, data
                    )

        return results

    def get_all_for_interview(self, job_id: str, interview_id: str) -> list[Answer]:
        """Get all answers for an interview - used for Result assembly."""
        pattern = f"job:{job_id}:interview:{interview_id}:answer:*"

        # Scan volatile keys first
        keys = self._storage.scan_keys_volatile(pattern)

        # Extract question names from keys
        # Key format: job:{job_id}:interview:{interview_id}:answer:{question_name}
        question_names = []
        for key in keys:
            parts = key.split(":")
            if len(parts) >= 6:
                question_names.append(parts[5])

        if not question_names:
            return []

        # Use batch read instead of N individual gets
        answers_dict = self.get_for_interview(job_id, interview_id, question_names)
        return list(answers_dict.values())

    def get_for_interviews_batch(
        self, job_id: str, interview_ids: list[str], question_names: list[str]
    ) -> dict[str, dict[str, Answer]]:
        """
        Batch read answers for multiple interviews in a single operation.

        Returns: dict mapping interview_id -> dict mapping question_name -> Answer
        Much more efficient than calling get_for_interview() for each interview.
        """
        if not interview_ids or not question_names:
            return {}

        # Build all keys for all interviews
        keys = []
        for interview_id in interview_ids:
            for qn in question_names:
                keys.append(f"job:{job_id}:interview:{interview_id}:answer:{qn}")

        # Single batch read for all keys
        volatile_values = self._storage.batch_read_volatile(keys)

        # Find missing keys and fetch from persistent
        missing_keys = [k for k in keys if volatile_values.get(k) is None]
        if missing_keys:
            persistent_values = self._storage.batch_read_persistent(missing_keys)
            for k, v in persistent_values.items():
                if v is not None:
                    volatile_values[k] = v

        # Build result structure
        result: dict[str, dict[str, Answer]] = {iid: {} for iid in interview_ids}
        for interview_id in interview_ids:
            for question_name in question_names:
                key = f"job:{job_id}:interview:{interview_id}:answer:{question_name}"
                data = volatile_values.get(key)
                if data is not None:
                    result[interview_id][question_name] = Answer.from_dict(
                        job_id, interview_id, question_name, data
                    )

        return result
