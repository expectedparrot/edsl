"""
JobService - The core orchestrator for job execution.

Handles:
- Job submission and decomposition into interviews/tasks
- Task completion flow and dependency propagation
- Interview and job finalization
"""

import logging
import time
from datetime import datetime
from typing import Any, TYPE_CHECKING
import itertools

logger = logging.getLogger(__name__)

from .storage import StorageProtocol
from .stores import JobStore, InterviewStore, TaskStore, AnswerStore
from .storage_sqlalchemy import reset_db_stats, get_db_stats
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
    RetryPolicy,
    DEFAULT_RETRY_POLICIES,
    generate_id,
)

# EDSL imports - relative since this module lives inside edsl package
from ..language_models import LanguageModel
from ..surveys import Survey
from ..surveys.base import EndOfSurvey
from ..results import Result, Results
from ..agents import Agent
from ..scenarios import Scenario
from ..questions import QuestionBase

if TYPE_CHECKING:
    # Avoid circular import - these would be EDSL types
    pass


class JobService:
    """
    Top-level orchestrator for job execution.

    Combines all stores and handles the complete lifecycle of jobs,
    from submission through completion.
    """

    def __init__(self, storage: StorageProtocol):
        self._storage = storage
        self._jobs = JobStore(storage)
        self._interviews = InterviewStore(storage)
        self._tasks = TaskStore(storage)
        self._answers = AnswerStore(storage)
        self._job_stop_on_exception: dict[str, bool] = {}  # job_id -> stop_on_exception
        self._original_models: dict[
            str, dict[str, Any]
        ] = {}  # job_id -> {model_id -> model_obj}

    @property
    def jobs(self) -> JobStore:
        return self._jobs

    @property
    def interviews(self) -> InterviewStore:
        return self._interviews

    @property
    def tasks(self) -> TaskStore:
        return self._tasks

    @property
    def answers(self) -> AnswerStore:
        return self._answers

    def get_model_for_task(self, job_id: str, model_id: str) -> Any:
        """
        Get the actual model object for LLM execution.

        Prefers the original (unserialized) model object if available,
        since some attributes like `func` don't survive serialization.
        Falls back to deserializing from stored dict.
        """
        # Prefer original model object (preserves func, closures, etc.)
        job_models = self._original_models.get(job_id)
        if job_models and model_id in job_models:
            return job_models[model_id]

        model_data = self._jobs.get_model(job_id, model_id)
        if model_data is None:
            return None

        return LanguageModel.from_dict(model_data)

    # =========================================================================
    # Job Submission
    # =========================================================================

    def submit_job(
        self,
        job: Any,  # EDSL Job object
        user_id: str = "anonymous",
        retry_policies: dict[str, RetryPolicy] | None = None,
        n: int = 1,  # Number of iterations to run each interview
        job_id: str | None = None,  # Pre-generated job ID (for GCS upload flow)
        stop_on_exception: bool = False,  # Compatibility parameter (not used yet)
    ) -> str:
        """
        Submit an EDSL Job for execution.

        This decomposes the job into interviews and tasks, storing all
        necessary data and initializing the execution pipeline.

        Args:
            job: EDSL Job object to execute
            user_id: User ID for tracking
            retry_policies: Custom retry policies by error type
            n: Number of iterations to run each interview. When n > 1,
               each (scenario, agent, model) combination is executed n times
               with different cache keys.
            job_id: Optional pre-generated job ID (for GCS upload flow)
            stop_on_exception: Whether to stop on first exception (reserved for future use)

        Returns the job_id.
        """
        submit_start = time.time()
        job_id = job_id or getattr(job, "id", None) or generate_id()
        self._job_stop_on_exception[job_id] = stop_on_exception
        n_iterations = max(1, n)  # Ensure at least 1 iteration

        # Reset DB stats tracking for this submit
        reset_db_stats()

        # Reset TaskStore batch stats for profiling
        TaskStore.reset_batch_stats()

        # Prepare the job - fills in default Agent(), Model(), Scenario() if missing
        t0 = time.time()
        job.replace_missing_objects()
        logger.info(
            f"[SUBMIT {job_id[:8]}] replace_missing_objects: {(time.time() - t0)*1000:.1f}ms"
        )

        # Extract components from the EDSL Job
        t0 = time.time()
        survey = job.survey if hasattr(job, "survey") else job._survey
        scenarios = list(job.scenarios)
        agents = list(job.agents)
        models = list(job.models)

        # Get the DAG from the survey
        dag = self._extract_dag(survey)

        # Get questions from survey
        questions = self._extract_questions(survey)

        # Assign IDs to all resources
        scenario_map = {self._get_or_create_id(s): s for s in scenarios}
        agent_map = {self._get_or_create_id(a): a for a in agents}
        model_map = {self._get_or_create_id(m): m for m in models}
        question_map = {self._get_or_create_id(q): q for q in questions}

        # Build question_name -> question_id mapping
        question_name_to_id = {}
        for q_id, q in question_map.items():
            q_name = self._get_question_name(q)
            question_name_to_id[q_name] = q_id

        logger.info(
            f"[SUBMIT {job_id[:8]}] extract_components: {(time.time() - t0)*1000:.1f}ms "
            f"(scenarios={len(scenarios)}, agents={len(agents)}, models={len(models)}, questions={len(questions)})"
        )

        # Merge retry policies with defaults
        effective_policies = dict(DEFAULT_RETRY_POLICIES)
        if retry_policies:
            effective_policies.update(retry_policies)

        # Store shared resources (with FileStore blob offloading) - using batch writes
        t0 = time.time()
        scenarios_batch = {}
        for s_id, s in scenario_map.items():
            scenario_dict = self._to_dict(s)
            # Offload any FileStore blobs to blob storage
            scenario_dict = self._offload_scenario_filestores(
                job_id, s_id, scenario_dict
            )
            scenarios_batch[s_id] = scenario_dict
        self._jobs.write_scenarios_batch(job_id, scenarios_batch)
        logger.info(
            f"[SUBMIT {job_id[:8]}] write_scenarios_batch ({len(scenarios_batch)}): {(time.time() - t0)*1000:.1f}ms"
        )

        t0 = time.time()
        agents_batch = {a_id: self._to_dict(a) for a_id, a in agent_map.items()}
        self._jobs.write_agents_batch(job_id, agents_batch)
        logger.info(
            f"[SUBMIT {job_id[:8]}] write_agents_batch ({len(agents_batch)}): {(time.time() - t0)*1000:.1f}ms"
        )

        t0 = time.time()
        models_batch = {m_id: self._to_dict(m) for m_id, m in model_map.items()}
        self._jobs.write_models_batch(job_id, models_batch)
        # Keep original model objects for local execution (func/closures don't serialize)
        self._original_models[job_id] = dict(model_map)
        logger.info(
            f"[SUBMIT {job_id[:8]}] write_models_batch ({len(models_batch)}): {(time.time() - t0)*1000:.1f}ms"
        )

        t0 = time.time()
        questions_batch = {q_id: self._to_dict(q) for q_id, q in question_map.items()}
        self._jobs.write_questions_batch(job_id, questions_batch)
        logger.info(
            f"[SUBMIT {job_id[:8]}] write_questions_batch ({len(questions_batch)}): {(time.time() - t0)*1000:.1f}ms"
        )

        # Store the survey for skip logic evaluation
        t0 = time.time()
        survey_dict = self._to_dict(survey)
        self._jobs.write_survey(job_id, survey_dict)
        logger.info(
            f"[SUBMIT {job_id[:8]}] write_survey: {(time.time() - t0)*1000:.1f}ms"
        )

        # Get questions to randomize (if any)
        questions_to_randomize = getattr(survey, "questions_to_randomize", []) or []

        # Generate interviews as cross-product x iterations
        # For n_iterations > 1, we create n copies of each (scenario, agent, model) combination
        t0 = time.time()
        interview_ids = []
        interview_definitions = []  # Collect for batch creation
        all_task_definitions = []  # Collect for job_data cache
        all_direct_task_info = []  # Collect all direct-answer task info
        total_tasks_created = 0

        for scenario, agent, model in itertools.product(
            scenario_map.items(), agent_map.items(), model_map.items()
        ):
            scenario_id, scenario_obj = scenario
            agent_id, agent_obj = agent
            model_id, _ = model

            # Create n_iterations interviews for this combination
            for iteration in range(n_iterations):
                interview_id = generate_id()
                interview_ids.append(interview_id)

                # Generate randomized question options for this interview
                question_option_permutations = self._generate_question_permutations(
                    questions, questions_to_randomize
                )

                # Create tasks for this interview
                # Pass agent and scenario objects for direct answer detection
                (
                    task_ids,
                    direct_task_info,
                    task_defs,
                ) = self._create_tasks_for_interview(
                    job_id=job_id,
                    interview_id=interview_id,
                    scenario_id=scenario_id,
                    agent_id=agent_id,
                    model_id=model_id,
                    questions=questions,
                    question_name_to_id=question_name_to_id,
                    dag=dag,
                    iteration=iteration,
                    agent=agent_obj,
                    scenario=scenario_obj,
                )
                total_tasks_created += len(task_ids)
                all_task_definitions.extend(task_defs)

                # Collect direct task info with context for registry building
                for info in direct_task_info:
                    all_direct_task_info.append(
                        {
                            **info,
                            "agent": agent_obj,
                            "scenario": scenario_obj,
                            "question": questions[info["question_index"]],
                        }
                    )

                # Collect interview definition for batch creation
                interview_def = InterviewDefinition(
                    interview_id=interview_id,
                    job_id=job_id,
                    scenario_id=scenario_id,
                    agent_id=agent_id,
                    model_id=model_id,
                    total_tasks=len(task_ids),
                    task_ids=task_ids,
                    iteration=iteration,
                    question_option_permutations=question_option_permutations,
                )
                interview_definitions.append(interview_def)

        tasks_prep_time = (time.time() - t0) * 1000
        logger.info(
            f"[SUBMIT {job_id[:8]}] prepare_tasks_for_interviews: {tasks_prep_time:.1f}ms "
            f"(interviews={len(interview_definitions)}, tasks={total_tasks_created})"
        )

        # Batch create all tasks (in chunks of 1000 for efficiency)
        t0 = time.time()
        TASK_BATCH_SIZE = 1000
        for i in range(0, len(all_task_definitions), TASK_BATCH_SIZE):
            batch = all_task_definitions[i : i + TASK_BATCH_SIZE]
            self._tasks.create_batch(batch)
        tasks_create_time = (time.time() - t0) * 1000

        batch_stats = TaskStore.get_batch_stats()
        logger.info(
            f"[SUBMIT {job_id[:8]}] tasks.create_batch: {tasks_create_time:.1f}ms "
            f"(calls={batch_stats['calls']}, tasks={batch_stats['total_tasks']})"
        )

        # Batch create all interviews (much faster than individual creates)
        t0 = time.time()
        self._interviews.create_batch(interview_definitions)
        logger.info(
            f"[SUBMIT {job_id[:8]}] interviews.create_batch ({len(interview_definitions)}): {(time.time() - t0)*1000:.1f}ms"
        )

        # Create job definition
        t0 = time.time()
        job_def = JobDefinition(
            job_id=job_id,
            user_id=user_id,
            created_at=datetime.utcnow(),
            total_interviews=len(interview_ids),
            interview_ids=interview_ids,
            retry_policies=effective_policies,
            dag=dag,
            scenario_ids=list(scenario_map.keys()),
            agent_ids=list(agent_map.keys()),
            model_ids=list(model_map.keys()),
            question_ids=list(question_map.keys()),
            n_iterations=n_iterations,
        )
        self._jobs.create(job_def)
        logger.info(
            f"[SUBMIT {job_id[:8]}] jobs.create: {(time.time() - t0)*1000:.1f}ms"
        )

        total_submit_time = (time.time() - submit_start) * 1000

        # Get DB stats
        db_stats = get_db_stats()
        logger.info(
            f"[SUBMIT {job_id[:8]}] TOTAL submit_job: {total_submit_time:.1f}ms "
            f"(interviews={len(interview_ids)}, tasks={total_tasks_created}, "
            f"DB_CALLS={db_stats['calls']}, db_time={db_stats['elapsed_ms']:.1f}ms)"
        )

        # Return job data for caching - pass to background thread to avoid re-reading from PostgreSQL
        job_data = {
            "survey": survey_dict,
            "scenarios": scenarios_batch,
            "agents": agents_batch,
            "models": models_batch,
            "questions": questions_batch,
            # Cache interview and task definitions to avoid PostgreSQL reads during render
            "interview_defs": {
                idef.interview_id: idef.to_dict() for idef in interview_definitions
            },
            "task_defs": {
                tdef.task_id: tdef.to_dict() for tdef in all_task_definitions
            },
        }

        return job_id, all_direct_task_info, job_data

    def _create_tasks_for_interview(
        self,
        job_id: str,
        interview_id: str,
        scenario_id: str,
        agent_id: str,
        model_id: str,
        questions: list,
        question_name_to_id: dict[str, str],
        dag: dict[str, set[str]],
        iteration: int = 0,
        agent: Any = None,
        scenario: Any = None,
    ) -> tuple[list[str], list[dict]]:
        """
        Create all tasks for an interview.

        Transforms the survey's question-level DAG into task-level dependencies.

        Args:
            iteration: Which iteration this interview represents (0-indexed).
                       Used for cache key differentiation when n > 1.
            agent: EDSL Agent object (for detecting direct answer capability)
            scenario: EDSL Scenario object (for detecting direct answer capability)

        Returns:
            Tuple of (task_ids, direct_task_info) where direct_task_info contains
            info about tasks with execution_type != "llm" for building client registry.
        """
        from .direct_answer import detect_execution_type

        # Step 1: Generate task IDs and build question_name -> task_id mapping
        question_name_to_task_id = {}
        task_ids = []
        direct_task_info = []  # Info for building client-side DirectAnswerRegistry

        for q in questions:
            task_id = generate_id()
            q_name = self._get_question_name(q)
            question_name_to_task_id[q_name] = task_id
            task_ids.append(task_id)

        # Step 2: Transform DAG from question names to task IDs
        # Forward index: task -> tasks it depends on
        # Reverse index: task -> tasks that depend on it
        task_depends_on: dict[str, list[str]] = {t: [] for t in task_ids}
        task_dependents: dict[str, list[str]] = {t: [] for t in task_ids}

        for q_name, dep_q_names in dag.items():
            if q_name in question_name_to_task_id:
                task_id = question_name_to_task_id[q_name]
                for dep_q_name in dep_q_names:
                    if dep_q_name in question_name_to_task_id:
                        dep_task_id = question_name_to_task_id[dep_q_name]
                        task_depends_on[task_id].append(dep_task_id)
                        task_dependents[dep_task_id].append(task_id)

        # Step 3: Create task definitions (collect for batch write)
        task_definitions = []
        for i, q in enumerate(questions):
            task_id = task_ids[i]
            q_name = self._get_question_name(q)
            q_id = question_name_to_id[q_name]

            # Detect execution type (llm, agent_direct, or functional)
            execution_type = detect_execution_type(agent, q)

            task_def = TaskDefinition(
                task_id=task_id,
                job_id=job_id,
                interview_id=interview_id,
                scenario_id=scenario_id,
                question_id=q_id,
                question_name=q_name,
                agent_id=agent_id,
                model_id=model_id,
                depends_on=task_depends_on[task_id],
                dependents=task_dependents[task_id],
                iteration=iteration,
                execution_type=execution_type,
            )
            task_definitions.append(task_def)

            # Track non-LLM tasks for client-side registry
            if execution_type != "llm":
                direct_task_info.append(
                    {
                        "task_id": task_id,
                        "execution_type": execution_type,
                        "question_index": i,
                    }
                )

        # Step 4: Return task definitions (caller batches all tasks together for efficiency)
        return task_ids, direct_task_info, task_definitions

    # =========================================================================
    # Skip Logic Evaluation
    # =========================================================================

    def should_skip_task(
        self,
        job_id: str,
        interview_id: str,
        task_id: str,
        debug: bool = False,
        # Optional cached data to avoid redundant fetches
        cached_survey: Any = None,
        cached_question_index_map: dict[str, int] | None = None,
        cached_answers: dict[str, Any] | None = None,
        cached_scenario_data: dict | None = None,
        cached_agent_data: dict | None = None,
        cached_task_def: Any = None,
    ) -> tuple[bool, str | None]:
        """
        Check if a task should be skipped based on survey rules and current answers.

        Returns (should_skip, reason) tuple.

        A task should be skipped if:
        1. Any of its memory dependencies (prior questions) have answer=None (failed)
        2. Survey skip rules indicate it should be skipped (EndOfSurvey, jump rules)

        For performance, callers can pass cached data to avoid redundant fetches:
        - cached_survey: Pre-reconstructed Survey object
        - cached_question_index_map: Dict mapping question_name -> index
        - cached_answers: Dict of current answers for this interview
        - cached_scenario_data: Scenario dict for this task
        - cached_agent_data: Agent dict for this task
        - cached_task_def: TaskDefinition for this task
        """
        # Track fallback operations (when cache not used)
        fallback_ops = {
            "task_def": 0,
            "survey": 0,
            "index_loop": 0,
            "answers": 0,
            "scenario": 0,
            "agent": 0,
        }

        # Use cached task_def or fetch
        if cached_task_def is not None:
            task_def = cached_task_def
        else:
            task_def = self._tasks.get_definition(job_id, interview_id, task_id)
            fallback_ops["task_def"] = 1
        if task_def is None:
            return False, None

        # Use cached survey or fetch and reconstruct
        if cached_survey is not None:
            survey = cached_survey
        else:
            fallback_ops["survey"] = 1
            survey_data = self._jobs.get_survey(job_id)
            if survey_data is None:
                if debug:
                    print(f"  [skip] No survey data for job {job_id}")
                return False, None

            survey = Survey.from_dict(survey_data)

        # Use cached index map or search
        if cached_question_index_map is not None:
            question_index = cached_question_index_map.get(task_def.question_name)
        else:
            fallback_ops["index_loop"] = len(survey.questions)  # O(Q) loop
            question_index = None
            for i, q in enumerate(survey.questions):
                if q.question_name == task_def.question_name:
                    question_index = i
                    break

        if question_index is None:
            if debug:
                print(f"  [skip] Question {task_def.question_name} not found in survey")
            return False, None

        # Check if survey has any user-defined skip rules (not just default "go to next" rules)
        has_skip_rules = False
        if hasattr(survey, "rule_collection") and survey.rule_collection is not None:
            # non_default_rules contains only user-defined rules, not the auto-generated defaults
            non_default = getattr(survey.rule_collection, "non_default_rules", None)
            has_skip_rules = non_default is not None and len(non_default) > 0

        if debug:
            non_default_count = (
                len(survey.rule_collection.non_default_rules)
                if hasattr(survey.rule_collection, "non_default_rules")
                else 0
            )
            print(
                f"  [skip] Q{question_index}: {task_def.question_name}, {len(survey.questions)} questions, {non_default_count} skip rules"
            )

        # First question is never skipped
        if question_index == 0:
            if debug:
                print(f"  [skip] First question - not skipping")
            return False, None

        # OPTIMIZATION: If survey has no user-defined skip rules, skip evaluation entirely
        # Default rules just say "go to next question", so nothing to skip
        # This avoids expensive rule_collection.skip_question_before_running() calls (O(N) per task)
        if not has_skip_rules:
            return False, None

        # Use cached answers or gather
        if cached_answers is not None:
            current_answers = cached_answers
        else:
            current_answers = self._gather_current_answers(job_id, interview_id)
            fallback_ops["answers"] = 1
        if debug:
            print(f"  [skip] Current answers: {len(current_answers)} answers")

        # Check if any memory dependency has failed (answer=None)
        memory_plan = survey.memory_plan
        question_name = task_def.question_name

        # Get prior questions this question depends on
        prior_questions = memory_plan.get(question_name, [])

        for prior_q_name in prior_questions:
            # Check if prior question's answer is None (failed)
            prior_answer = current_answers.get(prior_q_name)
            if prior_answer is None:
                # Check if this prior question was actually answered
                answer = self._answers.get(job_id, interview_id, prior_q_name)
                if answer is not None and answer.answer is None:
                    # Dependency failed - skip this question
                    return True, f"Memory dependency '{prior_q_name}' failed"

        # Build combined answers dict for rule evaluation
        # Format expected by rule evaluation: {question_name.answer: value}
        combined_answers = {}

        for key, value in current_answers.items():
            if not key.endswith(".answer"):
                combined_answers[f"{key}.answer"] = value
            else:
                combined_answers[key] = value

        # Use cached scenario/agent or fetch
        if cached_scenario_data is not None:
            scenario_data = cached_scenario_data
        else:
            scenario_data = self._jobs.get_scenario(job_id, task_def.scenario_id)
            fallback_ops["scenario"] = 1
        if scenario_data:
            combined_answers.update(scenario_data)

        if cached_agent_data is not None:
            agent_data = cached_agent_data
        else:
            agent_data = self._jobs.get_agent(job_id, task_def.agent_id)
            fallback_ops["agent"] = 1
        if agent_data and "traits" in agent_data:
            combined_answers.update(agent_data["traits"])

        # Debug: report any fallback operations
        if debug and any(v > 0 for v in fallback_ops.values()):
            print(f"  [skip] FALLBACK OPS: {fallback_ops}")

        if debug:
            print(f"  [skip] Combined answers: {len(combined_answers)} keys")

        # Check "before" skip rules
        before_skip = survey.rule_collection.skip_question_before_running(
            question_index, combined_answers
        )
        if debug:
            print(
                f"  [skip] skip_question_before_running({question_index}): {before_skip}"
            )
        if before_skip:
            return True, "Skip rule evaluated to true before running"

        # Check if previous question's rules skip past this question
        prev_question_index = question_index - 1

        next_q_info = survey.rule_collection.next_question(
            prev_question_index, combined_answers
        )
        if debug:
            print(
                f"  [skip] next_question({prev_question_index}): next_q={next_q_info.next_q}, current={question_index}"
            )

        if next_q_info.next_q == EndOfSurvey:
            # End of survey - all remaining questions should be skipped
            return True, "EndOfSurvey reached"

        if next_q_info.next_q > question_index:
            # Rule says to jump past this question
            return (
                True,
                f"Skip rule: jump from {prev_question_index} to {next_q_info.next_q}",
            )

        if debug:
            print(f"  [skip] No skip condition met for {task_def.question_name}")
        return False, None

    def _gather_current_answers(self, job_id: str, interview_id: str) -> dict[str, Any]:
        """Gather already-completed answers for an interview."""
        current = {}

        # Get all answers for this interview
        answers = self._answers.get_all_for_interview(job_id, interview_id)

        for answer in answers:
            current[answer.question_name] = answer.answer
            # Also add with .answer suffix for rule evaluation
            current[f"{answer.question_name}.answer"] = answer.answer
            # Include comments if present
            if answer.comment:
                current[f"{answer.question_name}_comment"] = answer.comment

        return current

    # =========================================================================
    # Task Completion
    # =========================================================================

    def on_task_completed(
        self,
        job_id: str,
        interview_id: str,
        task_id: str,
        answer_value: Any,
        comment: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        raw_model_response: dict | None = None,
        generated_tokens: str | None = None,
        cached: bool = False,
        system_prompt: str | None = None,
        user_prompt: str | None = None,
        input_price_per_million_tokens: float | None = None,
        output_price_per_million_tokens: float | None = None,
        cache_key: str | None = None,
        validated: bool | None = None,
        reasoning_summary: str | None = None,
    ) -> None:
        """Called when a task finishes successfully with an answer."""
        # Get task definition for question_name and model_id
        task_def = self._tasks.get_definition(job_id, interview_id, task_id)
        if task_def is None:
            raise ValueError(f"Task {task_id} not found")

        # Store answer with all metadata
        answer = Answer(
            job_id=job_id,
            interview_id=interview_id,
            question_name=task_def.question_name,
            answer=answer_value,
            created_at=datetime.utcnow(),
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            comment=comment,
            cached=cached,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            raw_model_response=raw_model_response,
            generated_tokens=generated_tokens,
            model_id=task_def.model_id,
            input_price_per_million_tokens=input_price_per_million_tokens,
            output_price_per_million_tokens=output_price_per_million_tokens,
            cache_key=cache_key,
            validated=validated,
            reasoning_summary=reasoning_summary,
        )
        self._answers.store(answer)

        # Update task status
        self._tasks.set_status(task_id, TaskStatus.COMPLETED)

        # Notify dependents
        for dependent_id in task_def.dependents:
            self._tasks.mark_dependency_satisfied(job_id, dependent_id)

        # Update interview status
        self._interviews.mark_task_completed(job_id, interview_id)

        # Check if interview is done -> update job
        interview_state = self._interviews.get_state(interview_id)
        if interview_state != InterviewState.RUNNING:
            had_failures = interview_state == InterviewState.COMPLETED_WITH_FAILURES
            self._jobs.mark_interview_completed(job_id, interview_id, had_failures)

    def on_task_skipped(
        self,
        job_id: str,
        interview_id: str,
        task_id: str,
        skip_reason: str | None = None,
    ) -> None:
        """Called when a task is skipped due to skip logic."""
        task_def = self._tasks.get_definition(job_id, interview_id, task_id)
        if task_def is None:
            raise ValueError(f"Task {task_id} not found")

        # Update task status
        self._tasks.set_status(task_id, TaskStatus.SKIPPED)

        # Notify dependents (skipped tasks still satisfy dependencies)
        for dependent_id in task_def.dependents:
            self._tasks.mark_dependency_satisfied(job_id, dependent_id)

        # Update interview status
        self._interviews.mark_task_skipped(job_id, interview_id)

        # Check if interview is done
        interview_state = self._interviews.get_state(interview_id)
        if interview_state != InterviewState.RUNNING:
            had_failures = interview_state == InterviewState.COMPLETED_WITH_FAILURES
            self._jobs.mark_interview_completed(job_id, interview_id, had_failures)

    def on_task_failed(
        self,
        job_id: str,
        interview_id: str,
        task_id: str,
        error_type: str,
        error_message: str,
    ) -> None:
        """Called when a task fails. Retries if policy allows, otherwise marks as permanent failure."""
        task_def = self._tasks.get_definition(job_id, interview_id, task_id)
        if task_def is None:
            raise ValueError(f"Task {task_id} not found")

        # Check retry policy before marking as permanently failed
        # Skip retries if stop_on_exception is set for this job
        if not self._job_stop_on_exception.get(job_id, False):
            job_def = self._jobs.get_definition(job_id)
            if job_def is not None:
                # Look up retry policy for this error type, fall back to a default retryable policy
                default_policy = RetryPolicy(
                    max_attempts=3, base_delay_seconds=0.5, retryable=True
                )
                policy = job_def.retry_policies.get(error_type, default_policy)

                if policy.retryable:
                    attempt_count = self._tasks.increment_attempt(task_id, error_type)
                    if attempt_count < policy.max_attempts:
                        # Reset task to READY and add back to the ready set for re-rendering
                        self._tasks.set_status(task_id, TaskStatus.READY)
                        self._tasks.add_to_ready(job_id, task_id)
                        return

        # Permanently failed — update task status and error
        self._tasks.set_status(task_id, TaskStatus.FAILED)
        self._tasks.set_error(task_id, error_type, error_message)

        # Propagate failure to dependents
        self._propagate_failure(job_id, interview_id, task_def.dependents)

        # Update interview status
        self._interviews.mark_task_failed(job_id, interview_id)

        # Check if interview is done
        interview_state = self._interviews.get_state(interview_id)
        if interview_state != InterviewState.RUNNING:
            had_failures = True  # We just had a failure
            self._jobs.mark_interview_completed(job_id, interview_id, had_failures)

    def _propagate_failure(
        self, job_id: str, interview_id: str, dependent_ids: list[str]
    ) -> None:
        """Recursively mark dependents as blocked."""
        for dep_id in dependent_ids:
            self._tasks.set_status(dep_id, TaskStatus.BLOCKED)
            self._tasks.set_error(
                dep_id, "upstream_failure", "Blocked by failed dependency"
            )
            self._interviews.mark_task_blocked(job_id, interview_id)

            # Recurse
            dep_def = self._tasks.get_definition(job_id, interview_id, dep_id)
            if dep_def:
                self._propagate_failure(job_id, interview_id, dep_def.dependents)

    # =========================================================================
    # Job Status & Results
    # =========================================================================

    def get_progress(self, job_id: str) -> dict:
        """Get detailed progress for a job."""
        job_def = self._jobs.get_definition(job_id)
        if job_def is None:
            raise ValueError(f"Job {job_id} not found")

        job_status = self._jobs.get_status(job_id)
        job_state = self._jobs.get_state(job_id)

        # Aggregate task counts across all interviews
        total_tasks = 0
        completed_tasks = 0
        skipped_tasks = 0
        failed_tasks = 0
        blocked_tasks = 0
        pending_tasks = 0
        ready_tasks = 0
        running_tasks = 0

        for interview_id in job_def.interview_ids:
            interview_def = self._interviews.get_definition(job_id, interview_id)
            interview_status = self._interviews.get_status(interview_id)

            if interview_def:
                total_tasks += interview_def.total_tasks

            completed_tasks += interview_status.completed
            skipped_tasks += interview_status.skipped
            failed_tasks += interview_status.failed
            blocked_tasks += interview_status.blocked

        # Calculate pending/ready/running from remaining
        accounted = completed_tasks + skipped_tasks + failed_tasks + blocked_tasks
        remaining = total_tasks - accounted

        # Get ready task count from all jobs
        ready_tasks = self._tasks.get_ready_count(job_id)

        # Collect all task IDs for batch status check
        all_task_ids = []
        for interview_id in job_def.interview_ids:
            interview_def = self._interviews.get_definition(job_id, interview_id)
            if interview_def:
                all_task_ids.extend(interview_def.task_ids)

        # Batch fetch all task statuses in a single operation (O(1) Redis calls)
        if all_task_ids:
            task_statuses = self._tasks.get_statuses_batch(all_task_ids)
            # Count running tasks (RUNNING, RENDERING, or QUEUED)
            for task_id, status in task_statuses.items():
                if status in (
                    TaskStatus.RUNNING,
                    TaskStatus.RENDERING,
                    TaskStatus.QUEUED,
                ):
                    running_tasks += 1

        pending_tasks = max(0, remaining - ready_tasks - running_tasks)

        return {
            "job_id": job_id,
            "state": job_state.value,
            "total_interviews": job_def.total_interviews,
            "completed_interviews": job_status.completed_interviews,
            "failed_interviews": job_status.failed_interviews,
            "running_interviews": job_def.total_interviews - job_status.finished_count,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "skipped_tasks": skipped_tasks,
            "failed_tasks": failed_tasks,
            "blocked_tasks": blocked_tasks,
            "pending_tasks": pending_tasks,
            "ready_tasks": ready_tasks,
            "running_tasks": running_tasks,
        }

    def get_progress_batch(self, job_ids: list[str]) -> dict[str, dict]:
        """
        Get detailed progress for multiple jobs in a single batch operation.

        Much more efficient than calling get_progress() for each job individually.
        Returns a dict mapping job_id to progress dict (same format as get_progress).
        """
        if not job_ids:
            return {}

        # Batch read all job definitions, statuses, and states
        job_defs = self._jobs.get_definitions_batch(job_ids)
        job_statuses = self._jobs.get_statuses_batch(job_ids)
        job_states = self._jobs.get_states_batch(job_ids)

        # Collect all interview IDs per job
        all_interview_ids_by_job: dict[str, list[str]] = {}
        for job_id in job_ids:
            job_def = job_defs.get(job_id)
            if job_def:
                all_interview_ids_by_job[job_id] = job_def.interview_ids

        # Batch read all interview definitions
        all_interview_defs: dict[str, dict[str, InterviewDefinition | None]] = {}
        for job_id, interview_ids in all_interview_ids_by_job.items():
            if interview_ids:
                all_interview_defs[job_id] = self._interviews.get_definitions_batch(
                    job_id, interview_ids
                )

        # Collect all interview IDs for batch status read
        all_interview_ids = []
        for interview_ids in all_interview_ids_by_job.values():
            all_interview_ids.extend(interview_ids)

        # Batch read all interview statuses
        all_interview_statuses = {}
        if all_interview_ids:
            all_interview_statuses = self._interviews.get_statuses_batch(
                all_interview_ids
            )

        # Collect all task IDs for batch status read
        all_task_ids = []
        task_ids_by_job: dict[str, list[str]] = {}
        for job_id, interview_ids in all_interview_ids_by_job.items():
            job_task_ids = []
            interview_defs = all_interview_defs.get(job_id, {})
            for interview_id in interview_ids:
                interview_def = interview_defs.get(interview_id)
                if interview_def:
                    job_task_ids.extend(interview_def.task_ids)
            task_ids_by_job[job_id] = job_task_ids
            all_task_ids.extend(job_task_ids)

        # Batch read all task statuses
        all_task_statuses = {}
        if all_task_ids:
            all_task_statuses = self._tasks.get_statuses_batch(all_task_ids)

        # Build progress for each job
        results = {}
        for job_id in job_ids:
            job_def = job_defs.get(job_id)
            if job_def is None:
                continue

            job_status = job_statuses.get(job_id)
            job_state = job_states.get(job_id)

            if job_status is None or job_state is None:
                continue

            # Aggregate task counts across all interviews
            total_tasks = 0
            completed_tasks = 0
            skipped_tasks = 0
            failed_tasks = 0
            blocked_tasks = 0
            running_tasks = 0

            interview_ids = all_interview_ids_by_job.get(job_id, [])
            interview_defs = all_interview_defs.get(job_id, {})

            for interview_id in interview_ids:
                interview_def = interview_defs.get(interview_id)
                interview_status = all_interview_statuses.get(interview_id)

                if interview_def:
                    total_tasks += interview_def.total_tasks

                if interview_status:
                    completed_tasks += interview_status.completed
                    skipped_tasks += interview_status.skipped
                    failed_tasks += interview_status.failed
                    blocked_tasks += interview_status.blocked

            # Get ready task count
            ready_tasks = self._tasks.get_ready_count(job_id)

            # Count running tasks from batch-fetched statuses
            job_task_ids = task_ids_by_job.get(job_id, [])
            for task_id in job_task_ids:
                status = all_task_statuses.get(task_id)
                if status and status in (
                    TaskStatus.RUNNING,
                    TaskStatus.RENDERING,
                    TaskStatus.QUEUED,
                ):
                    running_tasks += 1

            # Calculate pending tasks
            accounted = completed_tasks + skipped_tasks + failed_tasks + blocked_tasks
            remaining = total_tasks - accounted
            pending_tasks = max(0, remaining - ready_tasks - running_tasks)

            # Build base progress dict
            base_progress = {
                "job_id": job_id,
                "state": job_state.value,
                "total_interviews": job_def.total_interviews,
                "completed_interviews": job_status.completed_interviews,
                "failed_interviews": job_status.failed_interviews,
                "running_interviews": job_def.total_interviews
                - job_status.finished_count,
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "skipped_tasks": skipped_tasks,
                "failed_tasks": failed_tasks,
                "blocked_tasks": blocked_tasks,
                "pending_tasks": pending_tasks,
                "ready_tasks": ready_tasks,
                "running_tasks": running_tasks,
            }

            # Add model-grouped breakdown
            # Collect unique model_ids per job for batch model fetching
            model_ids = set()
            for interview_def in interview_defs.values():
                if interview_def:
                    model_ids.add(interview_def.model_id)

            # Batch read model data for this job
            models = {}
            if model_ids:
                models = self._jobs.get_models_batch(job_id, list(model_ids))

            # Group interviews by (inference_service, model_name, model_id)
            interviews_by_model: dict[tuple[str, str, str], list[str]] = {}
            for interview_id, interview_def in interview_defs.items():
                if interview_def is None:
                    continue

                model_data = models.get(interview_def.model_id)
                if model_data is None:
                    inference_service = "unknown"
                    model_name = interview_def.model_id
                else:
                    inference_service = model_data.get("inference_service") or "unknown"
                    model_name = model_data.get("model") or interview_def.model_id

                key = (inference_service, model_name, interview_def.model_id)
                if key not in interviews_by_model:
                    interviews_by_model[key] = []
                interviews_by_model[key].append(interview_id)

            # Calculate progress for each model group
            by_model = []
            for (
                inference_service,
                model_name,
                model_id,
            ), model_interview_ids in interviews_by_model.items():
                # Aggregate task counts across interviews in this group
                model_total_tasks = 0
                model_completed_tasks = 0
                model_skipped_tasks = 0
                model_failed_tasks = 0
                model_blocked_tasks = 0
                model_running_tasks = 0
                model_completed_interviews = 0
                model_failed_interviews = 0

                for interview_id in model_interview_ids:
                    interview_def = interview_defs.get(interview_id)
                    interview_status = all_interview_statuses.get(interview_id)

                    if interview_def:
                        model_total_tasks += interview_def.total_tasks

                    if interview_status:
                        model_completed_tasks += interview_status.completed
                        model_skipped_tasks += interview_status.skipped
                        model_failed_tasks += interview_status.failed
                        model_blocked_tasks += interview_status.blocked

                    # Count completed/failed interviews
                    if interview_status:
                        total_tasks_for_interview = (
                            interview_def.total_tasks if interview_def else 0
                        )
                        if interview_status.is_done(total_tasks_for_interview):
                            if (
                                interview_status.failed > 0
                                or interview_status.blocked > 0
                            ):
                                model_failed_interviews += 1
                            else:
                                model_completed_interviews += 1

                    # Count running tasks from this interview
                    if interview_def:
                        for task_id in interview_def.task_ids:
                            status = all_task_statuses.get(task_id)
                            if status and status in (
                                TaskStatus.RUNNING,
                                TaskStatus.RENDERING,
                                TaskStatus.QUEUED,
                            ):
                                model_running_tasks += 1

                # Calculate pending tasks for this model group
                model_accounted = (
                    model_completed_tasks
                    + model_skipped_tasks
                    + model_failed_tasks
                    + model_blocked_tasks
                )
                model_remaining = model_total_tasks - model_accounted
                # Note: ready_tasks is job-level, so we approximate
                model_pending_tasks = max(0, model_remaining - model_running_tasks)

                model_total_interviews = len(model_interview_ids)
                model_running_interviews = (
                    model_total_interviews
                    - model_completed_interviews
                    - model_failed_interviews
                )

                by_model.append(
                    {
                        "inference_service": inference_service,
                        "model_name": model_name,
                        "model_id": model_id,
                        "interview_ids": model_interview_ids,
                        "total_interviews": model_total_interviews,
                        "completed_interviews": model_completed_interviews,
                        "failed_interviews": model_failed_interviews,
                        "running_interviews": model_running_interviews,
                        "total_tasks": model_total_tasks,
                        "completed_tasks": model_completed_tasks,
                        "skipped_tasks": model_skipped_tasks,
                        "failed_tasks": model_failed_tasks,
                        "blocked_tasks": model_blocked_tasks,
                        "pending_tasks": model_pending_tasks,
                        "running_tasks": model_running_tasks,
                    }
                )

            base_progress["by_model"] = by_model
            results[job_id] = base_progress

        return results

    def get_first_failed_task(self, job_id: str) -> dict | None:
        """
        Get information about the first failed task in a job.

        Returns:
            Dict with task_id, interview_id, error_type, error_message,
            or None if no failed tasks.
        """
        job_def = self._jobs.get_definition(job_id)
        if job_def is None:
            return None

        for interview_id in job_def.interview_ids:
            interview_def = self._interviews.get_definition(job_id, interview_id)
            if interview_def is None:
                continue

            for task_id in interview_def.task_ids:
                status = self._tasks.get_status(task_id)
                if status == TaskStatus.FAILED:
                    state = self._tasks.get_state(task_id)
                    return {
                        "task_id": task_id,
                        "interview_id": interview_id,
                        "error_type": state.last_error_type or "unknown",
                        "error_message": state.last_error_message or "Unknown error",
                    }

        return None

    def get_error_counts(self, job_id: str) -> dict[str, int]:
        """
        Get counts of errors by type for a job.

        Returns:
            Dict mapping error_type to count, e.g. {"rate_limit": 5, "timeout": 2}
        """
        job_def = self._jobs.get_definition(job_id)
        if job_def is None:
            return {}

        error_counts: dict[str, int] = {}

        for interview_id in job_def.interview_ids:
            interview_def = self._interviews.get_definition(job_id, interview_id)
            if interview_def is None:
                continue

            for task_id in interview_def.task_ids:
                status = self._tasks.get_status(task_id)
                if status == TaskStatus.FAILED:
                    state = self._tasks.get_state(task_id)
                    error_type = state.last_error_type or "unknown"
                    error_counts[error_type] = error_counts.get(error_type, 0) + 1

        return error_counts

    def get_error_details(self, job_id: str) -> list[dict]:
        """
        Get detailed information about all failed tasks for a job.

        Returns:
            List of dicts with full error details for each failed task:
            - task_id: The task identifier
            - interview_id: The interview this task belongs to
            - question_name: The question being asked
            - model_id: The model being used
            - error_type: Classification of the error
            - error_message: Full error message
            - attempts: Dict of error_type -> attempt count
        """
        job_def = self._jobs.get_definition(job_id)
        if job_def is None:
            return []

        errors = []

        for interview_id in job_def.interview_ids:
            interview_def = self._interviews.get_definition(job_id, interview_id)
            if interview_def is None:
                continue

            for task_id in interview_def.task_ids:
                status = self._tasks.get_status(task_id)
                if status == TaskStatus.FAILED:
                    state = self._tasks.get_state(task_id)
                    task_def = self._tasks.get_definition(job_id, interview_id, task_id)

                    error_info = {
                        "task_id": task_id,
                        "interview_id": interview_id,
                        "question_name": task_def.question_name if task_def else None,
                        "model_id": task_def.model_id if task_def else None,
                        "error_type": state.last_error_type or "unknown",
                        "error_message": state.last_error_message or "Unknown error",
                        "attempts": state.attempts,
                    }

                    errors.append(error_info)

        return errors

    def get_results(self, job_id: str) -> list[dict]:
        """
        Get results for all completed interviews.

        Returns a list of result dicts, one per interview.
        """
        job_def = self._jobs.get_definition(job_id)
        if job_def is None:
            raise ValueError(f"Job {job_id} not found")

        results = []
        for interview_id in job_def.interview_ids:
            interview_def = self._interviews.get_definition(job_id, interview_id)
            interview_state = self._interviews.get_state(interview_id)

            if interview_def is None:
                continue

            # Get all answers for this interview
            answers = self._answers.get_all_for_interview(job_id, interview_id)

            result = {
                "interview_id": interview_id,
                "scenario_id": interview_def.scenario_id,
                "agent_id": interview_def.agent_id,
                "model_id": interview_def.model_id,
                "state": interview_state.value,
                "answers": {a.question_name: a.answer for a in answers},
            }
            results.append(result)

        return results

    def build_edsl_result(
        self,
        job_id: str,
        interview_id: str,
        job_def: "JobDefinition | None" = None,
        survey: "Survey | None" = None,
        interview_def: "InterviewDefinition | None" = None,
        all_object_data: dict | None = None,
        questions_data: dict | None = None,
        prefetched_answers: dict | None = None,
        _timing: dict | None = None,
    ) -> Any:
        """
        Build an EDSL Result object from a completed interview.

        This method mirrors EDSL's ResultFromInterview.convert() to ensure
        the Result object has all the expected fields.

        Args:
            job_id: The job ID
            interview_id: The interview ID
            job_def: Optional pre-fetched job definition to avoid duplicate DB calls
            survey: Optional pre-fetched survey to avoid duplicate DB calls
            interview_def: Optional pre-fetched interview definition
            all_object_data: Optional pre-fetched agent/scenario/model data
            questions_data: Optional pre-fetched questions data
            _timing: Optional dict to collect timing data

        Returns an edsl.results.Result object.
        """
        import time as _time

        # Use pre-fetched interview_def if available, otherwise fetch
        if interview_def is None:
            _t = _time.time()
            interview_def = self._interviews.get_definition(job_id, interview_id)
            if _timing is not None:
                _timing["get_interview_def"] = (
                    _timing.get("get_interview_def", 0) + (_time.time() - _t) * 1000
                )
        if interview_def is None:
            raise ValueError(f"Interview {interview_id} not found")

        # Use pre-fetched object data if available, otherwise fetch
        if all_object_data is not None:
            agent_data = all_object_data.get(
                f"job:{job_id}:agent:{interview_def.agent_id}"
            )
            scenario_data = all_object_data.get(
                f"job:{job_id}:scenario:{interview_def.scenario_id}"
            )
            model_data = all_object_data.get(
                f"job:{job_id}:model:{interview_def.model_id}"
            )
        else:
            keys_to_fetch = [
                f"job:{job_id}:agent:{interview_def.agent_id}",
                f"job:{job_id}:scenario:{interview_def.scenario_id}",
                f"job:{job_id}:model:{interview_def.model_id}",
            ]
            _t = _time.time()
            batch_data = self._storage.batch_read_persistent(keys_to_fetch)
            if _timing is not None:
                _timing["batch_read_agent_scenario_model"] = (
                    _timing.get("batch_read_agent_scenario_model", 0)
                    + (_time.time() - _t) * 1000
                )
            agent_data = batch_data.get(f"job:{job_id}:agent:{interview_def.agent_id}")
            scenario_data = batch_data.get(
                f"job:{job_id}:scenario:{interview_def.scenario_id}"
            )
            model_data = batch_data.get(f"job:{job_id}:model:{interview_def.model_id}")

        _t = _time.time()
        agent = Agent.from_dict(agent_data) if agent_data else Agent()
        scenario = Scenario.from_dict(scenario_data) if scenario_data else Scenario()
        model = LanguageModel.from_dict(model_data) if model_data else None
        if _timing is not None:
            _timing["deserialize_agent_scenario_model"] = (
                _timing.get("deserialize_agent_scenario_model", 0)
                + (_time.time() - _t) * 1000
            )

        # Use pre-fetched questions_data if available, otherwise fetch
        question_names = []
        if questions_data is None and job_def and job_def.question_ids:
            _t = _time.time()
            questions_data = self._jobs.get_questions_batch(
                job_id, job_def.question_ids
            )
            if _timing is not None:
                _timing["get_questions_batch"] = (
                    _timing.get("get_questions_batch", 0) + (_time.time() - _t) * 1000
                )

        if job_def and job_def.question_ids and questions_data:
            for q_id in job_def.question_ids:
                q_data = questions_data.get(q_id)
                if q_data:
                    question_names.append(q_data.get("question_name", q_id))

        # Get answers - use prefetched if available, otherwise fetch
        _t = _time.time()
        if prefetched_answers is not None:
            # Use pre-fetched answers (batch fetched by caller)
            answers = list(prefetched_answers.values())
        elif question_names:
            # Fetch answers using known question names (avoids Redis SCAN)
            answers_dict = self._answers.get_for_interview(
                job_id, interview_id, question_names
            )
            answers = list(answers_dict.values())
        else:
            # Fallback to SCAN if no question names available
            answers = self._answers.get_all_for_interview(job_id, interview_id)
        if _timing is not None:
            _timing["get_answers"] = (
                _timing.get("get_answers", 0) + (_time.time() - _t) * 1000
            )

        # Build the answer dict (matches EDSL's answer_dict structure)
        # Include None for failed/skipped questions so all questions appear in results
        answer_dict = {a.question_name: a.answer for a in answers}
        for qname in question_names:
            if qname not in answer_dict:
                answer_dict[qname] = None

        # Build prompt dict (matches EDSL's prompt_dictionary structure)
        from edsl.prompts import Prompt

        prompt_dict = {}
        for a in answers:
            prompt_dict[f"{a.question_name}_user_prompt"] = Prompt(
                text=a.user_prompt or ""
            )
            prompt_dict[f"{a.question_name}_system_prompt"] = Prompt(
                text=a.system_prompt or ""
            )

        # Build raw_model_response dict (matches EDSL's raw_model_results_dictionary)
        raw_model_response_dict = {}
        for a in answers:
            raw_model_response_dict[
                f"{a.question_name}_raw_model_response"
            ] = a.raw_model_response
            raw_model_response_dict[f"{a.question_name}_input_tokens"] = a.input_tokens
            raw_model_response_dict[
                f"{a.question_name}_output_tokens"
            ] = a.output_tokens
            raw_model_response_dict[
                f"{a.question_name}_input_price_per_million_tokens"
            ] = a.input_price_per_million_tokens
            raw_model_response_dict[
                f"{a.question_name}_output_price_per_million_tokens"
            ] = a.output_price_per_million_tokens
            # Calculate cost and one_usd_buys like EDSL does
            total_cost = None
            if a.input_tokens is not None and a.output_tokens is not None:
                input_price = a.input_price_per_million_tokens or 0
                output_price = a.output_price_per_million_tokens or 0
                total_cost = (input_price / 1_000_000 * a.input_tokens) + (
                    output_price / 1_000_000 * a.output_tokens
                )
            raw_model_response_dict[f"{a.question_name}_cost"] = total_cost
            one_usd_buys = (
                "NA" if total_cost is None or total_cost == 0 else 1.0 / total_cost
            )
            raw_model_response_dict[f"{a.question_name}_one_usd_buys"] = one_usd_buys

        # Build generated_tokens dict (matches EDSL's generated_tokens_dict)
        generated_tokens_dict = {}
        for a in answers:
            generated_tokens_dict[
                f"{a.question_name}_generated_tokens"
            ] = a.generated_tokens

        # Build comments dict (matches EDSL's comments_dict)
        comments_dict = {}
        for a in answers:
            comments_dict[f"{a.question_name}_comment"] = a.comment

        # Build reasoning_summaries dict (matches EDSL's reasoning_summaries_dict)
        reasoning_summaries_dict = {}
        for a in answers:
            reasoning_summaries_dict[
                f"{a.question_name}_reasoning_summary"
            ] = a.reasoning_summary

        # Build cache_used dict (matches EDSL's cache_used_dictionary)
        cache_used_dict = {a.question_name: a.cached for a in answers}

        # Build cache_keys dict (matches EDSL's cache_keys)
        cache_keys = {a.question_name: a.cache_key for a in answers}

        # Build validated dict (matches EDSL's validated_dict)
        validated_dict = {}
        for a in answers:
            validated_dict[f"{a.question_name}_validated"] = a.validated

        # Get survey and question attributes
        # Use passed job_def if available, otherwise fetch
        if job_def is None:
            _t = _time.time()
            job_def = self._jobs.get_definition(job_id)
            if _timing is not None:
                _timing["get_job_def"] = (
                    _timing.get("get_job_def", 0) + (_time.time() - _t) * 1000
                )
        question_to_attributes = {}

        # Use passed survey if available, otherwise fetch from DB
        if survey is None:
            _t = _time.time()
            survey_data = self._jobs.get_survey(job_id)
            if _timing is not None:
                _timing["get_survey"] = (
                    _timing.get("get_survey", 0) + (_time.time() - _t) * 1000
                )

            _t = _time.time()
            if survey_data:
                survey = Survey.from_dict(survey_data)
            if _timing is not None:
                _timing["deserialize_survey"] = (
                    _timing.get("deserialize_survey", 0) + (_time.time() - _t) * 1000
                )

        # Build question_to_attributes from already-fetched questions_data
        # Get per-interview option permutations (for questions_to_randomize)
        option_permutations = (
            interview_def.question_option_permutations
            if interview_def and hasattr(interview_def, "question_option_permutations")
            else {}
        )
        if job_def and job_def.question_ids and questions_data:
            for q_id in job_def.question_ids:
                q_data = questions_data.get(q_id)
                if q_data:
                    q_name = q_data.get("question_name", q_id)
                    q_options = q_data.get("question_options")
                    # Resolve template variables in question_options using prior answers
                    q_options = self._resolve_question_options(
                        q_options, answer_dict, scenario
                    )
                    # Apply per-interview randomized permutation if present
                    if option_permutations and q_name in option_permutations:
                        q_options = option_permutations[q_name]
                    question_to_attributes[q_name] = {
                        "question_text": q_data.get("question_text", ""),
                        "question_type": q_data.get("question_type", ""),
                        "question_options": q_options,
                    }

        # Get iteration from interview definition
        iteration = (
            interview_def.iteration if hasattr(interview_def, "iteration") else 0
        )

        _t = _time.time()
        result = Result(
            agent=agent,
            scenario=scenario,
            model=model,
            iteration=iteration,
            answer=answer_dict,
            prompt=prompt_dict,
            raw_model_response=raw_model_response_dict,
            survey=survey,
            generated_tokens=generated_tokens_dict,
            comments_dict=comments_dict,
            reasoning_summaries_dict=reasoning_summaries_dict,
            cache_used_dict=cache_used_dict,
            cache_keys=cache_keys,
            validated_dict=validated_dict,
            question_to_attributes=question_to_attributes,
        )

        # Set interview_hash for compatibility with EDSL's Interview-based results.
        # Compute a deterministic hash from the same components Interview.__hash__ uses.
        from edsl.utilities.utilities import dict_hash

        hash_data = {
            "agent": agent.to_dict(add_edsl_version=False)
            if hasattr(agent, "to_dict")
            else {},
            "scenario": scenario.to_dict(add_edsl_version=False)
            if hasattr(scenario, "to_dict")
            else {},
            "model": model.to_dict(add_edsl_version=False)
            if model and hasattr(model, "to_dict")
            else {},
            "iteration": iteration,
        }
        result.interview_hash = dict_hash(hash_data)

        if _timing is not None:
            _timing["create_result_object"] = (
                _timing.get("create_result_object", 0) + (_time.time() - _t) * 1000
            )

        return result

    def build_edsl_results(
        self,
        job_id: str,
        job_def: "JobDefinition | None" = None,
        _timing: dict | None = None,
    ) -> Any:
        """
        Build an EDSL Results object from all completed interviews.

        Args:
            job_id: The job ID
            job_def: Optional pre-fetched job definition to avoid duplicate DB calls
            _timing: Optional dict to collect timing data

        Returns an edsl.results.Results object.
        """
        import time as _time

        # Use passed job_def if available, otherwise fetch
        if job_def is None:
            _t = _time.time()
            job_def = self._jobs.get_definition(job_id)
            if _timing is not None:
                _timing["get_job_def"] = (_time.time() - _t) * 1000
        if job_def is None:
            raise ValueError(f"Job {job_id} not found")

        # =====================================================================
        # BATCH PREFETCH: Fetch all data in 2 DB calls instead of 4
        # =====================================================================

        # DB CALL 1: Fetch survey + interview_defs + questions in ONE batch
        _t = _time.time()
        keys_batch1 = [f"job:{job_id}:survey"]
        for iid in job_def.interview_ids:
            keys_batch1.append(f"job:{job_id}:interview:{iid}")
        for qid in job_def.question_ids or []:
            keys_batch1.append(f"job:{job_id}:question:{qid}")

        batch1_data = self._storage.batch_read_persistent(keys_batch1)
        if _timing is not None:
            _timing["db_call_1_survey_interviews_questions"] = (
                _time.time() - _t
            ) * 1000

        # Parse survey from batch1
        _t = _time.time()
        survey_data = batch1_data.get(f"job:{job_id}:survey")
        survey = Survey.from_dict(survey_data) if survey_data else None
        if _timing is not None:
            _timing["deserialize_survey"] = (_time.time() - _t) * 1000

        # Parse interview_defs from batch1
        _t = _time.time()
        interview_defs = {}
        for iid in job_def.interview_ids:
            data = batch1_data.get(f"job:{job_id}:interview:{iid}")
            if data:
                interview_defs[iid] = InterviewDefinition.from_dict(iid, job_id, data)
            else:
                interview_defs[iid] = None
        if _timing is not None:
            _timing["deserialize_interview_defs"] = (_time.time() - _t) * 1000

        # Parse questions_data from batch1
        questions_data = {}
        for qid in job_def.question_ids or []:
            questions_data[qid] = batch1_data.get(f"job:{job_id}:question:{qid}")

        # Collect unique agent/scenario/model IDs from interview_defs
        agent_ids = set()
        scenario_ids = set()
        model_ids = set()
        for interview_def in interview_defs.values():
            if interview_def:
                agent_ids.add(interview_def.agent_id)
                scenario_ids.add(interview_def.scenario_id)
                model_ids.add(interview_def.model_id)

        # DB CALL 2: Fetch ALL agent/scenario/model data
        _t = _time.time()
        keys_batch2 = []
        for aid in agent_ids:
            keys_batch2.append(f"job:{job_id}:agent:{aid}")
        for sid in scenario_ids:
            keys_batch2.append(f"job:{job_id}:scenario:{sid}")
        for mid in model_ids:
            keys_batch2.append(f"job:{job_id}:model:{mid}")
        all_object_data = (
            self._storage.batch_read_persistent(keys_batch2) if keys_batch2 else {}
        )
        if _timing is not None:
            _timing["db_call_2_agent_scenario_model"] = (_time.time() - _t) * 1000

        # DB CALL 3: Batch fetch ALL interview states (1 Redis call instead of N)
        _t = _time.time()
        interview_states = self._interviews.get_states_batch(job_def.interview_ids)
        if _timing is not None:
            _timing["get_interview_states"] = (_time.time() - _t) * 1000

        # Determine which interviews are completed
        completed_interview_ids = [
            iid
            for iid, state in interview_states.items()
            if state
            in (InterviewState.COMPLETED, InterviewState.COMPLETED_WITH_FAILURES)
        ]

        # DB CALL 4: Batch fetch ALL answers for completed interviews (1 Redis call instead of N)
        _t = _time.time()
        question_names = []
        if job_def.question_ids and questions_data:
            for q_id in job_def.question_ids:
                q_data = questions_data.get(q_id)
                if q_data:
                    question_names.append(q_data.get("question_name", q_id))

        all_answers = {}
        if completed_interview_ids and question_names:
            all_answers = self._answers.get_for_interviews_batch(
                job_id, completed_interview_ids, question_names
            )
        if _timing is not None:
            _timing["get_answers_batch"] = (_time.time() - _t) * 1000

        # =====================================================================
        # BUILD RESULTS: Use pre-fetched data (no more DB calls in loop)
        # =====================================================================

        result_list = []
        _t_loop = _time.time()
        for interview_id in completed_interview_ids:
            # Pass all pre-fetched data to avoid DB calls inside build_edsl_result
            interview_def = interview_defs.get(interview_id)
            interview_answers = all_answers.get(interview_id, {})
            result = self.build_edsl_result(
                job_id,
                interview_id,
                job_def=job_def,
                survey=survey,
                interview_def=interview_def,
                all_object_data=all_object_data,
                questions_data=questions_data,
                prefetched_answers=interview_answers,
                _timing=_timing,
            )
            result_list.append(result)
        if _timing is not None:
            _timing["build_results_loop_total"] = (_time.time() - _t_loop) * 1000

        # Create the Results object
        _t = _time.time()
        results = Results(
            survey=survey,
            data=result_list,
        )
        if _timing is not None:
            _timing["create_results_object"] = (_time.time() - _t) * 1000

        return results

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _extract_dag(self, survey: Any) -> dict[str, set[str]]:
        """Extract the dependency DAG from an EDSL Survey.

        The DAG includes dependencies from:
        - Memory plan (prior questions referenced)
        - Skip logic rules (questions that may be skipped based on prior answers)
        - Piping (questions that reference prior answers in their text)
        """
        # survey.dag() is a method that returns a DAG combining memory, rules, and piping
        # The DAG uses question indices as keys, which we need to convert to names
        if hasattr(survey, "dag"):
            # Call the method to get the DAG
            raw_dag = survey.dag()  # Returns index-based DAG like {1: {0}, 2: {0}}

            # Build index-to-name mapping
            index_to_name = {}
            for i, q in enumerate(survey.questions):
                index_to_name[i] = q.question_name

            # Convert index-based DAG to name-based DAG
            dag = {}
            for child_idx, parent_indices in raw_dag.items():
                if child_idx in index_to_name:
                    child_name = index_to_name[child_idx]
                    parent_names = set()
                    for parent_idx in parent_indices:
                        if parent_idx in index_to_name:
                            parent_names.add(index_to_name[parent_idx])
                    if parent_names:
                        dag[child_name] = parent_names

            # Add implicit dependencies from skip/stop rules
            # If question q0 has a rule that can affect q1 (stop, jump), then q1
            # must wait for q0 to complete so skip logic can evaluate properly.
            if (
                hasattr(survey, "rule_collection")
                and survey.rule_collection is not None
            ):
                non_default = getattr(survey.rule_collection, "non_default_rules", None)
                if non_default:
                    for rule in non_default:
                        source_idx = rule.current_q
                        if source_idx not in index_to_name:
                            continue
                        source_name = index_to_name[source_idx]
                        # All questions after the source depend on it
                        for target_idx in range(source_idx + 1, len(survey.questions)):
                            target_name = index_to_name[target_idx]
                            if target_name not in dag:
                                dag[target_name] = set()
                            dag[target_name].add(source_name)

            return dag

        # Fallback: no dependencies
        return {}

    def _extract_questions(self, survey: Any) -> list:
        """Extract questions from an EDSL Survey."""
        if hasattr(survey, "questions"):
            return list(survey.questions)
        if hasattr(survey, "_questions"):
            return list(survey._questions)
        return []

    def _get_question_name(self, question: Any) -> str:
        """Get the name/identifier of a question."""
        if hasattr(question, "question_name"):
            return question.question_name
        if hasattr(question, "name"):
            return question.name
        if isinstance(question, dict):
            return question.get(
                "question_name", question.get("name", str(id(question)))
            )
        return str(id(question))

    def _get_or_create_id(self, obj: Any) -> str:
        """Get or create an ID for an object."""
        if hasattr(obj, "id"):
            return str(obj.id)
        if hasattr(obj, "_id"):
            return str(obj._id)
        if isinstance(obj, dict) and "id" in obj:
            return str(obj["id"])
        return generate_id()

    @staticmethod
    def _resolve_question_options(
        options: Any, answer_dict: dict, scenario: Any
    ) -> Any:
        """Resolve template variables in question_options.

        Handles:
        - String templates: "{{ q1.answer }}"
        - Dict format: {"from": "{{ q1.answer }}", "add": ["Other"]}
        - Non-template values (lists, None): returned as-is
        """
        import re

        # Dict format: {"from": "{{ q1.answer }}", "add": ["Option X"]}
        if isinstance(options, dict) and "from" in options:
            from_template = options["from"]
            additional = options.get("add", [])
            base = JobService._resolve_template_string(
                from_template, answer_dict, scenario
            )
            if isinstance(base, list):
                return base + additional
            # Couldn't resolve the "from" template
            return additional if additional else options

        # String template: "{{ q1.answer }}"
        if isinstance(options, str) and "{{" in options:
            return JobService._resolve_template_string(options, answer_dict, scenario)

        # Non-template (list, None, etc.) — return as-is
        return options

    @staticmethod
    def _resolve_template_string(
        template: str, answer_dict: dict, scenario: Any
    ) -> Any:
        """Resolve a single template string like '{{ q1.answer }}' or '{{ scenario.var }}'."""
        import re

        # Match {{ question_name.answer }}
        match = re.match(r"\{\{\s*(\w+)\.answer\s*\}\}", template.strip())
        if match:
            q_name = match.group(1)
            if q_name in answer_dict and answer_dict[q_name] is not None:
                return answer_dict[q_name]

        # Match {{ scenario.variable }}
        match = re.match(r"\{\{\s*scenario\.(\w+)\s*\}\}", template.strip())
        if match and scenario:
            attr = match.group(1)
            if hasattr(scenario, attr):
                return getattr(scenario, attr)
            if isinstance(scenario, dict) and attr in scenario:
                return scenario[attr]

        # Couldn't resolve — return the raw template
        return template

    def _to_dict(self, obj: Any) -> dict:
        """Convert an object to a dict for storage."""
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        if isinstance(obj, dict):
            return obj
        # Fallback: store the repr
        return {"_repr": repr(obj), "_type": type(obj).__name__}

    def _generate_question_permutations(
        self, questions: list, questions_to_randomize: list[str]
    ) -> dict[str, list]:
        """
        Generate randomized question option permutations.

        For each question in questions_to_randomize that has question_options,
        generates a random permutation of those options.

        Args:
            questions: List of question objects from the survey
            questions_to_randomize: List of question names that should have
                                    their options randomized

        Returns:
            Dict mapping question_name -> permuted options list
        """
        import random

        if not questions_to_randomize:
            return {}

        permutations = {}
        for question in questions:
            q_name = self._get_question_name(question)
            if q_name not in questions_to_randomize:
                continue

            # Get question options
            options = None
            if hasattr(question, "question_options"):
                options = question.question_options
            elif isinstance(question, dict) and "question_options" in question:
                options = question["question_options"]

            if options and isinstance(options, list) and len(options) > 1:
                # Generate a random permutation
                permutations[q_name] = random.sample(options, len(options))

        return permutations

    # =========================================================================
    # FileStore Blob Handling
    # =========================================================================

    def _is_filestore_dict(self, value: Any) -> bool:
        """Check if a dict represents a serialized FileStore."""
        if not isinstance(value, dict):
            return False
        # FileStore dicts have these characteristic keys
        return "base64_string" in value and "mime_type" in value and "suffix" in value

    def _offload_scenario_filestores(
        self, job_id: str, scenario_id: str, scenario_dict: dict
    ) -> dict:
        """
        Extract FileStore blobs from a scenario dict and store them separately.

        For each FileStore found in scenario values:
        1. Extract the base64_string
        2. Store it as a blob with a unique ID
        3. Replace base64_string with a blob reference

        Returns the modified scenario dict with blob references.
        """
        import base64

        modified = {}
        for key, value in scenario_dict.items():
            if self._is_filestore_dict(value):
                # This is a FileStore - offload its blob
                base64_str = value.get("base64_string")
                if base64_str and base64_str != "offloaded":
                    # Generate blob ID
                    blob_id = f"blob:{job_id}:{scenario_id}:{key}"

                    # Decode base64 to bytes and store
                    blob_data = base64.b64decode(base64_str)
                    metadata = {
                        "job_id": job_id,
                        "scenario_id": scenario_id,
                        "field_key": key,
                        "mime_type": value.get("mime_type"),
                        "suffix": value.get("suffix"),
                        "original_size": len(base64_str),
                    }
                    self._storage.write_blob(blob_id, blob_data, metadata)

                    # Replace base64_string with blob reference
                    modified_value = value.copy()
                    modified_value["base64_string"] = "offloaded"
                    modified_value["_blob_id"] = blob_id
                    modified[key] = modified_value
                else:
                    # Already offloaded or no base64_string
                    modified[key] = value
            else:
                modified[key] = value

        return modified

    def _restore_scenario_filestores(self, scenario_dict: dict) -> dict:
        """
        Restore FileStore blobs from storage into a scenario dict.

        For each offloaded FileStore (has _blob_id):
        1. Read the blob from storage
        2. Re-encode as base64
        3. Replace the base64_string

        Returns the restored scenario dict.
        """
        import base64

        modified = {}
        for key, value in scenario_dict.items():
            if (
                self._is_filestore_dict(value)
                and value.get("base64_string") == "offloaded"
            ):
                blob_id = value.get("_blob_id")
                if blob_id:
                    blob_data = self._storage.read_blob(blob_id)
                    if blob_data:
                        # Restore base64_string
                        modified_value = value.copy()
                        modified_value["base64_string"] = base64.b64encode(
                            blob_data
                        ).decode("utf-8")
                        # Remove blob reference (it's now inline)
                        modified_value.pop("_blob_id", None)
                        modified[key] = modified_value
                    else:
                        # Blob not found - keep as is
                        modified[key] = value
                else:
                    modified[key] = value
            else:
                modified[key] = value

        return modified

    def get_scenario_with_files(self, job_id: str, scenario_id: str) -> dict | None:
        """
        Get a scenario with FileStore blobs restored.

        Use this when you need the full scenario data including file content,
        such as when rendering prompts for LLM calls.
        """
        scenario_data = self._jobs.get_scenario(job_id, scenario_id)
        if scenario_data is None:
            return None
        return self._restore_scenario_filestores(scenario_data)

    # =========================================================================
    # Job Recovery (for Distributed Execution)
    # =========================================================================

    def recover_job(
        self, job_id: str, running_timeout: int = 300
    ) -> JobDefinition | None:
        """
        Recover a job's state from persistent storage.

        This is used after a process restart to rebuild volatile state
        (counters, ready queues) from persistent data (definitions, answers).

        Tasks that were RUNNING when the process died are reset to READY
        and requeued if they've been running longer than running_timeout.

        Args:
            job_id: ID of job to recover
            running_timeout: Seconds after which a RUNNING task is considered stale

        Returns:
            JobDefinition if job exists, None otherwise
        """
        job_def = self._jobs.get_definition(job_id)
        if not job_def:
            return None

        # Recover each interview
        for interview_id in job_def.interview_ids:
            self._recover_interview(job_id, interview_id, running_timeout)

        return job_def

    def _recover_interview(
        self, job_id: str, interview_id: str, running_timeout: int = 300
    ) -> None:
        """
        Rebuild interview state from persistent data.

        Reconstructs volatile counters from task statuses and answers.
        Requeues tasks that were RUNNING when process died.
        """
        interview_def = self._interviews.get_definition(job_id, interview_id)
        if not interview_def:
            return

        completed = 0
        skipped = 0
        failed = 0
        blocked = 0
        tasks_to_requeue = []

        for task_id in interview_def.task_ids:
            status = self._tasks.get_status(task_id)

            if status == TaskStatus.COMPLETED:
                completed += 1
            elif status == TaskStatus.SKIPPED:
                skipped += 1
            elif status == TaskStatus.FAILED:
                failed += 1
            elif status == TaskStatus.BLOCKED:
                blocked += 1
            elif status == TaskStatus.RUNNING:
                # Task was in-flight when process died
                # Check if it's been running too long
                # Since we don't track start time precisely, we assume stale
                tasks_to_requeue.append(task_id)
            elif status == TaskStatus.QUEUED or status == TaskStatus.RENDERING:
                # Was in process of being rendered/queued - requeue
                tasks_to_requeue.append(task_id)

        # Update volatile counters
        status = InterviewStatus(
            interview_id=interview_id,
            completed=completed,
            skipped=skipped,
            failed=failed,
            blocked=blocked,
        )
        self._storage.write_volatile(status.completed_key, completed)
        self._storage.write_volatile(status.skipped_key, skipped)
        self._storage.write_volatile(status.failed_key, failed)
        self._storage.write_volatile(status.blocked_key, blocked)

        # Requeue stale tasks
        for task_id in tasks_to_requeue:
            self._requeue_task(job_id, interview_id, task_id)

    def _requeue_task(self, job_id: str, interview_id: str, task_id: str) -> None:
        """
        Requeue a task that was in-flight when process died.

        Resets task to READY status and adds to ready queue.
        """
        # Check if task definition exists
        task_def = self._tasks.get_definition(job_id, interview_id, task_id)
        if not task_def:
            return

        # Check if all dependencies are satisfied
        # (they should be if task was previously RUNNING/QUEUED)
        deps_satisfied = True
        for dep_task_id in task_def.depends_on:
            dep_status = self._tasks.get_status(dep_task_id)
            if dep_status not in (TaskStatus.COMPLETED, TaskStatus.SKIPPED):
                deps_satisfied = False
                break

        if deps_satisfied:
            # Reset to READY and add to ready queue
            self._tasks.set_status(task_id, TaskStatus.READY)
            self._tasks.add_to_ready(job_id, task_id)
        else:
            # Dependencies not satisfied - set to PENDING
            self._tasks.set_status(task_id, TaskStatus.PENDING)

    def list_jobs(self, state: JobState | None = None) -> list[str]:
        """
        List all job IDs, optionally filtered by state.

        Args:
            state: If provided, only return jobs in this state

        Returns:
            List of job IDs
        """
        # Scan for job metadata keys
        keys = self._storage.scan_keys_persistent("job:*:meta")

        job_ids = []
        for key in keys:
            # Extract job_id from key pattern "job:{job_id}:meta"
            parts = key.split(":")
            if len(parts) >= 2:
                job_id = parts[1]
                if state is None:
                    job_ids.append(job_id)
                else:
                    job_state = self._jobs.get_state(job_id)
                    if job_state == state:
                        job_ids.append(job_id)

        return job_ids

    def get_incomplete_jobs(self) -> list[str]:
        """Get all jobs that are not yet completed."""
        incomplete = []
        for job_id in self.list_jobs():
            state = self._jobs.get_state(job_id)
            if state in (JobState.PENDING, JobState.RUNNING):
                incomplete.append(job_id)
        return incomplete

    def recover_all_incomplete_jobs(self, running_timeout: int = 300) -> list[str]:
        """
        Recover all incomplete jobs.

        Returns list of job IDs that were recovered.
        """
        incomplete = self.get_incomplete_jobs()
        recovered = []

        for job_id in incomplete:
            job_def = self.recover_job(job_id, running_timeout)
            if job_def:
                recovered.append(job_id)

        return recovered
