"""Protocol selection and stopping over durable conversation transcripts."""

from __future__ import annotations

import hashlib
from typing import Callable, Mapping, Sequence

from .definition import Conversation, StopRule
from .store import SQLiteConversationStore


Coordinator = Callable[[Conversation, Sequence[Mapping], Sequence[str]], str]
SemanticJudge = Callable[[Conversation, Sequence[Mapping], str], bool]


class ConversationRuntime:
    def __init__(self, definition: Conversation, store: SQLiteConversationStore):
        self.definition = definition
        self.store = store

    def launch(self, participants: Mapping[str, str], *, instance_id: str) -> str:
        if set(participants) != set(self.definition.roles):
            raise ValueError("conversation participants must provide exactly one participant per role")
        self.store.create(instance_id, self.definition.to_dict(), participants)
        return instance_id

    def next_role(self, instance_id: str, coordinator: Coordinator | None = None) -> str:
        state = self.store.state(instance_id)
        transcript = self.store.transcript(instance_id)
        roles = list(self.definition.roles)
        previous = transcript[-1]["role"] if transcript else None
        protocol = self.definition.protocol
        n = len(transcript)
        if protocol.kind == "ordered":
            return protocol.options["order"][n % len(roles)]
        if protocol.kind == "random":
            eligible = [role for role in roles if not protocol.options.get("no_immediate_repeat") or role != previous]
            return self._stable_choice(instance_id, state["version"], protocol.options["seed"], eligible)
        if protocol.kind in {"central_ordered", "central_random"}:
            if n % 2 == 0:
                return protocol.options["center"]
            others = list(protocol.options["others"])
            if protocol.kind == "central_ordered":
                return others[(n // 2) % len(others)]
            return self._stable_choice(instance_id, state["version"], protocol.options["seed"], others)
        if protocol.kind == "coordinator_before":
            if coordinator is None:
                raise ValueError("coordinator-before protocol requires a coordinator callback")
            eligible = [role for role in roles if not protocol.options.get("no_immediate_repeat") or role != previous]
            selected = coordinator(self.definition, transcript, eligible)
            if selected not in eligible:
                raise ValueError("conversation coordinator selected an ineligible role")
            return selected
        if protocol.kind == "coordinator_after":
            raise ValueError("coordinator-after chooses among candidate responses, not a next role")
        raise ValueError(f"unsupported conversation protocol {protocol.kind!r}")

    @staticmethod
    def _stable_choice(instance_id: str, version: int, seed: str, eligible: Sequence[str]) -> str:
        if not eligible:
            raise ValueError("conversation has no eligible next speaker")
        digest = hashlib.sha256(f"{instance_id}:{version}:{seed}".encode()).digest()
        return eligible[int.from_bytes(digest, "big") % len(eligible)]

    def append(self, instance_id: str, *, role: str, text: str, expected_version: int, coordinator: Coordinator | None = None, metadata: Mapping | None = None) -> str:
        expected_role = self.next_role(instance_id, coordinator)
        if role != expected_role:
            raise ValueError(f"expected role {expected_role!r}, received {role!r}")
        participant = self.store.state(instance_id)["participants"][role]
        return self.store.append(instance_id, expected_version=expected_version, role=role, participant_id=participant, text=text, metadata=metadata)

    def realize_candidates(self, instance_id: str, candidates: Sequence[Mapping], *, expected_version: int, coordinator: Coordinator) -> str:
        if self.definition.protocol.kind != "coordinator_after":
            raise ValueError("candidate realization requires coordinator-after protocol")
        state = self.store.state(instance_id)
        participants = state["participants"]
        transcript = self.store.transcript(instance_id)
        previous = transcript[-1]["role"] if transcript else None
        eligible = [role for role in self.definition.roles if role != previous]
        by_role = {item["role"]: item for item in candidates}
        if set(by_role) != set(eligible) or any(item["participant_id"] != participants[item["role"]] for item in candidates):
            raise ValueError("coordinator-after requires exactly one valid candidate per eligible role")
        ids = self.store.record_candidates(instance_id, expected_version + 1, candidates)
        selected_role = coordinator(self.definition, transcript, eligible)
        if selected_role not in eligible:
            raise ValueError("conversation coordinator selected an ineligible candidate")
        selected_id = ids[[item["role"] for item in candidates].index(selected_role)]
        return self.store.select_candidate(instance_id, selected_id, expected_version=expected_version)

    def should_stop(self, instance_id: str, semantic_judge: SemanticJudge | None = None) -> bool:
        transcript = self.store.transcript(instance_id)
        def evaluate(rule: StopRule) -> bool:
            if rule.kind == "max_utterances":
                return len(transcript) >= int(rule.options["count"])
            if rule.kind == "semantic":
                if semantic_judge is None:
                    raise ValueError("semantic stop rule requires a judge callback")
                return bool(semantic_judge(self.definition, transcript, rule.options["question"]))
            if rule.kind == "any":
                return any(evaluate(item) for item in rule.options["rules"])
            raise ValueError(f"unsupported stop rule {rule.kind!r}")
        stopped = evaluate(self.definition.stop)
        if stopped:
            self.store.complete(instance_id)
        return stopped
