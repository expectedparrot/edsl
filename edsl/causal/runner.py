"""Execute compiled causal replications through a durable conversation runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from edsl.conversations import Conversation, ConversationRuntime, SQLiteConversationStore

from .compiler import CompiledExperiment, CompiledReplication, MeasurementManifest, ParticipantAssignment


@dataclass(frozen=True)
class ConversationTurnRequest:
    instance_id: str
    role: str
    participant: ParticipantAssignment
    scenario: str
    public_context: Mapping[str, Any]
    private_context: Mapping[str, Any]
    transcript: tuple[Mapping[str, Any], ...]
    turn_instruction: str = ""
    private_values: Mapping[str, Any] | None = None
    turn_contract: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class MeasurementRequest:
    instance_id: str
    manifest: MeasurementManifest
    participant: ParticipantAssignment
    transcript: tuple[Mapping[str, Any], ...]
    public_context: Mapping[str, Any]


@dataclass(frozen=True)
class CausalObservation:
    instance_id: str
    cell_id: str
    replication: int
    values: Mapping[str, Any]
    transcript_version: int

    def to_dict(self) -> dict[str, Any]:
        return {"instance_id": self.instance_id, "cell_id": self.cell_id, "replication": self.replication, "values": dict(self.values), "transcript_version": self.transcript_version}


Speaker = Callable[[ConversationTurnRequest], str]
Judge = Callable[[Conversation, Sequence[Mapping], str], bool]
Measurer = Callable[[MeasurementRequest], Any]


class CausalExperimentRunner:
    def __init__(self, compiled: CompiledExperiment, conversation: Conversation, store: SQLiteConversationStore, *, speakers: Mapping[str, Speaker], semantic_judge: Judge, measurers: Mapping[str, Measurer]):
        self.compiled = compiled
        self.conversation = conversation
        self.store = store
        self.speakers = dict(speakers)
        self.semantic_judge = semantic_judge
        self.measurers = dict(measurers)
        missing_speakers = set(conversation.roles) - set(self.speakers)
        missing_measurers = {item.variable for item in compiled.measurements} - set(self.measurers)
        if missing_speakers or missing_measurers:
            raise ValueError(f"runner is missing speakers {sorted(missing_speakers)} or measurers {sorted(missing_measurers)}")

    def run(self, replication: CompiledReplication) -> CausalObservation:
        runtime = ConversationRuntime(self.conversation, self.store)
        participants = {
            item.role: item.participant_id
            for item in replication.participants
            if item.role in self.conversation.roles
        }
        try:
            state = self.store.state(replication.instance_id)
        except KeyError:
            runtime.launch(participants, instance_id=replication.instance_id)
            state = self.store.state(replication.instance_id)
        by_role = {item.role: item for item in replication.participants}
        while state["status"] == "running":
            transcript = self.store.transcript(replication.instance_id)
            if transcript and runtime.should_stop(replication.instance_id, self.semantic_judge):
                break
            role = runtime.next_role(replication.instance_id)
            participant = by_role[role]
            instruction_parts = [
                self.conversation.turn_instructions.get("*", ""),
                self.conversation.turn_instructions.get(role, ""),
            ]
            recipient = runtime.next_recipient(replication.instance_id) if role == self.conversation.protocol.options.get("center") else None
            if recipient:
                instruction_parts.append(f"The next eligible participant is {recipient}; address that role, not a retired role.")
            private_values = {name: replication.system_context[name] for name in participant.private_context}
            request = ConversationTurnRequest(replication.instance_id, role, participant, self.conversation.scenario, replication.public_context, participant.private_context, tuple(transcript), "\n".join(item for item in instruction_parts if item), private_values, self.conversation.turn_contracts.get(role))
            text = self.speakers[role](request)
            runtime.append(replication.instance_id, role=role, text=text, expected_version=state["version"], metadata={"executor": "callback"})
            state = self.store.state(replication.instance_id)
        transcript = tuple(self.store.transcript(replication.instance_id))
        values = dict(replication.system_context)
        for manifest in self.compiled.measurements:
            participant = by_role[manifest.respondent_role]
            request = MeasurementRequest(replication.instance_id, manifest, participant, transcript, replication.public_context)
            values[manifest.variable] = self.measurers[manifest.variable](request)
        return CausalObservation(replication.instance_id, replication.cell_id, replication.replication, values, self.store.state(replication.instance_id)["version"])
