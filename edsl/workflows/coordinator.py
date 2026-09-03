"""Coordinator for durable human or simulated-agent workflow execution."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import statistics
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
                for dependency in (*step.after, *step.settled_after)
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
                if dependency["step_name"] in step.after
            ):
                self.store.skip(item["id"], reason="dependency skipped")
            elif self._enabled(instance_id, step.enabled_when):
                self.store.make_ready(item["id"])
            else:
                repeat = step.metadata.get("repeat")
                reason = (
                    f"repeat {repeat['name']!r} terminated before iteration "
                    f"{repeat['iteration']}"
                    if repeat
                    else "enable condition was false"
                )
                self.store.skip(item["id"], reason=reason)
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
            ChanceCondition,
            ExpressionCondition,
            NotCondition,
            OutputCountCondition,
            OutputDisagreementCondition,
            OutputMajorityCondition,
            OutputRangeCondition,
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
        if isinstance(condition, ChanceCondition):
            digest = hashlib.sha256(
                f"{instance_id}:{condition.key}".encode("utf-8")
            ).digest()
            draw = int.from_bytes(digest, "big") / (1 << (8 * len(digest)))
            return draw < condition.probability
        if isinstance(condition, ExpressionCondition):
            return bool(self._evaluate_expression(instance_id, condition.expression))
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
        if isinstance(condition, OutputRangeCondition):
            values = self._output_values(
                instance_id, condition.step_name, condition.question_name
            )
            try:
                numeric = [float(value) for value in values]
            except (TypeError, ValueError):
                return False
            return bool(numeric) and max(numeric) - min(numeric) <= condition.maximum
        raise TypeError(f"unsupported workflow condition {type(condition).__name__}")

    def _output_values(
        self, instance_id: str, step_name: str, question_name: str
    ) -> list[Any]:
        return [
            answers[question_name]
            for answers in self.store.step_answers(instance_id, step_name)
            if question_name in answers
        ]

    def _evaluate_expression(
        self,
        instance_id: str,
        expression,
        derived: Mapping[str, Mapping[str, Any]] | None = None,
        bindings: Mapping[str, Any] | None = None,
    ) -> Any:
        from .definition import WorkflowExpression

        def evaluate(value):
            return (
                self._evaluate_expression(instance_id, value, derived, bindings)
                if isinstance(value, WorkflowExpression)
                else value
            )

        op = expression.op
        if op == "submission_value":
            if bindings is None or "submission_value" not in bindings:
                raise ValueError("submission_value is only valid inside a submission map")
            return bindings["submission_value"]
        if op == "joined_value":
            if bindings is None or "joined_values" not in bindings:
                raise ValueError("joined_value is only valid inside a participant join map")
            return bindings["joined_values"][expression.options["source"]][expression.options["question_name"]]
        if op == "map_submissions":
            submissions = evaluate(expression.args[0])
            question = expression.options["question_name"]
            mapped = {}
            for submission in submissions:
                try:
                    own_value = submission["answers"][question]
                except KeyError as exc:
                    raise ValueError(
                        f"submission has no answer for mapped question {question!r}"
                    ) from exc
                mapped[submission["participant_id"]] = self._evaluate_expression(
                    instance_id,
                    expression.args[1],
                    derived,
                    {"submission_value": own_value},
                )
            if not mapped:
                raise LookupError("submission-map inputs are not available")
            return mapped
        if op == "map_joined_submissions":
            rows = evaluate(expression.args[0])
            if not rows:
                raise LookupError("joined submission inputs are not available")
            return {
                row["participant_id"]: self._evaluate_expression(
                    instance_id, expression.args[1], derived, {"joined_values": row["sources"]}
                )
                for row in rows
            }
        if op == "if_else":
            condition = evaluate(expression.args[0])
            return evaluate(expression.args[1] if condition else expression.args[2])
        args = [evaluate(item) for item in expression.args]
        if op == "literal":
            return args[0]
        if op == "parameter":
            try:
                return self.workflow.metadata["parameters"][expression.options["name"]]["value"]
            except KeyError as exc:
                raise ValueError(f"unknown workflow parameter {expression.options['name']!r}") from exc
        if op == "seeded_uniform":
            digest = hashlib.sha256(
                f"{instance_id}:{expression.options['key']}".encode("utf-8")
            ).digest()
            unit = int.from_bytes(digest, "big") / (1 << (8 * len(digest)))
            return args[0] + (args[1] - args[0]) * unit
        if op == "seeded_integer":
            digest = hashlib.sha256(
                f"{instance_id}:{expression.options['key']}".encode("utf-8")
            ).digest()
            return args[0] + int.from_bytes(digest, "big") % (args[1] - args[0] + 1)
        if op == "step_outputs":
            values = self._output_values(
                instance_id,
                expression.options["step_name"],
                expression.options["question_name"],
            )
            if not values:
                raise LookupError("workflow output is not available")
            return values
        if op == "step_answer":
            values = self._output_values(instance_id, expression.options["step_name"], expression.options["question_name"])
            if len(values) != 1:
                raise LookupError("workflow answer requires exactly one available value")
            return values[0]
        if op == "step_submissions":
            return [
                {"participant_id": item["participant_id"], "answers": dict(answers)}
                for item in self.store.items(instance_id, step_name=expression.options["step_name"])
                if (answers := self.store.item_answers(item["id"])) is not None
            ]
        if op == "join_submissions":
            names = tuple(expression.options["names"])
            indexed = [
                {item["participant_id"]: item["answers"] for item in submissions}
                for submissions in args
            ]
            participant_sets = [set(items) for items in indexed]
            if not participant_sets or not participant_sets[0] or any(items != participant_sets[0] for items in participant_sets[1:]):
                raise LookupError("participant join inputs are incomplete or do not match")
            return [
                {"participant_id": participant_id, "sources": {name: indexed[position][participant_id] for position, name in enumerate(names)}}
                for participant_id in sorted(participant_sets[0])
            ]
        if op == "derived_ref":
            available = (
                derived if derived is not None else self._evaluate_derived(instance_id)
            )
            return available[expression.options["name"]][expression.options["field"]]
        if op in {"mean", "median", "minimum", "maximum", "range", "sum"}:
            values = [float(value) for value in args[0]]
            if not values:
                raise ValueError(f"{op} requires at least one numeric value")
            operations = {
                "mean": statistics.fmean,
                "median": statistics.median,
                "minimum": min,
                "maximum": max,
                "range": lambda items: max(items) - min(items),
                "sum": sum,
            }
            return operations[op](values)
        if op == "count_value":
            return sum(value == args[1] for value in args[0])
        if op == "all_equal":
            if not args[0]:
                raise LookupError("all_equal inputs are not available")
            return len({self._hashable(value) for value in args[0]}) == 1
        if op == "absolute":
            return abs(args[0])
        if op == "order_statistic":
            values = [float(value) for value in args[0]]
            rank = int(expression.options["rank"])
            if rank < 1 or rank > len(values):
                raise LookupError(
                    f"order-statistic rank {rank} is unavailable for {len(values)} values"
                )
            reverse = expression.options.get("direction") == "largest"
            if expression.options.get("direction") not in {"largest", "smallest"}:
                raise ValueError("order-statistic direction must be 'largest' or 'smallest'")
            return sorted(values, reverse=reverse)[rank - 1]
        binary = {
            "add": lambda left, right: left + right,
            "subtract": lambda left, right: left - right,
            "multiply": lambda left, right: left * right,
            "divide": lambda left, right: left / right,
            "at_most": lambda left, right: left <= right,
            "at_least": lambda left, right: left >= right,
            "equals": lambda left, right: left == right,
        }
        if op in binary:
            return binary[op](*args)
        if op == "get_item":
            collection, key = args
            if isinstance(collection, Mapping):
                return collection[str(key)]
            return collection[int(key)]
        if op == "lookup":
            key = str(args[0])
            mapping = expression.options["mapping"]
            if key in mapping:
                return evaluate(mapping[key])
            if expression.options.get("has_default"):
                return evaluate(expression.options["default"])
            raise KeyError(f"lookup has no value for key {key!r}")
        if op == "payoff_matrix":
            submissions = sorted(args[0], key=lambda item: item["participant_id"])
            if len(submissions) != 2:
                raise LookupError("payoff_matrix inputs are not available")
            question = expression.options["question_name"]
            action_codes = expression.options.get("action_codes")
            actions = [str(item["answers"][question]) for item in submissions]
            if action_codes is None:
                codes = [action[0].upper() for action in actions]
            else:
                try:
                    codes = [action_codes[action] for action in actions]
                except KeyError as exc:
                    raise ValueError(
                        f"no payoff-matrix action code for submitted answer {exc.args[0]!r}"
                    ) from exc
            key = "".join(codes)
            try:
                values = expression.options["matrix"][key]
            except KeyError as exc:
                raise ValueError(
                    f"payoff matrix has no outcome for action-code key {key!r}"
                ) from exc
            if len(values) != len(submissions):
                raise ValueError(
                    f"payoff matrix outcome {key!r} must contain {len(submissions)} payoffs"
                )
            return {item["participant_id"]: values[index] for index, item in enumerate(submissions)}
        if op == "argmin_by":
            submissions, target = args
            if not submissions:
                raise LookupError("ranking inputs are not available")
            question = expression.options["question_name"]
            distances = [(abs(float(item["answers"][question]) - float(target)), item["participant_id"]) for item in submissions]
            best = min(distance for distance, _ in distances)
            winners = [participant for distance, participant in distances if distance == best]
            return winners if expression.options["ties"] == "all" else winners[:1]
        raise ValueError(f"unsupported workflow expression operator {op!r}")

    def _evaluate_derived(self, instance_id: str) -> dict[str, dict[str, Any]]:
        derived: dict[str, dict[str, Any]] = {}
        for definition in self.workflow.derived_values:
            try:
                derived[definition.name] = {
                    name: self._evaluate_expression(instance_id, expression, derived)
                    for name, expression in definition.fields.items()
                }
            except (LookupError, KeyError):
                continue
        return derived

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
        prior_submissions = {
            workflow_step.name: [
                {
                    "participant_id": prior_item["participant_id"],
                    "answers": dict(answers),
                }
                for prior_item in self.store.items(
                    item["instance_id"], step_name=workflow_step.name
                )
                if (answers := self.store.item_answers(prior_item["id"])) is not None
            ]
            for workflow_step in self.workflow.steps
            if workflow_step.name in prior_answers
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
                "submissions": {
                    name: submissions
                    for name, submissions in prior_submissions.items()
                    if submissions
                },
                "derived": self._evaluate_derived(item["instance_id"]),
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
        attempt_id: str | None = None,
    ) -> None:
        item = self.store.item(item_id)
        if item["status"] == "completed":
            if self.store.complete(item_id, answers, idempotency_key):
                if attempt_id is not None:
                    self.store.finish_attempt(attempt_id, status="succeeded")
                return
        step = self.workflow.step(item["step_name"])
        from .structured import structured_contract_from_dict
        for contract_data in step.metadata.get("response_contracts", ()):
            structured_contract_from_dict(contract_data).validate(answers)
        for question_name, (minimum, maximum) in step.answer_bounds.items():
            if question_name not in answers:
                continue
            value = float(answers[question_name])
            low = self._evaluate_expression(item["instance_id"], minimum) if minimum else None
            high = self._evaluate_expression(item["instance_id"], maximum) if maximum else None
            if (low is not None and value < float(low)) or (high is not None and value > float(high)):
                raise ValueError(f"answer {question_name!r}={value:g} is outside dynamic bounds [{low}, {high}]")
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
        if attempt_id is not None:
            self.store.finish_attempt(attempt_id, status="succeeded")
        self.reevaluate(item["instance_id"])

    def _backend(self, state_id: str) -> SQLiteStateBackend:
        try:
            return self.state_backends[state_id]
        except KeyError as exc:
            raise KeyError(
                f"no workflow state backend registered for {state_id!r}"
            ) from exc
