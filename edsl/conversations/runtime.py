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
        retired = self._retired_roles(transcript)
        roles = [role for role in self.definition.roles if role not in retired]
        previous = transcript[-1]["role"] if transcript else None
        protocol = self.definition.protocol
        n = len(transcript)
        if protocol.kind == "ordered":
            order = [role for role in protocol.options["order"] if role not in retired]
            if not order:
                raise ValueError("conversation has no eligible next speaker")
            if previous in order:
                return order[(order.index(previous) + 1) % len(order)]
            original = list(protocol.options["order"])
            previous_index = original.index(previous) if previous in original else -1
            return next((original[(previous_index + offset) % len(original)] for offset in range(1, len(original) + 1) if original[(previous_index + offset) % len(original)] in order), order[0])
        if protocol.kind == "random":
            eligible = [role for role in roles if not protocol.options.get("no_immediate_repeat") or role != previous]
            return self._stable_choice(instance_id, state["version"], protocol.options["seed"], eligible)
        if protocol.kind in {"central_ordered", "central_random"}:
            if previous is None or previous != protocol.options["center"]:
                return protocol.options["center"]
            others = [role for role in protocol.options["others"] if role not in retired]
            if not others:
                return protocol.options["center"]
            if protocol.kind == "central_ordered":
                spoken_others = [item["role"] for item in transcript if item["role"] in protocol.options["others"]]
                last_other = spoken_others[-1] if spoken_others else None
                original = list(protocol.options["others"])
                start = original.index(last_other) if last_other in original else -1
                return next(original[(start + offset) % len(original)] for offset in range(1, len(original) + 1) if original[(start + offset) % len(original)] in others)
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

    def next_recipient(self, instance_id: str) -> str | None:
        """Return the participant a central speaker should address next."""
        protocol = self.definition.protocol
        if protocol.kind not in {"central_ordered", "central_random"}:
            return None
        transcript = self.store.transcript(instance_id)
        retired = self._retired_roles(transcript)
        others = [role for role in protocol.options["others"] if role not in retired]
        if not others:
            return None
        if protocol.kind == "central_random":
            state = self.store.state(instance_id)
            return self._stable_choice(instance_id, state["version"] + 1, protocol.options["seed"], others)
        spoken_others = [item["role"] for item in transcript if item["role"] in protocol.options["others"]]
        last_other = spoken_others[-1] if spoken_others else None
        original = list(protocol.options["others"])
        start = original.index(last_other) if last_other in original else -1
        return next(original[(start + offset) % len(original)] for offset in range(1, len(original) + 1) if original[(start + offset) % len(original)] in others)

    def _retired_roles(self, transcript: Sequence[Mapping]) -> set[str]:
        retired = set()
        for item in transcript:
            phrases = self.definition.retire_on.get(item["role"], ())
            normalized = str(item["text"]).strip().lower().rstrip(".! ")
            if normalized in {str(value).strip().lower().rstrip(".! ") for value in phrases}:
                retired.add(item["role"])
        return retired

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
