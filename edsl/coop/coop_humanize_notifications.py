"""Pydantic models for human survey notification delivery settings."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


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
