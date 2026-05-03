"""Pydantic models and handler for human survey notification delivery settings."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from .coop import Coop


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


class HumanSurveyNotificationHandler:
    """Convenience wrapper for human survey notification and delivery methods.

    Binds a ``human_survey_uuid`` so callers don't have to pass it to every
    method.  Instantiates a ``Coop`` client automatically when one is not
    provided.

    Parameters
    ----------
    human_survey_uuid:
        UUID (or UUID string) of the human survey to manage.
    coop:
        Optional pre-configured ``Coop`` instance.  A default instance is
        created when omitted.
    """

    def __init__(
        self,
        human_survey_uuid: Union[str, UUID],
        coop: Optional[Coop] = None,
    ) -> None:
        self.human_survey_uuid = str(human_survey_uuid)
        if coop is None:
            from .coop import Coop as _Coop

            coop = _Coop()
        self._coop = coop

    # ------------------------------------------------------------------
    # Immediate delivery
    # ------------------------------------------------------------------

    def trigger_delivery(self, name: str) -> dict:
        """Trigger a new email delivery job for this human survey's agent list.

        Returns:
            dict: ``{"delivery_uuid": "<uuid>"}``
        """
        return self._coop.create_human_survey_delivery(
            human_survey_uuid=self.human_survey_uuid,
            name=name,
        )

    # ------------------------------------------------------------------
    # One-time schedules
    # ------------------------------------------------------------------

    def create_one_time_schedule(
        self,
        name: str,
        run_at: Union[str, datetime],
    ) -> dict:
        """Create a one-time delivery schedule.

        ``run_at`` may be an ISO 8601 string or a timezone-aware ``datetime``.
        """
        return self._coop.create_human_survey_one_time_schedule(
            human_survey_uuid=self.human_survey_uuid,
            name=name,
            run_at=run_at,
        )

    def update_one_time_schedule(
        self,
        schedule_uuid: Union[str, UUID],
        run_at: Union[str, datetime],
    ) -> dict:
        """Update the ``run_at`` time of a one-time delivery schedule."""
        return self._coop.update_human_survey_one_time_schedule(
            human_survey_uuid=self.human_survey_uuid,
            schedule_uuid=schedule_uuid,
            run_at=run_at,
        )

    # ------------------------------------------------------------------
    # Recurring schedules
    # ------------------------------------------------------------------

    def create_recurring_schedule(
        self,
        name: str,
        cron_expression: str,
        timezone: str,
        *,
        max_jobs: Optional[int] = None,
        deadline: Optional[datetime] = None,
        start_at: Optional[Union[str, datetime]] = None,
    ) -> dict:
        """Create a recurring delivery schedule.

        ``cron_expression`` uses standard cron syntax (e.g. ``"0 9 * * MON"``).
        ``timezone`` is an IANA timezone name.  Provide exactly one of
        ``max_jobs`` or ``deadline`` as the termination condition.
        """
        return self._coop.create_human_survey_recurring_schedule(
            human_survey_uuid=self.human_survey_uuid,
            name=name,
            cron_expression=cron_expression,
            timezone=timezone,
            max_jobs=max_jobs,
            deadline=deadline,
            start_at=start_at,
        )

    def update_recurring_schedule(
        self,
        schedule_uuid: Union[str, UUID],
        *,
        cron_expression: Optional[str] = None,
        timezone: Optional[str] = None,
        max_jobs: Optional[int] = None,
        deadline: Optional[datetime] = None,
        start_at: Optional[Union[str, datetime]] = None,
    ) -> dict:
        """Update a recurring delivery schedule.

        At most one of ``max_jobs`` or ``deadline`` may be set per call; omit
        both to leave the termination condition unchanged.
        """
        return self._coop.update_human_survey_recurring_schedule(
            human_survey_uuid=self.human_survey_uuid,
            schedule_uuid=schedule_uuid,
            cron_expression=cron_expression,
            timezone=timezone,
            max_jobs=max_jobs,
            deadline=deadline,
            start_at=start_at,
        )

    # ------------------------------------------------------------------
    # Schedule management
    # ------------------------------------------------------------------

    def get_schedule(self, schedule_uuid: Union[str, UUID]) -> dict:
        """Fetch a delivery schedule by UUID."""
        return self._coop.get_human_survey_schedule(
            human_survey_uuid=self.human_survey_uuid,
            schedule_uuid=schedule_uuid,
        )

    def set_schedule_active(
        self,
        schedule_uuid: Union[str, UUID],
        is_active: bool,
    ) -> dict:
        """Activate or deactivate a delivery schedule."""
        return self._coop.set_human_survey_schedule_active(
            human_survey_uuid=self.human_survey_uuid,
            schedule_uuid=schedule_uuid,
            is_active=is_active,
        )
