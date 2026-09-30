from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class InterviewSchedule:
    """Declarative ordering policy for interviews within one job."""

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


def validate_interview_schedule(job, schedule, n=1):
    """Validate scheduling consistently for local and service submissions."""
    if schedule == "serial":
        from .exceptions import JobsValueError

        if len(job.scenarios) != 1 or len(job.models) != 1:
            raise JobsValueError(
                "interview_schedule='serial' currently requires exactly one "
                "scenario and one model"
            )
        if n != 1:
            raise JobsValueError(
                "interview_schedule='serial' currently requires n=1; run "
                "each discussion round as a separate serial job"
            )
    elif isinstance(schedule, InterviewSchedule):
        from .exceptions import JobsValueError

        if schedule.kind not in {"grouped_round_robin", "rounds"}:
            raise JobsValueError(f"unknown interview schedule kind '{schedule.kind}'")
        if schedule.kind == "rounds":
            # Serialized schedules bypass the convenience constructor.
            if type(schedule.count) is not int or schedule.count < 1:
                raise JobsValueError("round count must be a positive integer")
            if schedule.within_round not in {"concurrent", "serial"}:
                raise JobsValueError("within_round must be 'concurrent' or 'serial'")
            if schedule.state_visibility not in {"snapshot", "live"}:
                raise JobsValueError("state_visibility must be 'snapshot' or 'live'")
            if schedule.round_order not in {"fixed", "rotate"}:
                raise JobsValueError("round_order must be 'fixed' or 'rotate'")
            if schedule.reveal not in {None, "live", "after_round"}:
                raise JobsValueError("invalid round reveal policy")
            if (schedule.reveal == "live" and schedule.state_visibility != "live") or (
                schedule.reveal == "after_round"
                and schedule.state_visibility != "snapshot"
            ):
                raise JobsValueError(
                    "round reveal policy conflicts with state_visibility"
                )
        if len(job.scenarios) != 1 or len(job.models) != 1:
            raise JobsValueError(
                "grouped_round_robin currently requires exactly one scenario "
                "and one model"
            )
        for condition in (schedule.stop_when, schedule.finalize_when):
            if condition is None:
                continue
            from ..sharedstate.model import StateCondition

            if not isinstance(condition, StateCondition):
                raise JobsValueError(
                    "schedule state conditions must come from "
                    "a scoped machine's is_complete() method"
                )
        if (
            schedule.kind == "rounds"
            and schedule.within_round == "concurrent"
            and schedule.state_visibility == "snapshot"
            and getattr(job.survey, "_state_before_writes", {})
        ):
            raise JobsValueError(
                "before-question state writes cannot be combined with "
                "concurrent snapshot rounds; use state_visibility='live' "
                "until pre-round write barriers are supported"
            )
        required_traits = (
            (schedule.group_by, schedule.order_by)
            if schedule.kind == "grouped_round_robin"
            else (schedule.group_by, schedule.order_by)
        )
        for agent in job.agents:
            missing = [
                key
                for key in required_traits
                if key is not None and key not in agent.traits
            ]
            if missing:
                raise JobsValueError(
                    f"agent '{agent.name}' is missing schedule traits {missing}"
                )
        if schedule.kind == "grouped_round_robin":
            seen_positions = set()
            for agent in job.agents:
                position = (
                    agent.traits[schedule.group_by],
                    agent.traits[schedule.order_by],
                )
                if position in seen_positions:
                    raise JobsValueError(
                        "grouped_round_robin requires unique order values within "
                        f"each group; duplicate position {position!r}"
                    )
                seen_positions.add(position)
    elif schedule != "concurrent":
        from .exceptions import JobsValueError

        raise JobsValueError(
            f"unknown interview_schedule {schedule!r}; expected 'concurrent', "
            "'serial', or an InterviewSchedule"
        )


def validate_distributed_interview_schedule(schedule, *, survey=None):
    """Admit only schedules whose coordination is implemented remotely."""
    if schedule in ("concurrent", "serial"):
        return
    if not isinstance(schedule, InterviewSchedule) or schedule.kind not in {
        "rounds",
        "grouped_round_robin",
    }:
        raise ValueError("unsupported distributed interview schedule")
    if (
        schedule.kind == "rounds"
        and schedule.within_round == "concurrent"
        and (schedule.stop_when is not None or schedule.finalize_when is not None)
        and getattr(survey, "_state_before_writes", {})
    ):
        raise ValueError(
            "concurrent stop/finalize requires answer-triggered state writes; "
            "before-question writes are not supported"
        )
