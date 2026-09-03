"""Serializable definitions for multi-agent conversations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class ConversationProtocol:
    kind: str
    options: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "options": dict(self.options)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ConversationProtocol":
        kind = str(data["kind"])
        if kind not in {"ordered", "random", "central_ordered", "central_random", "coordinator_before", "coordinator_after"}:
            raise ValueError(f"unsupported conversation protocol {kind!r}")
        return cls(kind, dict(data.get("options", {})))


def OrderedTurns(order: Sequence[str]) -> ConversationProtocol:
    if not order or len(set(order)) != len(order):
        raise ValueError("ordered turns require a nonempty unique role order")
    return ConversationProtocol("ordered", {"order": list(order)})


def RandomTurns(*, seed: str, no_immediate_repeat: bool = True) -> ConversationProtocol:
    if not seed:
        raise ValueError("random-turn seed must be non-empty")
    return ConversationProtocol("random", {"seed": seed, "no_immediate_repeat": no_immediate_repeat})


def CentralOrdered(*, center: str, others: Sequence[str]) -> ConversationProtocol:
    if not center or not others or center in others or len(set(others)) != len(others):
        raise ValueError("central ordered turns require one center and unique other roles")
    return ConversationProtocol("central_ordered", {"center": center, "others": list(others)})


def CentralRandom(*, center: str, others: Sequence[str], seed: str) -> ConversationProtocol:
    protocol = CentralOrdered(center=center, others=others)
    return ConversationProtocol("central_random", {**protocol.options, "seed": seed})


def CoordinatorBefore(*, coordinator: str, no_immediate_repeat: bool = True) -> ConversationProtocol:
    return ConversationProtocol("coordinator_before", {"coordinator": coordinator, "no_immediate_repeat": no_immediate_repeat})


def CoordinatorAfter(*, coordinator: str) -> ConversationProtocol:
    return ConversationProtocol("coordinator_after", {"coordinator": coordinator})


@dataclass(frozen=True)
class StopRule:
    kind: str
    options: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "options": dict(self.options)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StopRule":
        kind = str(data["kind"])
        options = dict(data.get("options", {}))
        if kind == "any":
            options["rules"] = [cls.from_dict(item) for item in options.get("rules", ())]
        if kind not in {"max_utterances", "semantic", "any"}:
            raise ValueError(f"unsupported conversation stop rule {kind!r}")
        return cls(kind, options)


def MaxUtterances(count: int) -> StopRule:
    if count < 1:
        raise ValueError("maximum utterances must be positive")
    return StopRule("max_utterances", {"count": count})


def SemanticStop(*, judge: str, question: str) -> StopRule:
    if not judge or not question:
        raise ValueError("semantic stop requires a judge and question")
    return StopRule("semantic", {"judge": judge, "question": question})


def AnyStop(*rules: StopRule) -> StopRule:
    if not rules:
        raise ValueError("AnyStop requires at least one rule")
    return StopRule("any", {"rules": list(rules)})


def _encode_stop(rule: StopRule) -> dict[str, Any]:
    data = rule.to_dict()
    if rule.kind == "any":
        data["options"]["rules"] = [_encode_stop(item) for item in rule.options["rules"]]
    return data


@dataclass(frozen=True)
class Conversation:
    name: str
    roles: tuple[str, ...]
    scenario: str
    protocol: ConversationProtocol
    stop: StopRule
    transcript_visibility: str = "public"
    include_remaining_turns: bool = True

    def __init__(self, name: str, roles: Sequence[str], scenario: str, protocol: ConversationProtocol, stop: StopRule, *, transcript_visibility: str = "public", include_remaining_turns: bool = True):
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "roles", tuple(roles))
        object.__setattr__(self, "scenario", scenario)
        object.__setattr__(self, "protocol", protocol)
        object.__setattr__(self, "stop", stop)
        object.__setattr__(self, "transcript_visibility", transcript_visibility)
        object.__setattr__(self, "include_remaining_turns", include_remaining_turns)
        if not name or not scenario or not self.roles or len(set(self.roles)) != len(self.roles):
            raise ValueError("conversation requires a name, scenario, and unique roles")
        referenced = set(protocol.options.get("order", ())) | set(protocol.options.get("others", ()))
        center = protocol.options.get("center")
        if center:
            referenced.add(center)
        if referenced and referenced != set(self.roles):
            raise ValueError("conversation protocol roles must exactly match conversation roles")
        if transcript_visibility not in {"public", "role_filtered"}:
            raise ValueError("unsupported transcript visibility")

    def to_dict(self) -> dict[str, Any]:
        return {"type": "conversation", "name": self.name, "roles": list(self.roles), "scenario": self.scenario, "protocol": self.protocol.to_dict(), "stop": _encode_stop(self.stop), "transcript_visibility": self.transcript_visibility, "include_remaining_turns": self.include_remaining_turns}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Conversation":
        if data.get("type") != "conversation":
            raise ValueError("not a conversation")
        return cls(data["name"], data["roles"], data["scenario"], ConversationProtocol.from_dict(data["protocol"]), StopRule.from_dict(data["stop"]), transcript_visibility=data.get("transcript_visibility", "public"), include_remaining_turns=bool(data.get("include_remaining_turns", True)))
