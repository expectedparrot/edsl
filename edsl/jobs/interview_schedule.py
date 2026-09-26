from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class InterviewSchedule:
    """Declarative ordering policy for interviews within one local job."""

    kind: str
    group_by: str | None = None
    order_by: str | None = None
    stop_when: Any | None = None
    count: int | None = None
    within_round: str | None = None
    state_visibility: str | None = None
    round_order: str | None = None
    reveal: str | None = None
    finalize_when: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize every behavior-bearing part of the schedule."""
        return {
            "type": "interview_schedule",
            "version": 1,
            "kind": self.kind,
            "group_by": self.group_by,
            "order_by": self.order_by,
            "stop_when": self._condition_to_dict(self.stop_when),
            "count": self.count,
            "within_round": self.within_round,
            "state_visibility": self.state_visibility,
            "round_order": self.round_order,
            "reveal": self.reveal,
            "finalize_when": self._condition_to_dict(self.finalize_when),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "InterviewSchedule":
        if data.get("type") != "interview_schedule" or data.get("version") != 1:
            raise ValueError("unsupported interview schedule format")
        return cls(
            kind=data["kind"],
            group_by=data.get("group_by"),
            order_by=data.get("order_by"),
            stop_when=cls._condition_from_dict(data.get("stop_when")),
            count=data.get("count"),
            within_round=data.get("within_round"),
            state_visibility=data.get("state_visibility"),
            round_order=data.get("round_order"),
            reveal=data.get("reveal"),
            finalize_when=cls._condition_from_dict(data.get("finalize_when")),
        )

    @staticmethod
    def _condition_to_dict(value: Any | None) -> dict[str, Any] | None:
        if value is None:
            return None
        from ..sharedstate import StateCondition

        if not isinstance(value, StateCondition):
            raise TypeError(
                "schedule conditions must be serializable StateCondition objects"
            )
        return value.to_dict()

    @staticmethod
    def _condition_from_dict(value: Mapping[str, Any] | None) -> Any | None:
        if value is None:
            return None
        from ..sharedstate import StateCondition

        return StateCondition.from_dict(value)

    @classmethod
    def grouped_round_robin(
        cls,
        group_by: str,
        order_by: str,
        stop_when: Any | None = None,
        finalize_when: Any | None = None,
    ) -> "InterviewSchedule":
        return cls(
            kind="grouped_round_robin",
            group_by=group_by,
            order_by=order_by,
            stop_when=stop_when,
            finalize_when=finalize_when,
        )

    @classmethod
    def rounds(
        cls,
        count: int,
        group_by: str | None = None,
        within_round: str = "concurrent",
        state_visibility: str = "snapshot",
        order_by: str | None = None,
        round_order: str = "fixed",
        stop_when: Any | None = None,
        reveal: str | None = None,
        finalize_when: Any | None = None,
    ) -> "InterviewSchedule":
        if count < 1:
            raise ValueError("round count must be at least one")
        if within_round == "sequential":
            within_round = "serial"
        if within_round not in {"concurrent", "serial"}:
            raise ValueError(
                "within_round must be 'concurrent', 'serial', or 'sequential'"
            )
        if state_visibility not in {"snapshot", "live"}:
            raise ValueError("state_visibility must be 'snapshot' or 'live'")
        if round_order not in {"fixed", "rotate"}:
            raise ValueError("round_order must be 'fixed' or 'rotate'")
        if reveal not in {None, "live", "after_round"}:
            raise ValueError("reveal must be 'live', 'after_round', or None")
        if reveal == "after_round":
            state_visibility = "snapshot"
        elif reveal == "live":
            state_visibility = "live"
        return cls(
            kind="rounds",
            group_by=group_by,
            order_by=order_by,
            count=count,
            within_round=within_round,
            state_visibility=state_visibility,
            round_order=round_order,
            stop_when=stop_when,
            reveal=reveal,
            finalize_when=finalize_when,
        )
