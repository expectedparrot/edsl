"""Delivery boundary between workflow orchestration and Humanize/email systems."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import TYPE_CHECKING, Any, Mapping, Protocol

from edsl.agents import Agent, AgentList

if TYPE_CHECKING:
    from edsl.coop import Coop

    from .coordinator import WorkflowCoordinator

from .store import SQLiteWorkflowStore
from .execution import ExecutionPlan


@dataclass(frozen=True)
class DeliveryRequest:
    idempotency_key: str
    instance_id: str
    work_item_id: str
    step_name: str
    participant_id: str


@dataclass(frozen=True)
class DeliveryReceipt:
    external_id: str


class DeliveryAdapter(Protocol):
    """Thin port implemented by Humanize, email, SMS, or a test inbox."""

    def deliver(self, request: DeliveryRequest) -> DeliveryReceipt: ...


class OutboxDispatcher:
    """Reliably dispatch ready work using adapter-level idempotency."""

    def __init__(self, store: SQLiteWorkflowStore, adapter: DeliveryAdapter):
        self.store = store
        self.adapter = adapter

    def dispatch(self) -> list[DeliveryReceipt]:
        receipts: list[DeliveryReceipt] = []
        for row in self.store.pending_outbox():
            payload: Mapping[str, str] = json.loads(row["payload"])
            receipt = self.adapter.deliver(
                DeliveryRequest(
                    idempotency_key=row["id"],
                    instance_id=payload["instance_id"],
                    work_item_id=row["work_item_id"],
                    step_name=payload["step_name"],
                    participant_id=payload["participant_id"],
                )
            )
            self.store.mark_delivered(row["id"])
            receipts.append(receipt)
        return receipts


class RoutedOutboxDispatcher:
    """Dispatch each pending item through its execution-plan adapter."""

    def __init__(self, store: SQLiteWorkflowStore, plan: ExecutionPlan, adapters: Mapping[str, DeliveryAdapter]):
        self.store, self.plan, self.adapters = store, plan, dict(adapters)

    def dispatch(self) -> list[DeliveryReceipt]:
        receipts = []
        for row in self.store.pending_outbox():
            payload = json.loads(row["payload"])
            agent = self.store.participant(payload["instance_id"], payload["participant_id"])
            spec = self.plan.resolve(agent.get("traits", {}))
            if spec.kind not in self.adapters:
                raise ValueError(f"no delivery adapter configured for executor {spec.kind!r}")
            self.store.record_executor(row["work_item_id"], spec.kind, spec.options)
            request = DeliveryRequest(row["id"], payload["instance_id"], row["work_item_id"], payload["step_name"], payload["participant_id"])
            receipts.append(self.adapters[spec.kind].deliver(request))
            self.store.mark_delivered(row["id"])
        return receipts


class HumanizeDeliveryAdapter:
    """Create one private Humanize survey for each ready workflow item.

    Humanize remains responsible only for rendering, email delivery, and response
    collection. ``poll_completed`` brings responses back into the workflow
    coordinator, which decides what becomes ready next.
    """

    provider = "humanize"

    def __init__(
        self,
        coordinator: "WorkflowCoordinator",
        coop: "Coop | None" = None,
        *,
        subject_prefix: str = "Weekend activity",
    ):
        if coop is None:
            from edsl.coop import Coop

            coop = Coop()
        self.coordinator = coordinator
        self.coop = coop
        self.subject_prefix = subject_prefix

    def deliver(self, request: DeliveryRequest) -> DeliveryReceipt:
        existing = [
            row
            for row in self.coordinator.store.external_tasks(self.provider)
            if row["work_item_id"] == request.work_item_id
        ]
        if existing:
            return DeliveryReceipt(external_id=existing[0]["resource_id"])

        opened = self.coordinator.open(request.work_item_id)
        agent_data = self.coordinator.store.participant(
            request.instance_id, request.participant_id
        )
        agent = Agent.from_dict(agent_data)
        details = self.coop.create_human_survey(
            survey=opened.survey,
            human_survey_name=f"{self.subject_prefix}: {request.step_name}",
            survey_visibility="private",
            agent_list=AgentList([agent]),
            agent_list_visibility="private",
            delivery_map={"email": {"col_name": "email"}},
        )
        human_survey_uuid = str(details["uuid"])
        delivery = self.coop.create_human_survey_delivery(
            human_survey_uuid,
            name=f"Workflow invitation: {request.step_name}",
        )
        delivery_uuid = delivery.get("delivery_uuid")
        self.coordinator.store.record_external_task(
            provider=self.provider,
            work_item_id=request.work_item_id,
            resource_id=human_survey_uuid,
            delivery_id=str(delivery_uuid) if delivery_uuid else None,
        )
        return DeliveryReceipt(external_id=human_survey_uuid)

    def poll_completed(self) -> int:
        completed = 0
        for external in self.coordinator.store.external_tasks(self.provider):
            details = self.coop.get_human_survey(external["resource_id"])
            if not details.get("n_responses"):
                continue
            responses = self.coop.get_human_survey_responses(external["resource_id"])
            answers = self._answers(responses)
            self.coordinator.submit(
                external["work_item_id"],
                answers,
                idempotency_key=f"humanize:{external['resource_id']}",
            )
            self.coordinator.store.complete_external_task(
                self.provider, external["work_item_id"]
            )
            completed += 1
        return completed

    @staticmethod
    def _answers(responses: Any) -> Mapping[str, Any]:
        if len(responses) != 1:
            raise RuntimeError(
                f"expected exactly one Humanize response, found {len(responses)}"
            )
        row = responses[0]
        if hasattr(row, "answer"):
            return dict(row.answer)
        if hasattr(row, "data"):
            return dict(row.data)
        if isinstance(row, Mapping):
            return dict(row)
        raise RuntimeError("Humanize response has an unsupported result shape")
