"""Portable workflow, state, participant, and executor specifications.

Only data is loaded. Algorithm implementations must already be available in
the selected EDSL runtime; no source text, imports, or pickle is executed.
"""

from copy import deepcopy
import json
from pathlib import Path

from edsl import Agent, Model, Scenario, Survey
from edsl._data_contracts import definition_fingerprint, validate_data
from edsl.sharedstate import SharedStateMap, SQLiteStateBackend
from edsl.sharedstate.dsl_runtime import default_runtime

from .coordinator import WorkflowCoordinator
from .definition import HumanWorkflow
from .execution import ExecutionPlan
from .store import SQLiteWorkflowStore


class WorkflowExperiment:
    """A JSON-portable experiment with explicit runtime capability dependencies."""

    def __init__(
        self, workflow, states, agents, execution_plan, *, metadata=None, runtime=None
    ):
        agents = tuple(agents)
        if any(
            a.has_dynamic_traits_function or hasattr(a, "answer_question_directly")
            for a in agents
        ):
            raise ValueError("portable agents cannot contain Python callbacks")
        self._check_questions(workflow.to_dict())
        self.workflow = HumanWorkflow.from_dict(workflow.to_dict())
        self.states = tuple(SharedStateMap.from_dict(s.to_dict()) for s in states)
        self.agents = tuple(Agent.from_dict(a.to_dict()) for a in agents)
        self.execution_plan = ExecutionPlan.from_dict(execution_plan.to_dict())
        self.metadata = deepcopy(metadata or {})
        self.runtime = runtime or default_runtime()
        self.validate()

    def validate(self):
        validate_data(self.to_dict(), path="workflow experiment")
        maps = {s.state_id: s for s in self.states}
        if len(maps) != len(self.states):
            raise ValueError("experiment state IDs must be unique")
        names = [a.name for a in self.agents]
        if any(not n for n in names) or len(names) != len(set(names)):
            raise ValueError("experiment agents require unique names")
        for state in self.states:
            for machine in state.definition.machines.values():
                self.runtime.validate_capabilities(machine)
        operations = [
            op for step in self.workflow.steps for op in (*step.reads, *step.writes)
        ]
        operations += [rule.read for rule in self.workflow.pause_rules]
        for op in operations:
            if op.state_id not in maps or definition_fingerprint(
                op.definition.to_dict()
            ) != definition_fingerprint(maps[op.state_id].definition.to_dict()):
                raise ValueError(
                    "workflow references an absent or different state definition"
                )
        for step in self.workflow.steps:
            if not any(step.assignee.matches(a.traits) for a in self.agents):
                raise ValueError(f"step {step.name!r} has no assigned participant")
        for agent in self.agents:
            executor = self.execution_plan.resolve(agent.traits)
            if executor.kind == "llm" and not executor.options.get("model"):
                raise ValueError("LLM executor must name a model")
            if executor.kind == "scripted" and not isinstance(
                executor.options.get("answers"), dict
            ):
                raise ValueError("portable scripted executor requires literal answers")

    def to_dict(self):
        return {
            "type": "workflow_experiment",
            "version": 1,
            "workflow": self.workflow.to_dict(),
            "states": [s.to_dict() for s in self.states],
            "agents": [a.to_dict() for a in self.agents],
            "execution_plan": self.execution_plan.to_dict(),
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, data, *, runtime=None):
        if data.get("type") != "workflow_experiment" or data.get("version") != 1:
            raise ValueError("unsupported workflow experiment serialization")
        cls._check_questions(data["workflow"])
        if any("traits" not in agent for agent in data["agents"]):
            raise ValueError(
                "portable agents require the data-only traits representation"
            )
        return cls(
            HumanWorkflow.from_dict(data["workflow"]),
            [SharedStateMap.from_dict(s) for s in data["states"]],
            [Agent.from_dict(deepcopy(a)) for a in data["agents"]],
            ExecutionPlan.from_dict(data["execution_plan"]),
            metadata=data.get("metadata"),
            runtime=runtime,
        )

    @staticmethod
    def _check_questions(workflow):
        for step in workflow["steps"]:
            for question in step["survey"]["questions"]:
                if question.get("question_type") == "functional":
                    raise ValueError(
                        "portable experiments do not embed functional Python questions"
                    )

    def save(self, path):
        path = Path(path)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(
            json.dumps(self.to_dict(), indent=2, allow_nan=False) + "\n"
        )
        temporary.replace(path)

    @classmethod
    def load(cls, path, *, runtime=None):
        return cls.from_dict(json.loads(Path(path).read_text()), runtime=runtime)

    def run(self, output, *, responses=None, resume=False, instance_id="experiment"):
        """Execute until a declared pause or completion.

        ``responses`` is optional replay data: a sequence of dictionaries with
        ``step``, ``participant``, and ``answers``. Supplying it forbids model
        calls, including when an answer is missing. Without it, configured LLM
        executors call their hosted provider through EDSL. All questions in a
        ready batch are opened before submitting any of that batch's answers.
        Live LLM work in each ready batch is executed as one EDSL Jobs object,
        preserving each interview's own rendered survey, agent, and model.
        """
        output = Path(output)
        pinned = output / "experiment.json"
        if pinned.exists():
            if not resume:
                raise FileExistsError("saved experiment exists; use resume=True")
            if json.loads(pinned.read_text()) != self.to_dict():
                raise ValueError("saved experiment specification changed")
        elif resume:
            raise FileNotFoundError("no experiment to resume")
        replay = None
        if responses is not None:
            replay = {}
            for row in responses:
                key = (row["step"], row["participant"])
                if key in replay:
                    raise ValueError(f"duplicate replay response: {key}")
                replay[key] = row["answers"]
        self.validate()
        output.mkdir(parents=True, exist_ok=True)
        if not pinned.exists():
            self.save(pinned)
        store = SQLiteWorkflowStore(output / "workflow.sqlite")
        backends = {
            s.state_id: SQLiteStateBackend(
                s, output / f"state-{i}.sqlite", runtime=self.runtime
            )
            for i, s in enumerate(self.states)
        }
        if resume:
            coordinator = WorkflowCoordinator.restore(
                instance_id, store, state_backends=backends
            )
            coordinator.recover(instance_id, max_attempts=3)
            if store.instance_status(instance_id) == "paused":
                coordinator.resume(instance_id)
        else:
            coordinator = WorkflowCoordinator(
                self.workflow, store, state_backends=backends
            )
            coordinator.launch(
                self.agents,
                instance_id=instance_id,
                random_seed=self.metadata.get("seed", instance_id),
            )
        agents = {a.name: a for a in self.agents}
        while pending := store.pending_outbox(instance_id):
            opened_items = []
            for row in pending:
                claim = store.claim_outbox(row["id"])
                if claim is None:
                    continue
                store.mark_delivered(row["id"], claim_token=claim)
                opened_items.append(coordinator.open(row["work_item_id"]))
            if replay is None:
                llm_items = [
                    item
                    for item in opened_items
                    if self.execution_plan.resolve(
                        agents[item.participant_id].traits
                    ).kind
                    == "llm"
                ]
                groups = {}
                for item in llm_items:
                    options = self.execution_plan.resolve(
                        agents[item.participant_id].traits
                    ).options
                    key = (
                        item.step_name,
                        json.dumps(options, sort_keys=True),
                        json.dumps(self._batch_survey(item).to_dict(), sort_keys=True),
                    )
                    groups.setdefault(key, []).append(item)
                for group in groups.values():
                    self._run_llm_batch(group, agents, coordinator, store, output)
                opened_items = [item for item in opened_items if item not in llm_items]
            for opened in opened_items:
                # Scripted work and supplied replay answers need no inference job.
                attempt = store.start_attempt(opened.id, lease_seconds=600)
                agent = agents[opened.participant_id]
                executor = self.execution_plan.resolve(agent.traits)
                store.record_executor(opened.id, executor.kind, executor.options)
                try:
                    if executor.kind == "scripted":
                        answers = deepcopy(executor.options["answers"])
                    elif replay is not None:
                        answers = deepcopy(replay[(opened.step_name, agent.name)])
                    else:
                        raise ValueError(
                            "human work needs a human delivery adapter or replay responses"
                        )
                    coordinator.submit(
                        opened.id,
                        answers,
                        idempotency_key=f"experiment:{opened.id}",
                        attempt_id=attempt["id"],
                    )
                except Exception as exc:
                    if store.item(opened.id)["status"] != "committing":
                        store.finish_attempt(
                            attempt["id"],
                            status="failed",
                            error_kind="exception",
                            error_message=str(exc)[:1000],
                        )
                        store.retry_item(
                            opened.id, reason="resume after executor failure"
                        )
                    raise
        status = store.instance_status(instance_id)
        if status not in {"paused", "completed"}:
            raise RuntimeError("workflow has unfinished work without a declared pause")
        return {
            "status": status,
            "instance_id": instance_id,
            "completed_items": sum(
                i["status"] == "completed" for i in store.items(instance_id)
            ),
            "pauses": [
                e for e in store.events(instance_id) if e["kind"] == "workflow.paused"
            ],
        }

    @staticmethod
    def _batch_survey(item):
        """Parameterize text only; differing response schemas get separate jobs."""
        data = item.survey.to_dict()
        for question in data["questions"]:
            if "question_name" in question:
                name = question["question_name"]
                question["question_text"] = (
                    "{{ workflow_question_texts[" + repr(name) + "] }}"
                )
        data["memory_plan"]["survey_question_texts"] = [
            q["question_text"] for q in data["questions"] if "question_name" in q
        ]
        return Survey.from_dict(data)

    def _run_llm_batch(self, opened_items, agents, coordinator, store, output):
        """One EDSL job per compatible step; match unordered results by participant."""
        from datetime import datetime, timezone
        import time

        attempts, participants, scenarios = {}, [], []
        by_id = {item.id: item for item in opened_items}
        started = time.monotonic()
        try:
            for item in opened_items:
                attempts[item.id] = store.start_attempt(item.id, lease_seconds=600)
                agent = agents[item.participant_id]
                executor = self.execution_plan.resolve(agent.traits)
                options = executor.options
                store.record_executor(item.id, executor.kind, options)
                model = Model(
                    options["model"],
                    service_name=options.get("service"),
                    **options.get("parameters", {}),
                )
                store.record_model(item.id, model.to_dict())
                participants.append(agent)
                scenarios.append(
                    Scenario(
                        {
                            "workflow_work_item_id": item.id,
                            "workflow_question_texts": {
                                q.question_name: q.question_text
                                for q in item.survey.questions
                            },
                        }
                    )
                )
            if len({a.name for a in participants}) != len(opened_items):
                raise ValueError("batch requires distinct participants")
            # Pair agent i only with its own frozen private scenario i.
            job = (
                self._batch_survey(opened_items[0])
                .by(participants)
                .by(scenarios)
                .by(model)
                .zip_assign(over=("agents", "scenarios"))
            )
            jobs_folder = output / "jobs"
            jobs_folder.mkdir(exist_ok=True)
            job_path = (
                jobs_folder
                / f"batch-{opened_items[0].id}-{attempts[opened_items[0].id]['id']}.json"
            )
            job_path.write_text(json.dumps(job.to_dict(), indent=2) + "\n")
            batch = {
                "started_at": datetime.now(timezone.utc).isoformat(),
                "work_item_ids": list(by_id),
                "steps": sorted({item.step_name for item in opened_items}),
                "interviews": len(opened_items),
                "job_path": str(job_path.relative_to(output)),
            }
            with (output / "inference-batches.jsonl").open("a") as handle:
                handle.write(json.dumps({**batch, "event": "started"}) + "\n")
            results = job.run(
                disable_remote_inference=True,
                disable_remote_cache=True,
                cache=False,
                stop_on_exceptions=False,
            )
            seen, failures = set(), []
            for result in results:
                item_id = result.scenario["workflow_work_item_id"]
                if item_id not in by_id or item_id in seen:
                    raise ValueError("unexpected or duplicate work-item result")
                seen.add(item_id)
                item = by_id[item_id]
                if result.agent.name != item.participant_id:
                    raise ValueError("result participant differs from work item")
                record = {
                    "work_item_id": item_id,
                    "step": item.step_name,
                    "participant": item.participant_id,
                    "result": result.to_dict(),
                }
                with (output / "model-calls.jsonl").open("a") as handle:
                    handle.write(json.dumps(record, allow_nan=False) + "\n")
                try:
                    required = {q.question_name for q in item.survey.questions}
                    if not required.issubset(result.answer) or any(
                        result.answer[name] is None for name in required
                    ):
                        raise ValueError("incomplete model result")
                    coordinator.submit(
                        item_id,
                        dict(result.answer),
                        idempotency_key=f"experiment:{item_id}",
                        attempt_id=attempts[item_id]["id"],
                    )
                except Exception as exc:
                    failures.append(exc)
            if seen != set(by_id):
                failures.append(ValueError("EDSL job returned an incomplete batch"))
            if failures:
                raise failures[0]
            with (output / "inference-batches.jsonl").open("a") as handle:
                handle.write(
                    json.dumps(
                        {
                            **batch,
                            "event": "completed",
                            "results": len(results),
                            "elapsed_seconds": time.monotonic() - started,
                        }
                    )
                    + "\n"
                )
        except Exception as exc:
            # Keep successful submissions; only unfinished interviews retry.
            for item_id, attempt in attempts.items():
                if store.item(item_id)["status"] not in {"completed", "committing"}:
                    store.finish_attempt(
                        attempt["id"],
                        status="failed",
                        error_kind="exception",
                        error_message=str(exc)[:1000],
                    )
                    store.retry_item(item_id, reason="resume after EDSL batch failure")
            raise
