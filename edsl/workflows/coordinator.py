"""Coordinator for durable human or simulated-agent workflow execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from uuid import uuid4

from edsl.agents import Agent
from edsl.sharedstate import SQLiteStateBackend, resolve_read, resolve_write
from edsl.sharedstate.steps import StepContext
from edsl.surveys import Survey

from .definition import HumanWorkflow
from .store import SQLiteWorkflowStore


@dataclass(frozen=True)
class OpenedWorkItem:
    id: str
    instance_id: str
    step_name: str
    participant_id: str
    survey: Survey
    shared_state: Mapping[str, Any]
    state_versions: Mapping[str, int]


class WorkflowCoordinator:
    """Turns completed submissions into newly deliverable work."""

    def __init__(
        self,
        workflow: HumanWorkflow,
        store: SQLiteWorkflowStore,
        *,
        state_backends: Mapping[str, SQLiteStateBackend] | None = None,
    ):
        self.workflow = workflow
        self.store = store
        self.state_backends = dict(state_backends or {})

    def launch(
        self, participants: Sequence[Agent], *, instance_id: str | None = None
    ) -> str:
        instance_id = instance_id or str(uuid4())
        encoded: list[tuple[str, dict[str, Any]]] = []
        seen: set[str] = set()
        for index, agent in enumerate(participants):
            participant_id = agent.name or f"participant-{index + 1}"
            if participant_id in seen:
                raise ValueError(
                    f"participant identifiers must be unique: {participant_id!r}"
                )
            seen.add(participant_id)
            encoded.append((participant_id, agent.to_dict()))
        self.store.create_instance(instance_id, self.workflow.to_dict(), encoded)
        for step in self.workflow.steps:
            matches = [
                participant_id
                for participant_id, data in encoded
                if step.assignee.matches(data.get("traits", {}))
            ]
            if not matches:
                raise ValueError(f"step {step.name!r} has no matching participant")
            from .definition import Quorum

            if isinstance(step.completion, Quorum) and step.completion.count > len(
                matches
            ):
                raise ValueError(
                    f"step {step.name!r} requires quorum {step.completion.count}, "
                    f"but only {len(matches)} participants match"
                )
            for participant_id in matches:
                self.store.create_item(instance_id, step.name, participant_id)
        self.reevaluate(instance_id)
        return instance_id

    def reevaluate(self, instance_id: str) -> None:
        self._settle_quorums(instance_id)
        for item in self.store.items(instance_id):
            if item["status"] != "blocked":
                continue
            step = self.workflow.step(item["step_name"])
            dependencies = [
                dependency_item
                for dependency in step.after
                for dependency_item in self.store.items(
                    instance_id, step_name=dependency
                )
            ]
            if not all(
                dependency["status"] in ("completed", "skipped")
                for dependency in dependencies
            ):
                continue
            if step.enabled_when is None and any(
                dependency["status"] == "skipped" for dependency in dependencies
            ):
                self.store.skip(item["id"], reason="dependency skipped")
            elif self._enabled(instance_id, step.enabled_when):
                self.store.make_ready(item["id"])
            else:
                self.store.skip(item["id"], reason="enable condition was false")
        self.store.finish_instance_if_complete(instance_id)

    def _settle_quorums(self, instance_id: str) -> None:
        from .definition import Quorum

        for step in self.workflow.steps:
            if not isinstance(step.completion, Quorum):
                continue
            items = self.store.items(instance_id, step_name=step.name)
            completed = sum(item["status"] == "completed" for item in items)
            if completed >= step.completion.count:
                for item in items:
                    if item["status"] not in ("completed", "skipped"):
                        self.store.skip(item["id"], reason="quorum reached")

    def _step_complete(self, instance_id: str, step_name: str) -> bool:
        items = self.store.items(instance_id, step_name=step_name)
        return bool(items) and all(
            item["status"] in ("completed", "skipped") for item in items
        )

    def _enabled(self, instance_id: str, condition) -> bool:
        from .definition import (
            AllCondition,
            AnswerCondition,
            AnyCondition,
            NotCondition,
            OutputCountCondition,
            OutputDisagreementCondition,
            OutputMajorityCondition,
            StepCompletedCondition,
        )

        if condition is None:
            return True
        if isinstance(condition, AnswerCondition):
            answers = self.store.step_answers(instance_id, condition.step_name)
            return bool(answers) and all(
                answer.get(condition.question_name) == condition.equals
                for answer in answers
            )
        if isinstance(condition, StepCompletedCondition):
            items = self.store.items(instance_id, step_name=condition.step_name)
            return bool(items) and all(item["status"] == "completed" for item in items)
        if isinstance(condition, AllCondition):
            return all(
                self._enabled(instance_id, item) for item in condition.conditions
            )
        if isinstance(condition, AnyCondition):
            return any(
                self._enabled(instance_id, item) for item in condition.conditions
            )
        if isinstance(condition, NotCondition):
            return not self._enabled(instance_id, condition.condition)
        if isinstance(condition, OutputCountCondition):
            values = self._output_values(
                instance_id, condition.step_name, condition.question_name
            )
            return (
                sum(value == condition.value for value in values) >= condition.minimum
            )
        if isinstance(condition, OutputDisagreementCondition):
            values = self._output_values(
                instance_id, condition.step_name, condition.question_name
            )
            return (
                len(values) > 1 and len({self._hashable(value) for value in values}) > 1
            )
        if isinstance(condition, OutputMajorityCondition):
            values = self._output_values(
                instance_id, condition.step_name, condition.question_name
            )
            return (
                bool(values)
                and sum(value == condition.value for value in values) > len(values) / 2
            )
        raise TypeError(f"unsupported workflow condition {type(condition).__name__}")

    def _output_values(
        self, instance_id: str, step_name: str, question_name: str
    ) -> list[Any]:
        return [
            answers[question_name]
            for answers in self.store.step_answers(instance_id, step_name)
            if question_name in answers
        ]

    @staticmethod
    def _hashable(value: Any) -> str:
        import json

        return json.dumps(value, sort_keys=True, default=str)

    def open(self, item_id: str) -> OpenedWorkItem:
        item = self.store.item(item_id)
        if item["status"] not in ("ready", "in_progress"):
            raise ValueError(f"work item {item_id!r} is not ready")
        step = self.workflow.step(item["step_name"])
        agent_data = self.store.participant(item["instance_id"], item["participant_id"])
        traits = {"name": item["participant_id"], **dict(agent_data.get("traits", {}))}
        context = StepContext({}, item_id, agent_traits=traits)
        views: dict[str, Any] = {}
        versions: dict[str, int] = {}
        for read in step.reads:
            backend = self._backend(read.state_id)
            observed = backend.read(resolve_read(read, context))
            views[read.target] = observed.value
            versions[read.target] = observed.version
        prior_answers = {
            workflow_step.name: self.store.step_answers(
                item["instance_id"], workflow_step.name
            )
            for workflow_step in self.workflow.steps
            if workflow_step.output_visibility is None
            or any(
                selector.matches(traits) for selector in workflow_step.output_visibility
            )
        }
        replacements = {
            "shared_state": views,
            "participant": traits,
            "workflow": {
                "answers": {
                    name: answers[0]
                    for name, answers in prior_answers.items()
                    if answers
                },
                "outputs": {
                    name: answers for name, answers in prior_answers.items() if answers
                },
            },
        }
        rendered = Survey(
            [question.render(replacements) for question in step.survey.questions]
        )
        self.store.record_render(
            item_id,
            survey=rendered.to_dict(),
            shared_state=views,
            state_versions=versions,
        )
        self.store.mark_opened(item_id)
        return OpenedWorkItem(
            id=item_id,
            instance_id=item["instance_id"],
            step_name=item["step_name"],
            participant_id=item["participant_id"],
            survey=rendered,
            shared_state=views,
            state_versions=versions,
        )

    def submit(
        self,
        item_id: str,
        answers: Mapping[str, Any],
        *,
        idempotency_key: str,
    ) -> None:
        item = self.store.item(item_id)
        if item["status"] == "completed":
            if self.store.complete(item_id, answers, idempotency_key):
                return
        step = self.workflow.step(item["step_name"])
        agent_data = self.store.participant(item["instance_id"], item["participant_id"])
        context = StepContext(
            dict(answers),
            item_id,
            agent_traits={
                "name": item["participant_id"],
                **dict(agent_data.get("traits", {})),
            },
        )
        for write in step.writes:
            outcome = self._backend(write.state_id).apply(resolve_write(write, context))
            if not outcome.accepted:
                raise RuntimeError(f"shared-state write {write.step_id!r} was rejected")
        self.store.complete(item_id, answers, idempotency_key)
        self.reevaluate(item["instance_id"])

    def _backend(self, state_id: str) -> SQLiteStateBackend:
        try:
            return self.state_backends[state_id]
        except KeyError as exc:
            raise KeyError(
                f"no workflow state backend registered for {state_id!r}"
            ) from exc
