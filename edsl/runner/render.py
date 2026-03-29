"""
RenderService - Handles prompt rendering for tasks.

This service takes a task and renders the prompts needed for LLM execution.
It reconstructs the EDSL objects from stored data and uses the EDSL
PromptConstructor to generate system and user prompts.
"""

from dataclasses import dataclass
from typing import Any

import base64

from .storage import StorageProtocol
from .stores import JobStore, InterviewStore, TaskStore, AnswerStore
from .models import TaskDefinition, TaskStatus, InterviewDefinition

# EDSL imports - relative since this module lives inside edsl package
from ..scenarios import Scenario
from ..agents import Agent
from ..language_models import LanguageModel
from ..questions import QuestionBase
from ..surveys import Survey
from ..surveys.memory import MemoryPlan
from ..invigilators.prompt_constructor import PromptConstructor
from ..invigilators.prompt_helpers import PromptPlan
from ..caching import CacheEntry


@dataclass
class RenderedPrompt:
    """The result of rendering a task's prompts."""

    task_id: str
    job_id: str
    interview_id: str
    system_prompt: str
    user_prompt: str
    estimated_tokens: int
    cache_key: str
    files_list: list[Any] | None = None
    question_name: str | None = None
    question_id: str | None = None
    model_id: str | None = None
    model_name: str | None = None
    service_name: str | None = None
    iteration: int = (
        0  # Which iteration this task belongs to (for cache key differentiation)
    )
    agent_name: str | None = None


class RenderService:
    """Renders prompts for tasks using EDSL's PromptConstructor."""

    def __init__(self, storage: StorageProtocol):
        self._storage = storage
        self._jobs = JobStore(storage)
        self._interviews = InterviewStore(storage)
        self._tasks = TaskStore(storage)
        self._answers = AnswerStore(storage)

    def _is_filestore_dict(self, value: Any) -> bool:
        """Check if a dict represents a serialized FileStore."""
        if not isinstance(value, dict):
            return False
        return "base64_string" in value and "mime_type" in value and "suffix" in value

    def _restore_scenario_filestores(self, scenario_dict: dict) -> dict:
        """
        Restore FileStore blobs from storage into a scenario dict.

        If a FileStore was offloaded (base64_string == "offloaded"),
        retrieve the blob data and restore the base64_string.
        """
        if scenario_dict is None:
            return scenario_dict

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
                        modified_value = value.copy()
                        modified_value["base64_string"] = base64.b64encode(
                            blob_data
                        ).decode("utf-8")
                        modified_value.pop("_blob_id", None)
                        modified[key] = modified_value
                    else:
                        modified[key] = value
                else:
                    modified[key] = value
            else:
                modified[key] = value
        return modified

    def _apply_option_permutation(
        self, question_data: dict, question_name: str, permutations: dict[str, list]
    ) -> dict:
        """
        Apply randomized option permutation to question data.

        If the question has a stored permutation, replaces question_options
        with the permuted version.

        Args:
            question_data: The question dict from storage
            question_name: Name of the question
            permutations: Dict mapping question_name -> permuted options list

        Returns:
            Modified question_data with permuted options (or original if no permutation)
        """
        if not permutations or question_name not in permutations:
            return question_data

        if question_data is None:
            return question_data

        # Make a copy to avoid mutating the cached data
        modified = question_data.copy()
        modified["question_options"] = permutations[question_name]
        return modified

    def render_task(
        self, job_id: str, interview_id: str, task_id: str
    ) -> RenderedPrompt:
        """Render the prompts for a single task."""
        task_def = self._tasks.get_definition(job_id, interview_id, task_id)
        interview_def = self._interviews.get_definition(job_id, interview_id)

        # Load stored objects
        scenario_data = self._jobs.get_scenario(job_id, task_def.scenario_id)
        # Restore any offloaded FileStore blobs
        scenario_data = self._restore_scenario_filestores(scenario_data)
        agent_data = self._jobs.get_agent(job_id, task_def.agent_id)
        model_data = self._jobs.get_model(job_id, task_def.model_id)
        question_data = self._jobs.get_question(job_id, task_def.question_id)

        # Apply question option permutations if this question was randomized
        question_data = self._apply_option_permutation(
            question_data,
            task_def.question_name,
            interview_def.question_option_permutations,
        )

        # Get current answers for memory/piping
        current_answers = self._get_current_answers(job_id, interview_id, task_def)

        # Render using EDSL
        prompts = self._render_with_edsl(
            scenario_data=scenario_data,
            agent_data=agent_data,
            model_data=model_data,
            question_data=question_data,
            current_answers=current_answers,
        )

        # Compute cache key and estimate tokens
        # Include iteration in cache key so different iterations don't share cache
        cache_key = self._compute_cache_key(
            model_data,
            prompts["system_prompt"],
            prompts["user_prompt"],
            iteration=task_def.iteration,
        )
        estimated_tokens = (
            len(prompts["system_prompt"]) + len(prompts["user_prompt"])
        ) // 4 + 500

        return RenderedPrompt(
            task_id=task_id,
            job_id=job_id,
            interview_id=interview_id,
            system_prompt=prompts["system_prompt"],
            user_prompt=prompts["user_prompt"],
            estimated_tokens=estimated_tokens,
            cache_key=cache_key,
            files_list=prompts.get("files_list"),
            question_name=task_def.question_name,
            question_id=task_def.question_id,
            model_id=task_def.model_id,
            model_name=model_data.get("model") if model_data else None,
            service_name=model_data.get("inference_service") if model_data else None,
            iteration=task_def.iteration,
            agent_name=agent_data.get("name") if agent_data else None,
        )

    def _get_current_answers(
        self, job_id: str, interview_id: str, task_def: TaskDefinition
    ) -> dict[str, Any]:
        """Get answers from completed tasks in this interview."""
        current_answers = {}
        interview_def = self._interviews.get_definition(job_id, interview_id)

        for other_task_id in interview_def.task_ids:
            if other_task_id == task_def.task_id:
                continue

            other_task = self._tasks.get_definition(job_id, interview_id, other_task_id)
            status = self._tasks.get_status(other_task_id)

            if status == TaskStatus.COMPLETED:
                answer = self._answers.get(
                    job_id, interview_id, other_task.question_name
                )
                if answer is not None:
                    current_answers[other_task.question_name] = answer.answer
                    # Include comment for piping ({{ qname.comment }})
                    if answer.comment:
                        current_answers[
                            f"{other_task.question_name}_comment"
                        ] = answer.comment

        return current_answers

    # Class-level timing accumulators for profiling
    _profile_times: dict[str, float] = {}
    _profile_counts: dict[str, int] = {}

    def _render_with_edsl(
        self,
        scenario_data: dict,
        agent_data: dict,
        model_data: dict,
        question_data: dict,
        current_answers: dict[str, Any],
    ) -> dict[str, str]:
        """Use EDSL's PromptConstructor to render the prompts."""
        import time as _t

        # Reconstruct EDSL objects with timing
        _t0 = _t.time()
        scenario = (
            Scenario.from_dict(scenario_data)
            if scenario_data and "_default" not in scenario_data
            else Scenario({})
        )
        self._profile_times["scenario_from_dict"] = self._profile_times.get(
            "scenario_from_dict", 0
        ) + (_t.time() - _t0)

        _t0 = _t.time()
        agent = (
            Agent.from_dict(agent_data)
            if agent_data and "_default" not in agent_data
            else Agent()
        )
        self._profile_times["agent_from_dict"] = self._profile_times.get(
            "agent_from_dict", 0
        ) + (_t.time() - _t0)

        _t0 = _t.time()
        model = (
            LanguageModel.from_dict(model_data)
            if model_data and "_default" not in model_data
            else LanguageModel.from_dict({"model": "gpt-4o-mini"})
        )
        self._profile_times["model_from_dict"] = self._profile_times.get(
            "model_from_dict", 0
        ) + (_t.time() - _t0)

        _t0 = _t.time()
        question = QuestionBase.from_dict(question_data)
        self._profile_times["question_from_dict"] = self._profile_times.get(
            "question_from_dict", 0
        ) + (_t.time() - _t0)

        # Create survey for prompt constructor
        # Include stub questions for dependencies so piping ({{ dep.answer }}) works
        _t0 = _t.time()
        questions_for_survey = []
        if current_answers:
            from ..questions import QuestionFreeText

            for qname in current_answers:
                if qname.endswith("_comment") or qname.endswith("_generated_tokens"):
                    continue
                if qname != question.question_name:
                    stub = QuestionFreeText(
                        question_name=qname,
                        question_text="(dependency)",
                    )
                    questions_for_survey.append(stub)
        questions_for_survey.append(question)
        survey = Survey(questions_for_survey)
        memory_plan = MemoryPlan(survey=survey)
        self._profile_times["survey_memory_plan"] = self._profile_times.get(
            "survey_memory_plan", 0
        ) + (_t.time() - _t0)

        # Create and use prompt constructor
        _t0 = _t.time()
        prompt_constructor = PromptConstructor(
            agent=agent,
            question=question,
            scenario=scenario,
            survey=survey,
            model=model,
            current_answers=current_answers,
            memory_plan=memory_plan,
            prompt_plan=PromptPlan(),
        )
        self._profile_times["prompt_constructor_init"] = self._profile_times.get(
            "prompt_constructor_init", 0
        ) + (_t.time() - _t0)

        _t0 = _t.time()
        prompts = prompt_constructor.get_prompts()
        self._profile_times["get_prompts"] = self._profile_times.get(
            "get_prompts", 0
        ) + (_t.time() - _t0)

        self._profile_counts["render_calls"] = (
            self._profile_counts.get("render_calls", 0) + 1
        )

        system_prompt = str(prompts.get("system_prompt", ""))
        if getattr(question, "question_type", None) == "thinking" or getattr(question, "_is_thinking_question", False):
            system_prompt = getattr(question, "_system_prompt", "")
        return {
            "system_prompt": system_prompt,
            "user_prompt": str(prompts.get("user_prompt", "")),
            "files_list": prompts.get("files_list"),
        }

    def _render_with_objects(
        self,
        scenario: "Scenario",
        agent: "Agent",
        model: "LanguageModel",
        question: "QuestionBase",
        survey: "Survey",
        memory_plan: "MemoryPlan",
        current_answers: dict[str, Any],
    ) -> dict[str, str]:
        """Render prompts using pre-built EDSL objects (avoids redundant from_dict)."""
        import time as _t

        _t0 = _t.time()
        prompt_constructor = PromptConstructor(
            agent=agent,
            question=question,
            scenario=scenario,
            survey=survey,
            model=model,
            current_answers=current_answers,
            memory_plan=memory_plan,
            prompt_plan=PromptPlan(),
        )
        self._profile_times["prompt_constructor_init"] = self._profile_times.get(
            "prompt_constructor_init", 0
        ) + (_t.time() - _t0)

        _t0 = _t.time()
        prompts = prompt_constructor.get_prompts()
        self._profile_times["get_prompts"] = self._profile_times.get(
            "get_prompts", 0
        ) + (_t.time() - _t0)

        self._profile_counts["render_calls"] = (
            self._profile_counts.get("render_calls", 0) + 1
        )

        system_prompt = str(prompts.get("system_prompt", ""))
        if getattr(question, "question_type", None) == "thinking" or getattr(question, "_is_thinking_question", False):
            system_prompt = getattr(question, "_system_prompt", "")
        return {
            "system_prompt": system_prompt,
            "user_prompt": str(prompts.get("user_prompt", "")),
            "files_list": prompts.get("files_list"),
        }

    def get_profile_stats(self) -> dict:
        """Return profiling statistics for _render_with_edsl calls."""
        return {
            "times_ms": {k: v * 1000 for k, v in self._profile_times.items()},
            "counts": self._profile_counts,
        }

    def reset_profile_stats(self):
        """Reset profiling statistics."""
        self._profile_times = {}
        self._profile_counts = {}

    def _compute_cache_key(
        self, model_data: dict, system_prompt: str, user_prompt: str, iteration: int = 0
    ) -> str:
        """Compute cache key for the rendered prompt.

        Uses EDSL's CacheEntry.gen_key() to produce MD5 hashes that match the
        existing cache entries in Coopr's Cloud SQL (17.7M entries).
        """
        return CacheEntry.gen_key(
            model=model_data.get("model", "") if model_data else "",
            parameters=model_data.get("parameters", {}) if model_data else {},
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            iteration=iteration,
        )


class RenderWorker:
    """Worker that renders tasks from the ready queue."""

    def __init__(self, storage: StorageProtocol, job_service: Any = None):
        self._storage = storage
        self._render_service = RenderService(storage)
        self._tasks = TaskStore(storage)
        self._interviews = InterviewStore(storage)
        self._jobs = JobStore(storage)
        self._answers = AnswerStore(storage)
        self._job_service = job_service  # Optional, for skip logic evaluation

    def render_ready_tasks(
        self,
        job_id: str,
        max_tasks: int = 100,
        debug: bool = False,
        job_data: dict | None = None,
    ) -> list[RenderedPrompt]:
        """
        Render all ready tasks for a job using batch operations.

        This optimized version reduces Redis calls from O(n*m) to O(1) by:
        1. Batch popping ready tasks
        2. Batch fetching locations, definitions, and related data
        3. Batch setting statuses

        If a JobService is provided, also evaluates skip logic before rendering.
        Tasks that should be skipped are marked as skipped and not rendered.

        Args:
            job_id: The job ID to render tasks for.
            max_tasks: Maximum number of tasks to render in one batch.
            debug: Whether to print debug information.
            job_data: Optional pre-loaded job data dict with keys:
                      'survey', 'scenarios', 'agents', 'models', 'questions'.
                      If provided, this data is used instead of fetching from PostgreSQL.
        """
        import time as _time

        _render_start = _time.time()
        _step_timings: dict[str, float] = {}

        # Step 1: Batch pop ready tasks
        _t0 = _time.time()
        task_ids = self._tasks.pop_ready_tasks_batch(job_id, max_tasks)
        _step_timings["step1_pop_ready"] = _time.time() - _t0
        if not task_ids:
            return []

        if debug:
            print(f"  [render] Popped {len(task_ids)} tasks from ready queue")

        # Step 2: Batch get locations
        _t0 = _time.time()
        locations = self._tasks.get_locations_batch(task_ids)
        _step_timings["step2_get_locations"] = _time.time() - _t0

        # Group tasks by interview_id for efficient batch fetches
        _t0 = _time.time()
        tasks_by_interview: dict[str, list[str]] = {}
        for task_id in task_ids:
            if task_id in locations:
                _, interview_id = locations[task_id]
                if interview_id not in tasks_by_interview:
                    tasks_by_interview[interview_id] = []
                tasks_by_interview[interview_id].append(task_id)
        _step_timings["step2b_group_tasks"] = _time.time() - _t0

        # Step 3: Batch get interview definitions
        # Use job_data cache if available, otherwise fetch from PostgreSQL
        _t0 = _time.time()
        interview_ids = list(tasks_by_interview.keys())
        _step3_timing: dict = {}
        _step3_from_cache = False
        if job_data and job_data.get("interview_defs"):
            # Use cached interview definitions from submit_job
            interview_defs = {}
            cached_defs = job_data["interview_defs"]
            for iid in interview_ids:
                if iid in cached_defs:
                    interview_defs[iid] = InterviewDefinition.from_dict(
                        iid, job_id, cached_defs[iid]
                    )
                else:
                    interview_defs[iid] = None
            _step3_from_cache = True
        else:
            # Fetch from PostgreSQL
            interview_defs = self._interviews.get_definitions_batch(
                job_id, interview_ids, _timing=_step3_timing
            )
        _step_timings["step3_interview_defs"] = _time.time() - _t0
        # Store detailed timing (already in ms from stores.py)
        if _step3_timing:
            _step_timings["step3a_build_keys"] = (
                _step3_timing.get("build_keys", 0) / 1000
            )  # convert to seconds for consistency
            _step_timings["step3b_db_call"] = _step3_timing.get("db_call", 0) / 1000
            _step_timings["step3c_deserialize"] = (
                _step3_timing.get("deserialize", 0) / 1000
            )
            _step_timings["step3_n"] = _step3_timing.get("n", 0)
        if _step3_from_cache:
            _step_timings["step3_from_cache"] = 1  # Marker: used cache

        # Step 4: Batch get task definitions
        # Use job_data cache if available, otherwise fetch from PostgreSQL
        _t0 = _time.time()
        all_task_defs: dict[str, TaskDefinition] = {}
        _step4_db_calls = 0
        _step4_total_db_ms = 0.0
        _step4_total_deserialize_ms = 0.0
        _step4_from_cache = False
        if job_data and job_data.get("task_defs"):
            # Use cached task definitions from submit_job
            cached_task_defs = job_data["task_defs"]
            for interview_id, task_id_list in tasks_by_interview.items():
                for task_id in task_id_list:
                    if task_id in cached_task_defs:
                        all_task_defs[task_id] = TaskDefinition.from_dict(
                            task_id, job_id, interview_id, cached_task_defs[task_id]
                        )
            _step4_from_cache = True
        else:
            # Fetch from PostgreSQL (N DB calls - 1 per interview)
            for interview_id, task_id_list in tasks_by_interview.items():
                _step4_timing: dict = {}
                task_defs = self._tasks.get_definitions_batch(
                    job_id, interview_id, task_id_list, _timing=_step4_timing
                )
                all_task_defs.update(task_defs)
                _step4_db_calls += 1
                _step4_total_db_ms += _step4_timing.get("db_call", 0)
                _step4_total_deserialize_ms += _step4_timing.get("deserialize", 0)
        _step_timings["step4_task_defs"] = _time.time() - _t0
        # Store detailed timing
        _step_timings["step4a_db_calls_total"] = (
            _step4_total_db_ms / 1000
        )  # convert to seconds
        _step_timings["step4b_deserialize_total"] = _step4_total_deserialize_ms / 1000
        _step_timings["step4_n_db_calls"] = _step4_db_calls
        _step_timings["step4_n_tasks"] = len(all_task_defs)
        if _step4_from_cache:
            _step_timings["step4_from_cache"] = 1  # Marker: used cache

        # Step 4.5: Pre-cache data for skip logic evaluation (if JobService available)
        # This reduces O(T) fetches to O(1) by caching survey, index map, and answers
        _t0 = _time.time()
        cached_survey = None
        cached_question_index_map: dict[str, int] | None = None
        cached_answers_by_interview: dict[str, dict[str, Any]] = {}

        # Debug counters to verify optimization
        ops_counter = {
            "get_survey": 0,
            "survey_from_dict": 0,
            "gather_answers": 0,
            "skip_task_calls": 0,
        }

        if self._job_service is not None:
            # Fetch and reconstruct survey ONCE
            # Use job_data if available, otherwise fetch from PostgreSQL
            _t_survey = _time.time()
            if job_data and job_data.get("survey"):
                survey_data = job_data["survey"]
                ops_counter["get_survey"] = 0  # No DB call needed
            else:
                survey_data = self._jobs.get_survey(job_id)
                ops_counter["get_survey"] = 1
            _step_timings["step4.5a_get_survey"] = _time.time() - _t_survey

            _t_survey_parse = _time.time()
            if survey_data:
                cached_survey = Survey.from_dict(survey_data)
                ops_counter["survey_from_dict"] = 1

                # Build question_name -> index map ONCE
                cached_question_index_map = {
                    q.question_name: i for i, q in enumerate(cached_survey.questions)
                }
            _step_timings["step4.5b_survey_from_dict"] = _time.time() - _t_survey_parse

            # Pre-fetch answers for each interview ONCE
            # OPTIMIZATION: Use MGET with known question names instead of SCAN
            # Question names are known from the survey, so we can build keys directly
            # MGET is O(Q) where Q = questions, SCAN is O(total_keys_in_redis)
            _t_answers = _time.time()
            num_questions = (
                len(cached_question_index_map) if cached_question_index_map else 0
            )
            if num_questions > 1:
                # Get question names from the cached map (already built in step 4.5b)
                question_names = list(cached_question_index_map.keys())
                for interview_id in tasks_by_interview.keys():
                    # Use get_for_interview which does MGET, not SCAN
                    answers_dict = self._answers.get_for_interview(
                        job_id, interview_id, question_names
                    )
                    # Convert to the format expected by should_skip_task
                    current = {}
                    for qname, answer in answers_dict.items():
                        current[qname] = answer.answer
                        current[f"{qname}.answer"] = answer.answer
                        if answer.comment:
                            current[f"{qname}_comment"] = answer.comment
                    cached_answers_by_interview[interview_id] = current
                    ops_counter["gather_answers"] += 1
            else:
                # Single question survey - no prior answers to gather
                ops_counter["gather_answers_skipped"] = len(tasks_by_interview)
            _step_timings["step4.5c_gather_answers"] = _time.time() - _t_answers

            if debug:
                print(
                    f"  [render] Pre-cached survey with {len(cached_question_index_map or {})} questions, "
                    f"answers for {len(cached_answers_by_interview)} interviews"
                )
        _step_timings["step4.5_total"] = _time.time() - _t0

        # Step 5: Collect unique IDs for scenarios, agents, models, questions
        _t0 = _time.time()
        scenario_ids = set()
        agent_ids = set()
        model_ids = set()
        question_ids = set()

        tasks_to_render = []
        direct_answer_tasks = []
        _skip_logic_time = 0.0

        # Pre-compute whether the survey has any user-defined skip rules ONCE.
        # non_default_rules is a @property that iterates ALL rules each call (O(N)).
        # With 8000 questions = 8000 default rules, calling it per-task =
        # 64M iterations = 18s wasted. Checking once = ~0s.
        _has_skip_rules = False
        if (
            cached_survey is not None
            and hasattr(cached_survey, "rule_collection")
            and cached_survey.rule_collection is not None
        ):
            non_default = getattr(
                cached_survey.rule_collection, "non_default_rules", None
            )
            _has_skip_rules = non_default is not None and len(non_default) > 0

        for task_id in task_ids:
            task_def = all_task_defs.get(task_id)
            if not task_def:
                continue

            # Check for direct answer tasks
            if task_def.execution_type != "llm":
                if debug:
                    print(
                        f"  [render] Task {task_id[:8]}... is {task_def.execution_type}, skipping render"
                    )
                direct_answer_tasks.append(task_id)
                continue

            # Check skip logic only if survey has user-defined skip rules
            if self._job_service is not None and _has_skip_rules:
                _, interview_id = locations[task_id]

                # Get cached answers for this interview
                cached_answers = cached_answers_by_interview.get(interview_id)
                ops_counter["skip_task_calls"] += 1

                _t_skip = _time.time()
                should_skip, skip_reason = self._job_service.should_skip_task(
                    job_id,
                    interview_id,
                    task_id,
                    debug=False,  # Reduce noise
                    cached_survey=cached_survey,
                    cached_question_index_map=cached_question_index_map,
                    cached_answers=cached_answers,
                    cached_task_def=task_def,
                )
                _skip_logic_time += _time.time() - _t_skip
                if should_skip:
                    self._job_service.on_task_skipped(
                        job_id, interview_id, task_id, skip_reason
                    )
                    continue

            tasks_to_render.append(task_id)
            scenario_ids.add(task_def.scenario_id)
            agent_ids.add(task_def.agent_id)
            model_ids.add(task_def.model_id)
            question_ids.add(task_def.question_id)
        _step_timings["step5_collect_ids"] = _time.time() - _t0
        _step_timings["step5a_skip_logic"] = _skip_logic_time

        # Put direct answer tasks back in queue
        _t0 = _time.time()
        for task_id in direct_answer_tasks:
            self._tasks.add_to_ready(job_id, task_id)
        _step_timings["step5b_readd_direct"] = _time.time() - _t0

        # Print optimization summary
        if debug and self._job_service is not None:
            print(f"  [render] OPTIMIZATION SUMMARY for {len(task_ids)} tasks:")
            print(
                f"    - get_survey() calls: {ops_counter['get_survey']} (was {len(task_ids)} before)"
            )
            print(
                f"    - Survey.from_dict() calls: {ops_counter['survey_from_dict']} (was {len(task_ids)} before)"
            )
            print(
                f"    - _gather_current_answers() calls: {ops_counter['gather_answers']} (was {len(task_ids)} before)"
            )
            print(f"    - should_skip_task() calls: {ops_counter['skip_task_calls']}")
            old_complexity = len(task_ids) * (
                2 + 50
            )  # 2 DB calls + ~50 answer fetches per task
            new_complexity = (
                ops_counter["get_survey"]
                + ops_counter["survey_from_dict"]
                + ops_counter["gather_answers"] * 50
            )
            print(
                f"    - Estimated I/O reduction: ~{old_complexity} -> ~{new_complexity} calls"
            )

        if not tasks_to_render:
            return []

        # Step 6: Batch set statuses to RENDERING
        _t0 = _time.time()
        self._tasks.set_statuses_batch(tasks_to_render, TaskStatus.RENDERING)
        _step_timings["step6_set_rendering"] = _time.time() - _t0

        # Step 7: Batch fetch scenarios, agents, models, questions
        # Use job_data if available, otherwise fetch from PostgreSQL
        _t0 = _time.time()
        if job_data and job_data.get("scenarios"):
            scenarios = {sid: job_data["scenarios"].get(sid) for sid in scenario_ids}
        else:
            scenarios = self._jobs.get_scenarios_batch(job_id, list(scenario_ids))

        if job_data and job_data.get("agents"):
            agents = {aid: job_data["agents"].get(aid) for aid in agent_ids}
        else:
            agents = self._jobs.get_agents_batch(job_id, list(agent_ids))

        if job_data and job_data.get("models"):
            models = {mid: job_data["models"].get(mid) for mid in model_ids}
        else:
            models = self._jobs.get_models_batch(job_id, list(model_ids))

        if job_data and job_data.get("questions"):
            questions = {qid: job_data["questions"].get(qid) for qid in question_ids}
        else:
            questions = self._jobs.get_questions_batch(job_id, list(question_ids))
        _step_timings["step7_fetch_objects"] = _time.time() - _t0

        if debug:
            source = "job_data cache" if job_data else "PostgreSQL"
            print(
                f"  [render] Fetched {len(scenarios)} scenarios, {len(agents)} agents, "
                f"{len(models)} models, {len(questions)} questions (from {source})"
            )

        # Step 8: Batch fetch current answers per interview (using depends_on for efficiency)
        # Instead of checking ALL interview tasks, only fetch answers for actual dependencies
        # This reduces O(n) to O(d) where d = number of dependencies (usually small)
        _t0 = _time.time()
        answers_cache: dict[
            str, dict[str, Any]
        ] = {}  # interview_id -> {question_name -> answer}

        # Collect all dependency task IDs from tasks being rendered
        dep_task_ids_by_interview: dict[
            str, set[str]
        ] = {}  # interview_id -> set of dependency task_ids
        for task_id in tasks_to_render:
            task_def = all_task_defs.get(task_id)
            if task_def and task_def.depends_on:
                _, interview_id = locations[task_id]
                if interview_id not in dep_task_ids_by_interview:
                    dep_task_ids_by_interview[interview_id] = set()
                dep_task_ids_by_interview[interview_id].update(task_def.depends_on)

        # Batch fetch definitions for dependency tasks to get question names
        for interview_id, dep_task_ids in dep_task_ids_by_interview.items():
            if not dep_task_ids:
                continue
            # Get definitions for dependency tasks (to get question_names)
            dep_defs = self._tasks.get_definitions_batch(
                job_id, interview_id, list(dep_task_ids)
            )
            question_names = [d.question_name for d in dep_defs.values() if d]
            if question_names:
                # Fetch answers for those specific questions
                answers = self._answers.get_for_interview(
                    job_id, interview_id, question_names
                )
                cache_entry = {}
                for qn, a in answers.items():
                    cache_entry[qn] = a.answer
                    if a.comment:
                        cache_entry[f"{qn}_comment"] = a.comment
                answers_cache[interview_id] = cache_entry
        _step_timings["step8_answer_cache"] = _time.time() - _t0

        if debug:
            print(
                f"  [render] Step 8 (answer caching): {_step_timings['step8_answer_cache']:.2f}s, deps={sum(len(v) for v in dep_task_ids_by_interview.values())}"
            )

        # Step 8.5: Pre-build EDSL objects once per unique ID
        # Instead of calling from_dict() 800 times with the same data,
        # build each unique object once and reuse it in the render loop.
        _t0 = _time.time()
        edsl_scenarios: dict[str, "Scenario"] = {}
        for sid, data in scenarios.items():
            data = self._render_service._restore_scenario_filestores(data)
            if data and "_default" not in data:
                edsl_scenarios[sid] = Scenario.from_dict(data)
            else:
                edsl_scenarios[sid] = Scenario({})

        edsl_agents: dict[str, "Agent"] = {}
        for aid, data in agents.items():
            if data and "_default" not in data:
                edsl_agents[aid] = Agent.from_dict(data)
            else:
                edsl_agents[aid] = Agent()

        edsl_models: dict[str, "LanguageModel"] = {}
        for mid, data in models.items():
            if data and "_default" not in data:
                edsl_models[mid] = LanguageModel.from_dict(data)
            else:
                edsl_models[mid] = LanguageModel.from_dict({"model": "gpt-4o-mini"})

        edsl_questions_base: dict[str, "QuestionBase"] = {}
        for qid, data in questions.items():
            if data:
                edsl_questions_base[qid] = QuestionBase.from_dict(data)

        _step_timings["step8.5_prebuild_objects"] = _time.time() - _t0

        if debug:
            print(
                f"  [render] Step 8.5 (pre-build): {len(edsl_scenarios)} scenarios, "
                f"{len(edsl_agents)} agents, {len(edsl_models)} models, "
                f"{len(edsl_questions_base)} questions in "
                f"{_step_timings['step8.5_prebuild_objects']:.3f}s"
            )

        # Step 9: Render each task using pre-built objects
        _t0 = _time.time()
        rendered = []
        _edsl_render_time = 0.0
        _cache_key_time = 0.0
        _append_time = 0.0
        _lookup_time = 0.0
        _survey_build_time = 0.0

        # Reset timing accumulators before the loop
        from ..invigilators.prompt_constructor import (
            reset_prompt_timings,
            get_prompt_timings,
        )
        from ..invigilators.question_instructions_prompt_builder import (
            reset_build_timings,
            get_build_timings,
        )
        from ..prompts.prompt import reset_render_timings, get_render_timings

        reset_prompt_timings()
        reset_build_timings()
        reset_render_timings()

        # Caches for objects that depend on per-task context
        _permuted_questions: dict[tuple, "QuestionBase"] = {}
        _survey_cache: dict[tuple, tuple] = {}
        _prompt_cache: dict[
            tuple, dict
        ] = {}  # Cache rendered prompts by input combination

        from ..questions import QuestionFreeText as _QuestionFreeText

        for task_id in tasks_to_render:
            _t_loop = _time.time()
            task_def = all_task_defs.get(task_id)
            if not task_def:
                continue

            _, interview_id = locations[task_id]
            interview_def = interview_defs.get(interview_id)

            # Look up pre-built objects by ID
            scenario = edsl_scenarios.get(task_def.scenario_id, Scenario({}))
            agent = edsl_agents.get(task_def.agent_id, Agent())
            model = edsl_models.get(task_def.model_id)
            if not model:
                continue

            # Get question — handle optional permutations
            question = edsl_questions_base.get(task_def.question_id)
            if not question:
                continue
            _lookup_time += _time.time() - _t_loop

            # Track permutation key for prompt caching
            _perm_key = None
            if (
                interview_def
                and interview_def.question_option_permutations
                and task_def.question_name in interview_def.question_option_permutations
            ):
                perms = interview_def.question_option_permutations[
                    task_def.question_name
                ]
                _perm_key = (task_def.question_id, tuple(str(o) for o in perms))
                if _perm_key not in _permuted_questions:
                    q_data = questions.get(task_def.question_id)
                    q_data = self._render_service._apply_option_permutation(
                        q_data,
                        task_def.question_name,
                        interview_def.question_option_permutations,
                    )
                    _permuted_questions[_perm_key] = QuestionBase.from_dict(q_data)
                question = _permuted_questions[_perm_key]

            # Get current answers from cache
            current_answers = answers_cache.get(interview_id, {})

            # Get or build Survey + MemoryPlan (cached by question + answer keys)
            _t_survey = _time.time()
            answer_names = tuple(
                sorted(
                    k
                    for k in current_answers
                    if not k.endswith("_comment")
                    and not k.endswith("_generated_tokens")
                )
            )
            survey_key = (id(question), answer_names)
            if survey_key not in _survey_cache:
                questions_for_survey = []
                if current_answers:
                    for qname in current_answers:
                        if qname.endswith("_comment") or qname.endswith(
                            "_generated_tokens"
                        ):
                            continue
                        if qname != question.question_name:
                            stub = _QuestionFreeText(
                                question_name=qname,
                                question_text="(dependency)",
                            )
                            questions_for_survey.append(stub)
                questions_for_survey.append(question)
                survey = Survey(questions_for_survey)
                _survey_cache[survey_key] = (survey, MemoryPlan(survey=survey))

            survey, memory_plan = _survey_cache[survey_key]
            _survey_build_time += _time.time() - _t_survey

            # Render prompts using pre-built objects (cached by input combination)
            _t_edsl = _time.time()
            prompt_key = (
                task_def.scenario_id,
                task_def.agent_id,
                task_def.model_id,
                task_def.question_id,
                _perm_key,  # None if no permutation, otherwise (qid, perm_tuple)
                answer_names,
            )
            if prompt_key in _prompt_cache:
                prompts = _prompt_cache[prompt_key]
            else:
                prompts = self._render_service._render_with_objects(
                    scenario=scenario,
                    agent=agent,
                    model=model,
                    question=question,
                    survey=survey,
                    memory_plan=memory_plan,
                    current_answers=current_answers,
                )
                _prompt_cache[prompt_key] = prompts
            _edsl_render_time += _time.time() - _t_edsl

            # Compute cache key
            _t_ck = _time.time()
            model_data = models.get(task_def.model_id)
            cache_key = self._render_service._compute_cache_key(
                model_data,
                prompts["system_prompt"],
                prompts["user_prompt"],
                iteration=task_def.iteration,
            )
            estimated_tokens = (
                len(prompts["system_prompt"]) + len(prompts["user_prompt"])
            ) // 4 + 500

            _cache_key_time += _time.time() - _t_ck
            _t_ap = _time.time()
            agent_data = agents.get(task_def.agent_id)
            rendered.append(
                RenderedPrompt(
                    task_id=task_id,
                    job_id=job_id,
                    interview_id=interview_id,
                    system_prompt=prompts["system_prompt"],
                    user_prompt=prompts["user_prompt"],
                    estimated_tokens=estimated_tokens,
                    cache_key=cache_key,
                    files_list=prompts.get("files_list"),
                    question_name=task_def.question_name,
                    question_id=task_def.question_id,
                    model_id=task_def.model_id,
                    model_name=model_data.get("model") if model_data else None,
                    service_name=model_data.get("inference_service")
                    if model_data
                    else None,
                    iteration=task_def.iteration,
                    agent_name=agent_data.get("name") if agent_data else None,
                )
            )
            _append_time += _time.time() - _t_ap

        _step_timings["step9_render_loop"] = _time.time() - _t0
        _step_timings["step9a_edsl_render"] = _edsl_render_time
        _step_timings["step9f_cache_key"] = _cache_key_time
        _step_timings["step9g_append"] = _append_time
        _step_timings["step9h_lookup"] = _lookup_time
        _step_timings["step9i_survey_build"] = _survey_build_time
        _step_timings["step9b_survey_cache_size"] = len(_survey_cache)
        _step_timings["step9c_permuted_questions"] = len(_permuted_questions)
        _step_timings["step9d_prompt_cache_size"] = len(_prompt_cache)
        _step_timings["step9e_prompt_cache_hit_rate"] = (
            f"{len(rendered) - len(_prompt_cache)}/{len(rendered)} hits"
            if rendered
            else "0/0"
        )

        if debug:
            print(
                f"  [render] Step 9 (EDSL render): {_step_timings['step9_render_loop']:.2f}s for {len(rendered)} tasks | "
                f"edsl={_edsl_render_time:.3f}s, cache_key={_cache_key_time:.3f}s, "
                f"append={_append_time:.3f}s, lookup={_lookup_time:.3f}s, "
                f"survey={_survey_build_time:.3f}s, prompt_cache={len(_prompt_cache)} unique"
            )
            # Print accumulated sub-timings from EDSL internals
            pt = get_prompt_timings()
            bt = get_build_timings()
            rt = get_render_timings()
            print(
                f"  [render] Step 9 get_prompts breakdown ({pt['call_count']} calls): "
                f"agent_instr={pt['agent_instructions']:.3f}s, "
                f"agent_persona={pt['agent_persona']:.3f}s, "
                f"q_instructions={pt['question_instructions']:.3f}s "
                f"(init={pt.get('q_instr__init', 0):.3f}s, build={pt.get('q_instr__build', 0):.3f}s), "
                f"prior_memory={pt['prior_question_memory']:.3f}s, "
                f"prompt_plan={pt['prompt_plan']:.3f}s, "
                f"file_keys={pt['file_keys']:.3f}s"
            )
            print(
                f"  [render] Step 9 build() breakdown ({bt['call_count']} calls): "
                f"create_base={bt['create_base_prompt']:.3f}s, "
                f"enrich_opts={bt['enrich_options']:.3f}s, "
                f"render_prompt={bt['render_prompt']:.3f}s "
                f"(build_dict={bt['render_prompt__build_dict']:.3f}s, "
                f"prompt.render={bt['render_prompt__prompt_render']:.3f}s), "
                f"validate={bt['validate_template']:.3f}s, "
                f"survey_instr={bt['append_survey_instr']:.3f}s"
            )
            print(
                f"  [render] Step 9 Prompt._render() breakdown ({rt['call_count']} calls, "
                f"{int(rt['fast_path_skips'])} fast-path skips): "
                f"find_vars={rt['find_template_vars']:.3f}s, "
                f"build_repl={rt['build_replacements']:.3f}s, "
                f"template.render={rt['template_render']:.3f}s, "
                f"total={rt['total_render']:.3f}s"
            )
            print(
                f"  [render] Step 9 prior_answers: "
                f"q_names_to_questions={pt.get('prior_answers__q_names', 0):.3f}s, "
                f"add_answers={pt.get('prior_answers__add_answers', 0):.3f}s"
            )

        # Step 10: Batch set statuses to QUEUED
        _t0 = _time.time()
        task_ids_rendered = [r.task_id for r in rendered]
        self._tasks.set_statuses_batch(task_ids_rendered, TaskStatus.QUEUED)
        _step_timings["step10_set_queued"] = _time.time() - _t0

        # Compute total render time
        _step_timings["total"] = _time.time() - _render_start

        if debug:
            # Print all step timings sorted by key
            time_steps = {
                k: v
                for k, v in sorted(_step_timings.items())
                if isinstance(v, (int, float))
            }
            parts = []
            for k, v in time_steps.items():
                if isinstance(v, float) and v < 100:  # skip counts
                    parts.append(f"{k}={v:.3f}s")
                elif isinstance(v, int) or v >= 100:
                    parts.append(f"{k}={v}")
            print(f"  [render] ALL STEPS: {', '.join(parts)}")

        # Store render timing as timing events for the job
        # This data will be available via the /jobs/{job_id}/timing endpoint
        timing_events = []
        # Count metrics should not be multiplied by 1000
        count_metrics = {
            "step3_n",
            "step4_n_db_calls",
            "step4_n_tasks",
            "step3_from_cache",
            "step4_from_cache",
        }
        for step_name, value in _step_timings.items():
            if step_name in count_metrics:
                # Store counts as-is
                duration_ms = value
            else:
                # Convert seconds to milliseconds
                duration_ms = value * 1000
            timing_events.append(
                {
                    "phase": f"render_{step_name}",
                    "component": "api",
                    "timestamp": _render_start,
                    "duration_ms": duration_ms,
                    "details": {"tasks_rendered": len(rendered)},
                }
            )

        # Store via storage if available
        if hasattr(self._storage, "add_timing_events_batch"):
            self._storage.add_timing_events_batch(job_id, timing_events)

        # Collect EDSL render profiling stats (stored as timing events, not printed)
        profile_stats = self._render_service.get_profile_stats()
        if profile_stats["counts"].get("render_calls", 0) > 0:
            # Reset for next batch
            self._render_service.reset_profile_stats()

            # Add to timing events for visibility via API
            for name, time_ms in profile_stats["times_ms"].items():
                timing_events.append(
                    {
                        "phase": f"render_profile_{name}",
                        "component": "api",
                        "timestamp": _render_start,
                        "duration_ms": time_ms,
                        "details": None,
                    }
                )
            # Re-store with profile events
            if hasattr(self._storage, "add_timing_events_batch"):
                self._storage.add_timing_events_batch(job_id, timing_events)

        if debug:
            print(f"  [render] Rendered {len(rendered)} tasks")

        return rendered
