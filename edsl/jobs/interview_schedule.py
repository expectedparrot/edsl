from dataclasses import dataclass


@dataclass(frozen=True)
class GroupStopCondition:
    """Serializable reference to a shared primitive's terminal predicate."""

    target: str
    predicate: str


@dataclass(frozen=True)
class InterviewSchedule:
    """Declarative ordering policy for interviews within one local job."""

    kind: str
    group_by: str | None = None
    order_by: str | None = None
    stop_when: GroupStopCondition | None = None
    count: int | None = None
    within_round: str | None = None
    state_visibility: str | None = None
    round_order: str | None = None
    reveal: str | None = None
    finalize_when: GroupStopCondition | None = None

    @classmethod
    def grouped_round_robin(
        cls,
        group_by: str,
        order_by: str,
        stop_when: GroupStopCondition | None = None,
        finalize_when: GroupStopCondition | None = None,
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
        stop_when: GroupStopCondition | None = None,
        reveal: str | None = None,
        finalize_when: GroupStopCondition | None = None,
    ) -> "InterviewSchedule":
        if count < 1:
            raise ValueError("round count must be at least one")
        if within_round not in {"concurrent", "serial"}:
            raise ValueError("within_round must be 'concurrent' or 'serial'")
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
