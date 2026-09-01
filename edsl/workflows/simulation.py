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
    ):
        self.coordinator = coordinator
        self.agents = dict(agents)
        self.answerer = answerer
        self.response_delay = response_delay
        self.clock = VirtualClock()
        self.inbox = SimulatedInbox()

    def run(self, instance_id: str) -> None:
        while True:
            delivered = self._deliver_pending()
            ran = self.clock.run_next()
            if not delivered and not ran:
                break
        remaining = [
            item
            for item in self.coordinator.store.items(instance_id)
            if item["status"] not in ("completed", "skipped")
        ]
        if remaining:
            blocked = [(item["step_name"], item["status"]) for item in remaining]
            raise RuntimeError(
                f"workflow reached quiescence with unfinished work: {blocked}"
            )

    def _deliver_pending(self) -> bool:
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
                opened = self.coordinator.open(item_id)
                answers = self.answerer.answer(self.agents[participant_id], opened)
                self.coordinator.submit(
                    item_id, answers, idempotency_key=f"simulation:{item_id}"
                )

            self.clock.call_later(self.response_delay, respond)
        return bool(rows)
