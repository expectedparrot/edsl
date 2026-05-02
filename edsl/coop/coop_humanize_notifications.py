"""Pydantic models for human survey notification delivery settings."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class ChannelConfig(BaseModel):
    """Trait column mapping for a delivery channel."""

    model_config = ConfigDict(extra="forbid")

    col_name: str


class DeliveryMap(BaseModel):
    """Mapping of delivery channels to their source trait keys."""

    model_config = ConfigDict(extra="forbid")

    email: Optional[ChannelConfig] = None
    ep_username: Optional[ChannelConfig] = None
    sms: Optional[ChannelConfig] = None


class ScheduleTerminationAfterNJobs(BaseModel):
    """End a recurring schedule after a fixed number of delivery jobs."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["after_n_jobs"] = "after_n_jobs"
    n: int


class ScheduleTerminationByDeadline(BaseModel):
    """End a recurring schedule at a wall-clock deadline."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["by_deadline"] = "by_deadline"
    deadline: datetime


ScheduleTermination = Annotated[
    Union[ScheduleTerminationAfterNJobs, ScheduleTerminationByDeadline],
    Field(discriminator="type"),
]

_schedule_termination_adapter = TypeAdapter(
    Union[ScheduleTerminationAfterNJobs, ScheduleTerminationByDeadline]
)


def parse_schedule_termination(
    termination: Union[
        Dict[str, Any],
        ScheduleTerminationAfterNJobs,
        ScheduleTerminationByDeadline,
    ],
) -> Union[ScheduleTerminationAfterNJobs, ScheduleTerminationByDeadline]:
    """Validate and normalize a recurring schedule termination (dict or model)."""
    return _schedule_termination_adapter.validate_python(termination)
