"""Helpers for the humanize CLI commands."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional


def read_optional_text(path: Optional[str]) -> Optional[str]:
    if path is None:
        return None
    return Path(path).read_text(encoding="utf-8")


def build_routes_input(
    routes_path: Optional[str],
    owner_email_template: Optional[str],
    respondent_email_template: Optional[str],
    template_file: Optional[str],
    respondent_filter_path: Optional[str],
    subject: Optional[str],
    *,
    read_json: Callable[[str], object],
    usage_error: Callable[[str], None],
) -> Optional[list[dict]]:
    if routes_path:
        if any([owner_email_template, respondent_email_template, template_file, respondent_filter_path, subject]):
            usage_error("--routes cannot be combined with route helper options.")
        routes = read_json(routes_path)
        if isinstance(routes, list):
            return routes
        if isinstance(routes, dict):
            return [routes]
        usage_error("Routes JSON must be a route object or a list of route objects.")

    route = build_route_input(
        None,
        owner_email_template,
        respondent_email_template,
        template_file,
        respondent_filter_path,
        subject,
        read_json=read_json,
        usage_error=usage_error,
        required=False,
    )
    return [route] if route is not None else None


def build_route_input(
    route_path: Optional[str],
    owner_email_template: Optional[str],
    respondent_email_template: Optional[str],
    template_file: Optional[str],
    respondent_filter_path: Optional[str],
    subject: Optional[str],
    *,
    read_json: Callable[[str], object],
    usage_error: Callable[[str], None],
    required: bool = True,
) -> Optional[dict]:
    helper_supplied = any([
        owner_email_template,
        respondent_email_template,
        template_file,
        respondent_filter_path,
        subject,
    ])
    if route_path:
        if helper_supplied:
            usage_error("--route cannot be combined with route helper options.")
        route = read_json(route_path)
        if not isinstance(route, dict):
            usage_error("Route JSON must be an object.")
        return route
    if not helper_supplied:
        if required:
            usage_error("Provide --route or route helper options.")
        return None
    if owner_email_template and (respondent_email_template or template_file or respondent_filter_path):
        usage_error("Owner email routes cannot be combined with respondent email route options.")
    if owner_email_template:
        route = {
            "channel": "email",
            "subtype": "owner",
            "delivery_template": {
                "source": "expected_parrot",
                "name": owner_email_template,
            },
        }
        if subject is not None:
            route["subject"] = subject
        return route

    template = (
        {"source": "inline", "html": read_optional_text(template_file)}
        if template_file
        else {
            "source": "expected_parrot",
            "name": respondent_email_template or "respondent_invitation",
        }
    )
    route = {
        "channel": "email",
        "subtype": "respondent",
        "delivery_template": template,
    }
    if respondent_filter_path:
        route["respondent_filter"] = read_json(respondent_filter_path)
    if subject is not None:
        route["subject"] = subject
    return route


def wait_for_delivery(
    coop,
    human_survey_uuid: str,
    delivery_uuid: str,
    poll_interval: float,
    timeout: Optional[float],
) -> dict:
    terminal_statuses = {"completed", "failed", "cancelled", "canceled"}
    started_at = time.monotonic()
    polls = 0

    while True:
        delivery = coop.get_human_survey_delivery(human_survey_uuid, delivery_uuid)
        polls += 1
        status = delivery.get("status")
        if str(status or "").lower() in terminal_statuses:
            return {
                "completed": status == "completed",
                "timed_out": False,
                "polls": polls,
                "elapsed_seconds": round(time.monotonic() - started_at, 3),
                "last_status": status,
                "delivery": delivery,
            }
        if timeout is not None and time.monotonic() - started_at >= timeout:
            return {
                "completed": False,
                "timed_out": True,
                "polls": polls,
                "elapsed_seconds": round(time.monotonic() - started_at, 3),
                "last_status": status,
                "delivery": delivery,
            }
        time.sleep(poll_interval)
