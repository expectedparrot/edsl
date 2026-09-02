"""Virtual delivery loop for testing workflows with EDSL agents as respondents."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import heapq
import json
from typing import Any, Callable, Mapping, Protocol
from uuid import uuid4

from edsl.agents import Agent
from edsl.language_models import Model
from .coordinator import OpenedWorkItem, WorkflowCoordinator
from .execution import ExecutionPlan


@dataclass(order=True)
class _Scheduled:
    at: datetime
    sequence: int
    callback: Callable[[], None] = field(compare=False)


class VirtualClock:
    def __init__(self, start: datetime | None = None):
        self.now = start or datetime(2025, 1, 1, tzinfo=timezone.utc)
        self._queue: list[_Scheduled] = []
        self._sequence = 0

    def call_later(self, delay: timedelta, callback: Callable[[], None]) -> None:
        self._sequence += 1
        heapq.heappush(
            self._queue, _Scheduled(self.now + delay, self._sequence, callback)
        )

    def run_next(self) -> bool:
        if not self._queue:
            return False
        scheduled = heapq.heappop(self._queue)
        self.now = scheduled.at
        scheduled.callback()
        return True


@dataclass(frozen=True)
class InboxMessage:
    id: str
    participant_id: str
    work_item_id: str
    delivered_at: datetime


class SimulatedInbox:
    def __init__(self):
        self.messages: list[InboxMessage] = []

    def deliver(self, participant_id: str, work_item_id: str, at: datetime) -> None:
        self.messages.append(
            InboxMessage(str(uuid4()), participant_id, work_item_id, at)
        )


class Answerer(Protocol):
    def answer(self, agent: Agent, opened: OpenedWorkItem) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 1
    lease_seconds: float = 300
    retryable: tuple[str, ...] = ("remote_error", "timeout", "exception")

    def __post_init__(self) -> None:
        if self.max_attempts < 1 or self.lease_seconds <= 0:
            raise ValueError(
                "retry policy requires positive attempts and lease duration"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_attempts": self.max_attempts,
            "lease_seconds": self.lease_seconds,
            "retryable": list(self.retryable),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RetryPolicy":
        return cls(
            data.get("max_attempts", 1),
            data.get("lease_seconds", 300),
            tuple(data.get("retryable", ("remote_error", "timeout", "exception"))),
        )


class EDSLAgentAnswerer:
    """Runs the delivered survey through the ordinary EDSL agent/model pipeline."""

    def __init__(
        self,
        model: Model | None = None,
        *,
        run_options: Mapping[str, Any] | None = None,
    ):
        self.model = model or Model("test")
        self.run_options = {
            "disable_remote_inference": True,
            "disable_remote_cache": True,
            "cache": False,
            "stop_on_exceptions": True,
            **dict(run_options or {}),
        }

    def answer(self, agent: Agent, opened: OpenedWorkItem) -> Mapping[str, Any]:
        results = opened.survey.by(agent).by(self.model).run(**self.run_options)
        return dict(results[0].answer)


class WorkflowSimulation:
    """Deliver ready tasks, let recipients respond, and turn the crank to quiescence."""

    def __init__(
        self,
        coordinator: WorkflowCoordinator,
        agents: Mapping[str, Agent],
        answerer: Answerer,
        *,
        response_delay: timedelta = timedelta(),
        execution_plan: ExecutionPlan | None = None,
        answerers: Mapping[str, Answerer] | None = None,
    ):
        self.coordinator = coordinator
        self.agents = dict(agents)
        self.answerer = answerer
        self.execution_plan = execution_plan
        self.answerers = dict(answerers or {})
        self.response_delay = response_delay
        self.clock = VirtualClock()
        self.inbox = SimulatedInbox()

    def run(
        self,
        instance_id: str,
        *,
        resume: bool = False,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        policy = retry_policy or RetryPolicy()
        if resume:
            self.coordinator.store.recover_items(
                instance_id, max_attempts=policy.max_attempts
            )
        while True:
            delivered = self._deliver_pending(policy)
            ran = self.clock.run_next()
            if not delivered and not ran:
                break
        remaining = [
            item
            for item in self.coordinator.store.items(instance_id)
            if item["status"] not in ("completed", "skipped", "failed")
        ]
        failed = [
            item
            for item in self.coordinator.store.items(instance_id)
            if item["status"] == "failed"
        ]
        if failed:
            names = [item["step_name"] for item in failed]
            raise RuntimeError(f"workflow execution failed for steps: {names}")
        if remaining:
            blocked = [(item["step_name"], item["status"]) for item in remaining]
            raise RuntimeError(
                f"workflow reached quiescence with unfinished work: {blocked}"
            )

    def _deliver_pending(self, policy: RetryPolicy) -> bool:
        rows = self.coordinator.store.pending_outbox()
        for row in rows:
            payload = json.loads(row["payload"])
            participant_id = payload["participant_id"]
            item_id = row["work_item_id"]
            self.inbox.deliver(participant_id, item_id, self.clock.now)
            self.coordinator.store.mark_delivered(row["id"])

            def respond(item_id=item_id, participant_id=participant_id):
                if self.coordinator.store.item(item_id)["status"] == "skipped":
                    return
                attempt = self.coordinator.store.start_attempt(
                    item_id, lease_seconds=policy.lease_seconds
                )
                try:
                    opened = self.coordinator.open(item_id)
                    agent = self.agents[participant_id]
                    selected = self.answerer
                    if self.execution_plan is not None:
                        spec = self.execution_plan.resolve(agent.traits)
                        self.coordinator.store.record_executor(item_id, spec.kind, spec.options)
                        try:
                            selected = self.answerers[spec.kind]
                        except KeyError as exc:
                            raise ValueError(
                                f"no answerer configured for executor {spec.kind!r}"
                            ) from exc
                    answers = selected.answer(agent, opened)
                    self.coordinator.submit(
                        item_id,
                        answers,
                        idempotency_key=f"simulation:{item_id}",
                        attempt_id=attempt["id"],
                    )
                except Exception as exc:
                    kind = self._error_kind(exc)
                    self.coordinator.store.finish_attempt(
                        attempt["id"],
                        status="failed",
                        error_kind=kind,
                        error_message=str(exc)[:1000],
                    )
                    if (
                        kind in policy.retryable
                        and attempt["number"] < policy.max_attempts
                    ):
                        self.coordinator.store.retry_item(
                            item_id, reason=f"retryable {kind}"
                        )
                    else:
                        self.coordinator.store.fail_item(
                            item_id,
                            reason=f"{kind} after {attempt['number']} attempt(s)",
                        )

            self.clock.call_later(self.response_delay, respond)
        return bool(rows)

    @staticmethod
    def _error_kind(error: Exception) -> str:
        if isinstance(error, TimeoutError):
            return "timeout"
        identity = f"{type(error).__module__}.{type(error).__name__}".lower()
        if "remote" in identity or "coop" in identity:
            return "remote_error"
        return "exception"
