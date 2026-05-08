"""Pydantic models and handler for human survey notification delivery settings."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Annotated, List, Literal, Optional, Union
from uuid import UUID

CallbackType = Literal["human_survey_respondent.completed"]

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag, TypeAdapter

if TYPE_CHECKING:
    from .coop import Coop


# ---------------------------------------------------------------------------
# Delivery map (survey creation)
# ---------------------------------------------------------------------------


class ChannelConfig(BaseModel):
    """Trait column mapping for a delivery channel."""

    model_config = ConfigDict(extra="forbid")

    col_name: str


class DeliveryMap(BaseModel):
    """Mapping of delivery channels to their source trait keys."""

    model_config = ConfigDict(extra="forbid")

    email: Optional[ChannelConfig] = None


# ---------------------------------------------------------------------------
# Status enums (used in respondent filters)
# ---------------------------------------------------------------------------


class SendStatus(str, Enum):
    pending = "pending"
    sent = "sent"
    failed = "failed"


class DeliveryStatus(str, Enum):
    pending = "pending"
    delivered = "delivered"
    bounced = "bounced"
    failed = "failed"


class ResponseStatus(str, Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    completed = "completed"
    expired = "expired"


class FilterOperator(str, Enum):
    and_ = "and"
    or_ = "or"


# ---------------------------------------------------------------------------
# Respondent filter (who receives a delivery)
# ---------------------------------------------------------------------------


class RespondentCondition(BaseModel):
    """One clause in a respondent filter."""

    type: Literal["condition"] = "condition"
    respondent_uuids: Optional[List[str]] = None
    response_status: Optional[List[ResponseStatus]] = None
    never_contacted: Optional[bool] = None
    any_send_status: Optional[List[SendStatus]] = None
    any_delivery_status: Optional[List[DeliveryStatus]] = None
    most_recent_send_status: Optional[List[SendStatus]] = None
    most_recent_delivery_status: Optional[List[DeliveryStatus]] = None


class HumanizeRespondentFilter(BaseModel):
    """Filter that controls which respondents receive a delivery.

    ``conditions`` accepts both leaf ``RespondentCondition`` nodes and nested
    ``HumanizeRespondentFilter`` groups, allowing arbitrarily deep filter trees.
    """

    type: Literal["group"] = "group"
    operator: FilterOperator = FilterOperator.and_
    conditions: List["RespondentFilterNode"] = []


RespondentFilterNode = Annotated[
    Union[
        Annotated[HumanizeRespondentFilter, Tag("group")],
        Annotated[RespondentCondition, Tag("condition")],
    ],
    Field(discriminator="type"),
]

HumanizeRespondentFilter.model_rebuild()


# ---------------------------------------------------------------------------
# Route configs (what channel/subtype each delivery leg uses)
# ---------------------------------------------------------------------------


class RespondentEmailRouteConfig(BaseModel):
    """Email sent to each survey respondent."""

    channel: Literal["email"] = "email"
    subtype: Literal["respondent"] = "respondent"
    delivery_template: Optional[str] = None
    respondent_filter: Optional[HumanizeRespondentFilter] = None


class OwnerEmailRouteConfig(BaseModel):
    """Email sent to the survey owner."""

    channel: Literal["email"] = "email"
    subtype: Literal["owner"] = "owner"
    delivery_template: Optional[str] = None


class OwnerWebhookRouteConfig(BaseModel):
    """Webhook fired to a URL the owner controls."""

    channel: Literal["webhook"] = "webhook"
    subtype: Literal["owner"] = "owner"
    webhook_url: str
    threshold: Optional[int] = None


def _route_discriminator(v: "dict | object") -> str:
    if isinstance(v, dict):
        return f"{v.get('channel')}.{v.get('subtype')}"
    return f"{v.channel}.{v.subtype}"


RouteConfig = Annotated[
    Union[
        Annotated[RespondentEmailRouteConfig, Tag("email.respondent")],
        Annotated[OwnerEmailRouteConfig, Tag("email.owner")],
        Annotated[OwnerWebhookRouteConfig, Tag("webhook.owner")],
    ],
    Discriminator(_route_discriminator),
]


def serialize_routes(routes: List) -> list[dict]:
    """Serialize route configs to JSON-compatible dicts for Coop API requests.

    Each item may be a ``RouteConfig`` model instance or a dict matching the
    server's route schema.  Values are validated before serialization.
    """
    adapter = TypeAdapter(List[RouteConfig])
    validated = adapter.validate_python(routes)
    return [route.model_dump(mode="json") for route in validated]


# ---------------------------------------------------------------------------
# HumanSurveyNotificationHandler
# ---------------------------------------------------------------------------


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

    def send_respondent_email(
        self,
        name: str,
        delivery_template: Optional[str] = None,
        respondent_filter: Optional[HumanizeRespondentFilter] = None,
    ) -> dict:
        """Trigger a respondent email delivery job for this human survey.

        Builds a ``RespondentEmailRouteConfig`` from the supplied options and
        sends it immediately.  ``delivery_template`` and ``respondent_filter``
        are passed through to the route; omit them to use the server defaults.

        Returns:
            dict: ``{"delivery_uuid": "<uuid>", "routes": [...]}``
        """
        route = RespondentEmailRouteConfig(
            delivery_template=delivery_template,
            respondent_filter=respondent_filter,
        )
        return self._coop.create_human_survey_delivery(
            human_survey_uuid=self.human_survey_uuid,
            name=name,
            routes=[route],
        )

    # ------------------------------------------------------------------
    # One-time schedules
    # ------------------------------------------------------------------

    def create_one_time_schedule(
        self,
        name: str,
        run_at: Union[str, datetime],
        routes: Optional[List[RouteConfig]] = None,
    ) -> dict:
        """Create a one-time delivery schedule.

        ``run_at`` may be an ISO 8601 string or a timezone-aware ``datetime``.
        ``routes`` customises which channels are used; defaults to ``respondent_email``.
        """
        return self._coop.create_human_survey_one_time_schedule(
            human_survey_uuid=self.human_survey_uuid,
            name=name,
            run_at=run_at,
            routes=routes,
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
        routes: Optional[List[RouteConfig]] = None,
    ) -> dict:
        """Create a recurring delivery schedule.

        ``cron_expression`` uses standard cron syntax (e.g. ``"0 9 * * MON"``).
        ``timezone`` is an IANA timezone name.  Provide exactly one of
        ``max_jobs`` or ``deadline`` as the termination condition.
        ``routes`` customises which channels are used; defaults to ``respondent_email``.
        """
        return self._coop.create_human_survey_recurring_schedule(
            human_survey_uuid=self.human_survey_uuid,
            name=name,
            cron_expression=cron_expression,
            timezone=timezone,
            max_jobs=max_jobs,
            deadline=deadline,
            start_at=start_at,
            routes=routes,
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

    def activate_schedule(self, schedule_uuid: Union[str, UUID]) -> dict:
        """Activate a delivery schedule."""
        return self._coop.set_human_survey_schedule_active(
            human_survey_uuid=self.human_survey_uuid,
            schedule_uuid=schedule_uuid,
            is_active=True,
        )

    def deactivate_schedule(self, schedule_uuid: Union[str, UUID]) -> dict:
        """Deactivate a delivery schedule."""
        return self._coop.set_human_survey_schedule_active(
            human_survey_uuid=self.human_survey_uuid,
            schedule_uuid=schedule_uuid,
            is_active=False,
        )

    # ------------------------------------------------------------------
    # Route management
    # ------------------------------------------------------------------

    def patch_respondent_email_route(
        self,
        schedule_uuid: Union[str, UUID],
        route_uuid: Union[str, UUID],
        *,
        delivery_template: Optional[str] = None,
        respondent_filter: Optional[HumanizeRespondentFilter] = None,
    ) -> dict:
        """Update the template and/or respondent filter on a respondent route.

        Fields omitted are left unchanged on the server.
        """
        return self._coop.patch_human_survey_respondent_email_route(
            human_survey_uuid=self.human_survey_uuid,
            schedule_uuid=schedule_uuid,
            route_uuid=route_uuid,
            delivery_template=delivery_template,
            respondent_filter=respondent_filter,
        )

    def add_schedule_route(
        self,
        schedule_uuid: Union[str, UUID],
        route_config: RouteConfig,
    ) -> dict:
        """Add a new route to an existing schedule.

        Returns:
            dict: ``{"route_uuid": "<uuid>", "channel": "...", "subtype": "..."}``
        """
        return self._coop.add_human_survey_schedule_route(
            human_survey_uuid=self.human_survey_uuid,
            schedule_uuid=schedule_uuid,
            route_config=route_config,
        )

    def delete_schedule_route(
        self,
        schedule_uuid: Union[str, UUID],
        route_uuid: Union[str, UUID],
    ) -> dict:
        """Delete a route from a schedule.

        The schedule itself is not affected.

        Returns:
            dict: ``{"deleted": "<route_uuid>"}``
        """
        return self._coop.delete_human_survey_schedule_route(
            human_survey_uuid=self.human_survey_uuid,
            schedule_uuid=schedule_uuid,
            route_uuid=route_uuid,
        )

    # ------------------------------------------------------------------
    # Agent list
    # ------------------------------------------------------------------

    def get_agent_list(self) -> dict:
        """Get the agent list config for this human survey.

        Returns:
            dict: ``{"agent_list_config": {"uuid", "description", "delivery_map",
            "anonymous", "allow_resubmit"}}`` — ``agent_list_config`` is ``None``
            when no agent list has been attached.
        """
        return self._coop.get_human_survey_agent_list(
            human_survey_uuid=self.human_survey_uuid,
        )

    def patch_agent_list(
        self,
        *,
        delivery_map: Optional["DeliveryMap"] = None,
        anonymous: Optional[bool] = None,
        allow_resubmit: Optional[bool] = None,
    ) -> dict:
        """Update the agent list config for this human survey.

        Fields omitted are left unchanged on the server.

        Returns:
            dict: ``{"uuid", "description", "delivery_map", "anonymous",
            "allow_resubmit"}``
        """
        return self._coop.patch_human_survey_agent_list(
            human_survey_uuid=self.human_survey_uuid,
            delivery_map=delivery_map,
            anonymous=anonymous,
            allow_resubmit=allow_resubmit,
        )

    # ------------------------------------------------------------------
    # Respondents
    # ------------------------------------------------------------------

    def get_respondents(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """Get the paginated respondent list for this human survey.

        Returns:
            dict: ``{"respondents": [{"agent_index", "respondent_uuid", "url",
            "response_status"}, ...], "total", "page", "page_size",
            "total_pages"}``
        """
        return self._coop.get_human_survey_respondents(
            human_survey_uuid=self.human_survey_uuid,
            page=page,
            page_size=page_size,
        )

    # ------------------------------------------------------------------
    # Delivery status
    # ------------------------------------------------------------------

    def get_delivery(self, delivery_uuid: Union[str, UUID]) -> dict:
        """Fetch a delivery job by UUID.

        Returns:
            dict: ``{"delivery_uuid", "status", "total_respondents",
            "processed_respondents", "sent_count", "failed_count",
            "started_at", "completed_at"}``
        """
        return self._coop.get_human_survey_delivery(
            human_survey_uuid=self.human_survey_uuid,
            delivery_uuid=delivery_uuid,
        )

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def create_callback(
        self,
        name: str,
        callback_type: CallbackType,
        routes: Optional[List[RouteConfig]] = None,
        max_fires: Optional[int] = None,
    ) -> dict:
        """Create an event-triggered callback for this human survey.

        Only ``"human_survey_respondent.completed"`` is supported: fires once
        per respondent who completes the survey.  The survey must have an
        agent list with an email delivery channel configured.

        Returns:
            dict: ``{"callback_uuid", "name", "callback_type", "event_config",
            "is_active", "fired_count", "max_fires", "routes": [...]}``
        """
        return self._coop.create_human_survey_callback(
            human_survey_uuid=self.human_survey_uuid,
            name=name,
            callback_type=callback_type,
            routes=routes,
            max_fires=max_fires,
        )

    def get_callback(self, callback_uuid: Union[str, UUID]) -> dict:
        """Fetch a callback by UUID.

        Returns:
            dict: ``{"callback_uuid", "name", "callback_type", "event_config",
            "is_active", "fired_count", "max_fires"}``
        """
        return self._coop.get_human_survey_callback(
            human_survey_uuid=self.human_survey_uuid,
            callback_uuid=callback_uuid,
        )

    def activate_callback(self, callback_uuid: Union[str, UUID]) -> dict:
        """Activate a callback."""
        return self._coop.set_human_survey_callback_active(
            human_survey_uuid=self.human_survey_uuid,
            callback_uuid=callback_uuid,
            is_active=True,
        )

    def deactivate_callback(self, callback_uuid: Union[str, UUID]) -> dict:
        """Deactivate a callback."""
        return self._coop.set_human_survey_callback_active(
            human_survey_uuid=self.human_survey_uuid,
            callback_uuid=callback_uuid,
            is_active=False,
        )

    def delete_callback(self, callback_uuid: Union[str, UUID]) -> dict:
        """Delete a callback (and its routes).

        Returns:
            dict: ``{"deleted": "<callback_uuid>"}``
        """
        return self._coop.delete_human_survey_callback(
            human_survey_uuid=self.human_survey_uuid,
            callback_uuid=callback_uuid,
        )
