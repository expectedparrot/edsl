"""Humanize commands for the EDSL CLI."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Optional

import click

from edsl.cli_humanize_helpers import (
    build_route_input as build_route_input_helper,
    build_routes_input as build_routes_input_helper,
    read_optional_text as read_optional_text_helper,
    wait_for_delivery as wait_for_delivery_helper,
)
from edsl.cli_shared import (
    EXIT_ERROR,
    EXIT_REMOTE,
    EXIT_USAGE,
    EXIT_VALIDATION,
    error,
    jsonable,
    load_git_object,
    load_openable_json,
    output,
    read_serialized_object,
)


def register(humanize: click.Group) -> None:
    @humanize.group("schema", invoke_without_command=True)
    @click.pass_context
    def humanize_schema(ctx):
        """Validate humanize schemas."""
        if ctx.invoked_subcommand is None:
            output({
                "commands": ["validate", "patch"],
                "help": "Use 'ep humanize schema <command> --help' for details.",
            })


    @humanize.group("css", invoke_without_command=True)
    @click.pass_context
    def humanize_css(ctx):
        """Manage humanize CSS."""
        if ctx.invoked_subcommand is None:
            output({
                "commands": ["patch"],
                "help": "Use 'ep humanize css <command> --help' for details.",
            })


    @humanize.group("schedules", invoke_without_command=True)
    @click.pass_context
    def humanize_schedules(ctx):
        """Manage human survey delivery schedules."""
        if ctx.invoked_subcommand is None:
            output({
                "commands": [
                    "list", "get", "create-one-time", "create-cron",
                    "update-one-time", "update-cron", "activate", "deactivate",
                    "delete", "route-add", "route-delete", "route-patch-respondent-email",
                ],
                "help": "Use 'ep humanize schedules <command> --help' for details.",
            })


    @humanize.group("deliveries", invoke_without_command=True)
    @click.pass_context
    def humanize_deliveries(ctx):
        """Manage human survey deliveries."""
        if ctx.invoked_subcommand is None:
            output({
                "commands": ["list", "create", "get", "tasks", "task", "wait"],
                "help": "Use 'ep humanize deliveries <command> --help' for details.",
            })


    @humanize.group("callbacks", invoke_without_command=True)
    @click.pass_context
    def humanize_callbacks(ctx):
        """Manage human survey callbacks."""
        if ctx.invoked_subcommand is None:
            output({
                "commands": [
                    "list", "create", "get", "patch", "activate", "deactivate",
                    "delete", "route-add", "route-delete", "route-patch-respondent-email",
                ],
                "help": "Use 'ep humanize callbacks <command> --help' for details.",
            })


    @humanize.group("agent-list", invoke_without_command=True)
    @click.pass_context
    def humanize_agent_list(ctx):
        """Manage a human survey agent list config."""
        if ctx.invoked_subcommand is None:
            output({
                "commands": ["get", "patch"],
                "help": "Use 'ep humanize agent-list <command> --help' for details.",
            })


    @humanize.group("prolific", invoke_without_command=True)
    @click.pass_context
    def humanize_prolific(ctx):
        """Manage Prolific studies for human surveys."""
        if ctx.invoked_subcommand is None:
            output({
                "commands": ["filters", "cost", "create", "publish", "responses"],
                "help": "Use 'ep humanize prolific <command> --help' for details.",
            })


    # ---------------------------------------------------------------------------
    # ep humanize
    # ---------------------------------------------------------------------------

    @humanize.command("list")
    @click.option("--query", "-q", default=None, help="Search by name or UUID.")
    @click.option("--page", default=1, type=int, help="Page number.")
    @click.option("--page_size", default=10, type=int, help="Results per page (max 100).")
    @click.option("--sort_ascending", is_flag=True, default=False, help="Sort oldest first.")
    def humanize_list(query, page, page_size, sort_ascending):
        """List human surveys."""
        try:
            from edsl.coop import Coop

            result = Coop().list_human_surveys(
                page=page,
                page_size=page_size,
                search_query=query,
                sort_ascending=sort_ascending,
            )
            surveys = result.get("human_surveys", [])
            output({
                **jsonable(result),
                "page": page,
                "page_size": result.get("page_size", page_size),
                "returned_count": len(surveys),
                "query": query,
                "sort_ascending": sort_ascending,
            })
        except SystemExit:
            raise
        except Exception as e:
            error(
                "HUMANIZE_ERROR",
                str(e),
                suggestion="Check your Expected Parrot API key and list filters.",
                exit_code=EXIT_REMOTE,
            )


    @humanize_prolific.command("filters")
    def humanize_prolific_filters():
        """List supported Prolific filters."""
        try:
            from edsl.coop import Coop

            filters = Coop().list_prolific_filters()
            output(
                {
                    "object_type": type(filters).__name__,
                    "filter_count": len(filters) if hasattr(filters, "__len__") else None,
                    "filters": jsonable(filters.to_list() if hasattr(filters, "to_list") else filters),
                }
            )
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_prolific.command("cost")
    @click.option("--participant_payment_cents", required=True, type=int, help="Reward per participant in cents.")
    @click.option("--num_participants", required=True, type=int, help="Number of participants.")
    @click.option("--estimated_completion_time_minutes", required=True, type=int, help="Estimated completion time in minutes.")
    def humanize_prolific_cost(participant_payment_cents, num_participants, estimated_completion_time_minutes):
        """Estimate Prolific study cost."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().calculate_prolific_study_cost(
                participant_payment_cents=participant_payment_cents,
                num_participants=num_participants,
                estimated_completion_time_minutes=estimated_completion_time_minutes,
            )))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_prolific.command("create")
    @click.argument("human_survey_uuid")
    @click.option("--config", "config_path", required=True, type=click.Path(exists=True), help="Prolific study config JSON.")
    def humanize_prolific_create(human_survey_uuid, config_path):
        """Create a Prolific study for a human survey."""
        try:
            from edsl.coop import Coop

            config = _read_json_or_gzip(config_path)
            if not isinstance(config, dict):
                error("USAGE_ERROR", "Prolific config must be a JSON object.", exit_code=EXIT_USAGE)
            output(jsonable(Coop().create_prolific_study(human_survey_uuid, **config)))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_prolific.command("publish")
    @click.argument("human_survey_uuid")
    @click.argument("study_id")
    def humanize_prolific_publish(human_survey_uuid, study_id):
        """Publish a Prolific study."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().publish_prolific_study(human_survey_uuid, study_id)))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_prolific.command("responses")
    @click.argument("human_survey_uuid")
    @click.argument("study_id")
    @click.option("--output", "-o", "output_path", default=None, help="Save responses to .ep, .json, or .json.gz.")
    def humanize_prolific_responses(human_survey_uuid, study_id, output_path):
        """Fetch Prolific study responses."""
        try:
            from edsl.coop import Coop

            response_obj = Coop().get_prolific_study_responses(human_survey_uuid, study_id)
            data = {
                "human_survey_uuid": human_survey_uuid,
                "study_id": study_id,
                "object_type": type(response_obj).__name__,
                "result_count": len(response_obj) if hasattr(response_obj, "__len__") else None,
            }
            if output_path:
                data["saved"] = _save_edsl_object(response_obj, output_path)
            else:
                data["next_step"] = (
                    f"Use 'ep humanize prolific responses {human_survey_uuid} {study_id} "
                    "--output responses.ep' to save the response data."
                )
            output(data)
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize.command("status")
    @click.argument("human_survey_uuid")
    def humanize_status(human_survey_uuid):
        """Get human survey status and metadata."""
        try:
            from edsl.coop import Coop

            coop = Coop()
            data = jsonable(coop.get_human_survey(human_survey_uuid))
            if data.get("agent_list_uuid") is None:
                try:
                    agent_list_data = coop.get_human_survey_agent_list(human_survey_uuid)
                    agent_list_config = agent_list_data.get("agent_list_config")
                    if agent_list_config:
                        data["agent_list_uuid"] = agent_list_config.get("uuid")
                        data["agent_list_config"] = agent_list_config
                except Exception:
                    pass
            output(data)
        except SystemExit:
            raise
        except Exception as e:
            error(
                "HUMANIZE_ERROR",
                str(e),
                suggestion="Check the human survey UUID and Expected Parrot API key.",
                exit_code=EXIT_REMOTE,
            )


    @humanize.command("preview")
    @click.option("--survey", "survey_path", required=True, type=click.Path(exists=True), help="Survey .ep, JSON, or package directory.")
    @click.option("--schema", "schema_path", default=None, type=click.Path(exists=True), help="Humanize schema JSON.")
    def humanize_preview(survey_path, schema_path):
        """Create a human survey preview URL."""
        try:
            from edsl.coop import Coop

            survey = _load_survey_object(survey_path)
            humanize_schema_data = _read_json_or_gzip(schema_path) if schema_path else None
            preview_url = Coop().get_survey_preview_url(
                survey,
                humanize_schema=humanize_schema_data,
            )
            output({"preview_url": preview_url})
        except SystemExit:
            raise
        except Exception as e:
            error(
                "HUMANIZE_ERROR",
                str(e),
                suggestion="Check the survey path, schema, and Expected Parrot API key.",
                exit_code=EXIT_REMOTE,
            )


    @humanize_schema.command("validate")
    @click.option("--survey", "survey_path", required=True, type=click.Path(exists=True), help="Survey .ep, JSON, or package directory.")
    @click.option("--schema", "schema_path", required=True, type=click.Path(exists=True), help="Humanize schema JSON.")
    def humanize_schema_validate(survey_path, schema_path):
        """Validate a humanize schema against a survey."""
        try:
            from edsl.coop.coop_humanize_schema import validate_humanize_schema

            survey = _load_survey_object(survey_path)
            humanize_schema_data = _read_json_or_gzip(schema_path)
            validate_humanize_schema(survey, humanize_schema_data)
            output({"valid": True})
        except SystemExit:
            raise
        except Exception as e:
            error(
                "VALIDATION_ERROR",
                str(e),
                suggestion="Check that the schema matches the survey questions and supported humanize options.",
                exit_code=EXIT_VALIDATION,
            )


    @humanize.command("responses")
    @click.argument("human_survey_uuid")
    @click.option("--output", "-o", "output_path", default=None, help="Save responses to .ep, .json, or .json.gz.")
    def humanize_responses(human_survey_uuid, output_path):
        """Fetch human survey responses."""
        try:
            from edsl.coop import Coop

            response_obj = Coop().get_human_survey_responses(human_survey_uuid)
            data = {
                "human_survey_uuid": human_survey_uuid,
                "object_type": type(response_obj).__name__,
                "result_count": len(response_obj) if hasattr(response_obj, "__len__") else None,
            }
            if output_path:
                data["saved"] = _save_edsl_object(response_obj, output_path)
            else:
                data["next_step"] = (
                    f"Use 'ep humanize responses {human_survey_uuid} --output responses.ep' "
                    "to save the response data."
                )
            output(data)
        except SystemExit:
            raise
        except Exception as e:
            error(
                "HUMANIZE_ERROR",
                str(e),
                suggestion="Check the human survey UUID, output path, and Expected Parrot API key.",
                exit_code=EXIT_REMOTE,
            )


    @humanize.command("qr")
    @click.argument("human_survey_uuid")
    @click.option("--output", "-o", "output_path", required=True, help="PNG output path.")
    def humanize_qr(human_survey_uuid, output_path):
        """Generate a QR code for a human survey respondent URL."""
        try:
            from edsl.coop import Coop

            qr = Coop().get_human_survey_qr_code(human_survey_uuid)
            qr.save(output_path)
            output({"human_survey_uuid": human_survey_uuid, "saved_to": output_path})
        except ImportError as e:
            error(
                "DEPENDENCY_ERROR",
                str(e),
                suggestion='Install QR support with pip install "edsl[full]" or pip install "qrcode[pil]".',
                exit_code=EXIT_ERROR,
            )
        except SystemExit:
            raise
        except Exception as e:
            error(
                "HUMANIZE_ERROR",
                str(e),
                suggestion="Check the human survey UUID, output path, and Expected Parrot API key.",
                exit_code=EXIT_REMOTE,
            )


    @humanize.command("respondents")
    @click.argument("human_survey_uuid")
    @click.option("--page", default=1, type=int, help="Page number.")
    @click.option("--page_size", default=50, type=int, help="Results per page.")
    def humanize_respondents(human_survey_uuid, page, page_size):
        """List human survey respondents."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().get_human_survey_respondents(
                human_survey_uuid,
                page=page,
                page_size=page_size,
            )))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_schema.command("patch")
    @click.argument("human_survey_uuid")
    @click.option("--schema", "schema_path", required=True, type=click.Path(exists=True), help="Partial humanize schema JSON.")
    def humanize_schema_patch(human_survey_uuid, schema_path):
        """Patch a human survey humanize schema."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().patch_human_survey_humanize_schema(
                human_survey_uuid,
                _read_json_or_gzip(schema_path),
            )))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_css.command("patch")
    @click.argument("human_survey_uuid")
    @click.option("--file", "css_path", default=None, type=click.Path(exists=True), help="CSS file to apply.")
    @click.option("--clear", is_flag=True, default=False, help="Clear existing custom CSS.")
    def humanize_css_patch(human_survey_uuid, css_path, clear):
        """Patch or clear human survey custom CSS."""
        if bool(css_path) == bool(clear):
            error(
                "USAGE_ERROR",
                "Provide exactly one of --file or --clear.",
                exit_code=EXIT_USAGE,
            )
        try:
            from edsl.coop import Coop

            css = None if clear else Path(css_path).read_text(encoding="utf-8")
            output(jsonable(Coop().patch_human_survey_css(human_survey_uuid, css)))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_agent_list.command("get")
    @click.argument("human_survey_uuid")
    def humanize_agent_list_get(human_survey_uuid):
        """Get a human survey agent list config."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().get_human_survey_agent_list(human_survey_uuid)))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_agent_list.command("patch")
    @click.argument("human_survey_uuid")
    @click.option("--delivery_map", "delivery_map_path", default=None, type=click.Path(exists=True), help="Delivery map JSON.")
    @click.option("--anonymous/--not_anonymous", default=None, help="Set anonymous response mode.")
    @click.option("--allow_resubmit/--no_allow_resubmit", default=None, help="Set respondent resubmission mode.")
    def humanize_agent_list_patch(human_survey_uuid, delivery_map_path, anonymous, allow_resubmit):
        """Patch a human survey agent list config."""
        if delivery_map_path is None and anonymous is None and allow_resubmit is None:
            error(
                "USAGE_ERROR",
                "Provide at least one of --delivery_map, --anonymous/--not_anonymous, or --allow_resubmit/--no_allow_resubmit.",
                exit_code=EXIT_USAGE,
            )
        try:
            from edsl.coop import Coop

            delivery_map = _read_json_or_gzip(delivery_map_path) if delivery_map_path else None
            output(jsonable(Coop().patch_human_survey_agent_list(
                human_survey_uuid,
                delivery_map=delivery_map,
                anonymous=anonymous,
                allow_resubmit=allow_resubmit,
            )))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_deliveries.command("list")
    @click.argument("human_survey_uuid")
    @click.option("--page", default=1, type=int, help="Page number.")
    @click.option("--page_size", default=50, type=int, help="Results per page.")
    def humanize_deliveries_list(human_survey_uuid, page, page_size):
        """List human survey deliveries."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().list_human_survey_deliveries(
                human_survey_uuid,
                page=page,
                page_size=page_size,
            )))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_deliveries.command("create")
    @click.argument("human_survey_uuid")
    @click.option("--name", required=True, help="Delivery job name.")
    @click.option("--routes", "routes_path", default=None, type=click.Path(exists=True), help="Routes JSON list.")
    @click.option("--owner-email-template", default=None, type=click.Choice(["owner_response_received", "owner_transcript"]), help="Create an owner email route with this built-in template.")
    @click.option("--respondent-email-template", default=None, type=click.Choice(["respondent_invitation", "respondent_transcript"]), help="Create a respondent email route with this built-in template.")
    @click.option("--template_file", default=None, type=click.Path(exists=True), help="Inline HTML template file for a respondent email route.")
    @click.option("--respondent_filter", "respondent_filter_path", default=None, type=click.Path(exists=True), help="Respondent filter JSON for respondent email route.")
    @click.option("--subject", default=None, help="Email subject for generated route.")
    def humanize_deliveries_create(
        human_survey_uuid,
        name,
        routes_path,
        owner_email_template,
        respondent_email_template,
        template_file,
        respondent_filter_path,
        subject,
    ):
        """Create a human survey delivery."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().create_human_survey_delivery(
                human_survey_uuid,
                name=name,
                routes=_build_routes_input(
                    routes_path,
                    owner_email_template,
                    respondent_email_template,
                    template_file,
                    respondent_filter_path,
                    subject,
                ),
            )))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_deliveries.command("get")
    @click.argument("human_survey_uuid")
    @click.argument("delivery_uuid")
    def humanize_deliveries_get(human_survey_uuid, delivery_uuid):
        """Get a human survey delivery."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().get_human_survey_delivery(human_survey_uuid, delivery_uuid)))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_deliveries.command("tasks")
    @click.argument("human_survey_uuid")
    @click.argument("delivery_uuid")
    @click.option("--page", default=1, type=int, help="Page number.")
    @click.option("--page_size", default=50, type=int, help="Results per page.")
    def humanize_deliveries_tasks(human_survey_uuid, delivery_uuid, page, page_size):
        """List human survey delivery tasks."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().list_human_survey_delivery_tasks(
                human_survey_uuid,
                delivery_uuid,
                page=page,
                page_size=page_size,
            )))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_deliveries.command("task")
    @click.argument("human_survey_uuid")
    @click.argument("task_uuid")
    def humanize_deliveries_task(human_survey_uuid, task_uuid):
        """Get a human survey delivery task."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().get_human_survey_delivery_task(human_survey_uuid, task_uuid)))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_deliveries.command("wait")
    @click.argument("human_survey_uuid")
    @click.argument("delivery_uuid")
    @click.option("--poll_interval", default=2.0, type=float, help="Seconds between delivery status checks.")
    @click.option("--timeout", default=None, type=float, help="Maximum seconds to wait.")
    def humanize_deliveries_wait(human_survey_uuid, delivery_uuid, poll_interval, timeout):
        """Poll a delivery until it reaches a terminal status."""
        if poll_interval <= 0:
            error("USAGE_ERROR", "--poll_interval must be greater than 0.", exit_code=EXIT_USAGE)
        if timeout is not None and timeout <= 0:
            error("USAGE_ERROR", "--timeout must be greater than 0.", exit_code=EXIT_USAGE)
        try:
            from edsl.coop import Coop

            coop = Coop()
            output(_wait_for_humanize_delivery(
                coop,
                human_survey_uuid,
                delivery_uuid,
                poll_interval=poll_interval,
                timeout=timeout,
            ))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_schedules.command("list")
    @click.argument("human_survey_uuid")
    @click.option("--page", default=1, type=int, help="Page number.")
    @click.option("--page_size", default=50, type=int, help="Results per page.")
    def humanize_schedules_list(human_survey_uuid, page, page_size):
        """List human survey schedules."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().list_human_survey_schedules(
                human_survey_uuid,
                page=page,
                page_size=page_size,
            )))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_schedules.command("get")
    @click.argument("human_survey_uuid")
    @click.argument("schedule_uuid")
    def humanize_schedules_get(human_survey_uuid, schedule_uuid):
        """Get a human survey schedule."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().get_human_survey_schedule(human_survey_uuid, schedule_uuid)))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_schedules.command("create-one-time")
    @click.argument("human_survey_uuid")
    @click.option("--name", required=True, help="Schedule name.")
    @click.option("--run_at", required=True, help="ISO 8601 run time.")
    @click.option("--routes", "routes_path", default=None, type=click.Path(exists=True), help="Routes JSON list.")
    @click.option("--owner-email-template", default=None, type=click.Choice(["owner_response_received", "owner_transcript"]), help="Create an owner email route with this built-in template.")
    @click.option("--respondent-email-template", default=None, type=click.Choice(["respondent_invitation", "respondent_transcript"]), help="Create a respondent email route with this built-in template.")
    @click.option("--template_file", default=None, type=click.Path(exists=True), help="Inline HTML template file for a respondent email route.")
    @click.option("--respondent_filter", "respondent_filter_path", default=None, type=click.Path(exists=True), help="Respondent filter JSON for respondent email route.")
    @click.option("--subject", default=None, help="Email subject for generated route.")
    def humanize_schedules_create_one_time(
        human_survey_uuid,
        name,
        run_at,
        routes_path,
        owner_email_template,
        respondent_email_template,
        template_file,
        respondent_filter_path,
        subject,
    ):
        """Create a one-time human survey schedule."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().create_human_survey_one_time_schedule(
                human_survey_uuid,
                name=name,
                run_at=run_at,
                routes=_build_routes_input(
                    routes_path,
                    owner_email_template,
                    respondent_email_template,
                    template_file,
                    respondent_filter_path,
                    subject,
                ),
            )))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_schedules.command("create-cron")
    @click.argument("human_survey_uuid")
    @click.option("--name", required=True, help="Schedule name.")
    @click.option("--cron_expression", required=True, help="Cron expression.")
    @click.option("--timezone", required=True, help="IANA timezone.")
    @click.option("--max_jobs", default=None, type=int, help="Stop after this many jobs.")
    @click.option("--deadline", default=None, help="ISO 8601 deadline.")
    @click.option("--start_at", default=None, help="ISO 8601 start time.")
    @click.option("--routes", "routes_path", default=None, type=click.Path(exists=True), help="Routes JSON list.")
    @click.option("--owner-email-template", default=None, type=click.Choice(["owner_response_received", "owner_transcript"]), help="Create an owner email route with this built-in template.")
    @click.option("--respondent-email-template", default=None, type=click.Choice(["respondent_invitation", "respondent_transcript"]), help="Create a respondent email route with this built-in template.")
    @click.option("--template_file", default=None, type=click.Path(exists=True), help="Inline HTML template file for a respondent email route.")
    @click.option("--respondent_filter", "respondent_filter_path", default=None, type=click.Path(exists=True), help="Respondent filter JSON for respondent email route.")
    @click.option("--subject", default=None, help="Email subject for generated route.")
    def humanize_schedules_create_cron(
        human_survey_uuid,
        name,
        cron_expression,
        timezone,
        max_jobs,
        deadline,
        start_at,
        routes_path,
        owner_email_template,
        respondent_email_template,
        template_file,
        respondent_filter_path,
        subject,
    ):
        """Create a cron human survey schedule."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().create_human_survey_cron_schedule(
                human_survey_uuid,
                name=name,
                cron_expression=cron_expression,
                timezone=timezone,
                max_jobs=max_jobs,
                deadline=deadline,
                start_at=start_at,
                routes=_build_routes_input(
                    routes_path,
                    owner_email_template,
                    respondent_email_template,
                    template_file,
                    respondent_filter_path,
                    subject,
                ),
            )))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_schedules.command("update-one-time")
    @click.argument("human_survey_uuid")
    @click.argument("schedule_uuid")
    @click.option("--run_at", required=True, help="ISO 8601 run time.")
    def humanize_schedules_update_one_time(human_survey_uuid, schedule_uuid, run_at):
        """Update a one-time human survey schedule."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().update_human_survey_one_time_schedule(
                human_survey_uuid,
                schedule_uuid,
                run_at=run_at,
            )))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_schedules.command("update-cron")
    @click.argument("human_survey_uuid")
    @click.argument("schedule_uuid")
    @click.option("--cron_expression", default=None, help="Cron expression.")
    @click.option("--timezone", default=None, help="IANA timezone.")
    @click.option("--max_jobs", default=None, type=int, help="Stop after this many jobs.")
    @click.option("--deadline", default=None, help="ISO 8601 deadline.")
    @click.option("--start_at", default=None, help="ISO 8601 start time.")
    def humanize_schedules_update_cron(human_survey_uuid, schedule_uuid, cron_expression, timezone, max_jobs, deadline, start_at):
        """Update a cron human survey schedule."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().update_human_survey_cron_schedule(
                human_survey_uuid,
                schedule_uuid,
                cron_expression=cron_expression,
                timezone=timezone,
                max_jobs=max_jobs,
                deadline=deadline,
                start_at=start_at,
            )))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_schedules.command("activate")
    @click.argument("human_survey_uuid")
    @click.argument("schedule_uuid")
    def humanize_schedules_activate(human_survey_uuid, schedule_uuid):
        """Activate a human survey schedule."""
        _set_humanize_schedule_active(human_survey_uuid, schedule_uuid, True)


    @humanize_schedules.command("deactivate")
    @click.argument("human_survey_uuid")
    @click.argument("schedule_uuid")
    def humanize_schedules_deactivate(human_survey_uuid, schedule_uuid):
        """Deactivate a human survey schedule."""
        _set_humanize_schedule_active(human_survey_uuid, schedule_uuid, False)


    @humanize_schedules.command("delete")
    @click.argument("human_survey_uuid")
    @click.argument("schedule_uuid")
    def humanize_schedules_delete(human_survey_uuid, schedule_uuid):
        """Delete a human survey schedule."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().delete_human_survey_schedule(human_survey_uuid, schedule_uuid)))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_schedules.command("route-add")
    @click.argument("human_survey_uuid")
    @click.argument("schedule_uuid")
    @click.option("--route", "route_path", default=None, type=click.Path(exists=True), help="Route JSON object.")
    @click.option("--owner-email-template", default=None, type=click.Choice(["owner_response_received", "owner_transcript"]), help="Create an owner email route with this built-in template.")
    @click.option("--respondent-email-template", default=None, type=click.Choice(["respondent_invitation", "respondent_transcript"]), help="Create a respondent email route with this built-in template.")
    @click.option("--template_file", default=None, type=click.Path(exists=True), help="Inline HTML template file for a respondent email route.")
    @click.option("--respondent_filter", "respondent_filter_path", default=None, type=click.Path(exists=True), help="Respondent filter JSON for respondent email route.")
    @click.option("--subject", default=None, help="Email subject for generated route.")
    def humanize_schedules_route_add(
        human_survey_uuid,
        schedule_uuid,
        route_path,
        owner_email_template,
        respondent_email_template,
        template_file,
        respondent_filter_path,
        subject,
    ):
        """Add a route to a human survey schedule."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().add_human_survey_schedule_route(
                human_survey_uuid,
                schedule_uuid,
                _build_route_input(
                    route_path,
                    owner_email_template,
                    respondent_email_template,
                    template_file,
                    respondent_filter_path,
                    subject,
                ),
            )))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_schedules.command("route-delete")
    @click.argument("human_survey_uuid")
    @click.argument("schedule_uuid")
    @click.argument("route_uuid")
    def humanize_schedules_route_delete(human_survey_uuid, schedule_uuid, route_uuid):
        """Delete a route from a human survey schedule."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().delete_human_survey_schedule_route(
                human_survey_uuid,
                schedule_uuid,
                route_uuid,
            )))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_schedules.command("route-patch-respondent-email")
    @click.argument("human_survey_uuid")
    @click.argument("schedule_uuid")
    @click.argument("route_uuid")
    @click.option("--template_file", default=None, type=click.Path(exists=True), help="HTML email template file.")
    @click.option("--respondent_filter", "respondent_filter_path", default=None, type=click.Path(exists=True), help="Respondent filter JSON.")
    @click.option("--subject", default=None, help="Email subject.")
    def humanize_schedules_route_patch_respondent_email(human_survey_uuid, schedule_uuid, route_uuid, template_file, respondent_filter_path, subject):
        """Patch a respondent email route on a human survey schedule."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().patch_human_survey_schedule_respondent_email_route(
                human_survey_uuid,
                schedule_uuid,
                route_uuid,
                delivery_template=_read_optional_text(template_file),
                respondent_filter=_read_json_or_gzip(respondent_filter_path) if respondent_filter_path else None,
                subject=subject,
            )))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_callbacks.command("list")
    @click.argument("human_survey_uuid")
    @click.option("--page", default=1, type=int, help="Page number.")
    @click.option("--page_size", default=50, type=int, help="Results per page.")
    def humanize_callbacks_list(human_survey_uuid, page, page_size):
        """List human survey callbacks."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().list_human_survey_callbacks(
                human_survey_uuid,
                page=page,
                page_size=page_size,
            )))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_callbacks.command("create")
    @click.argument("human_survey_uuid")
    @click.option("--name", required=True, help="Callback name.")
    @click.option("--type", "callback_type", required=True, help="Callback event type.")
    @click.option("--routes", "routes_path", default=None, type=click.Path(exists=True), help="Routes JSON list.")
    @click.option("--max_fires", default=None, type=int, help="Maximum callback fires.")
    @click.option("--owner-email-template", default=None, type=click.Choice(["owner_response_received", "owner_transcript"]), help="Create an owner email route with this built-in template.")
    @click.option("--respondent-email-template", default=None, type=click.Choice(["respondent_invitation", "respondent_transcript"]), help="Create a respondent email route with this built-in template.")
    @click.option("--template_file", default=None, type=click.Path(exists=True), help="Inline HTML template file for a respondent email route.")
    @click.option("--respondent_filter", "respondent_filter_path", default=None, type=click.Path(exists=True), help="Respondent filter JSON for respondent email route.")
    @click.option("--subject", default=None, help="Email subject for generated route.")
    def humanize_callbacks_create(
        human_survey_uuid,
        name,
        callback_type,
        routes_path,
        max_fires,
        owner_email_template,
        respondent_email_template,
        template_file,
        respondent_filter_path,
        subject,
    ):
        """Create a human survey callback."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().create_human_survey_callback(
                human_survey_uuid,
                name=name,
                callback_type=callback_type,
                routes=_build_routes_input(
                    routes_path,
                    owner_email_template,
                    respondent_email_template,
                    template_file,
                    respondent_filter_path,
                    subject,
                ),
                max_fires=max_fires,
            )))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_callbacks.command("get")
    @click.argument("human_survey_uuid")
    @click.argument("callback_uuid")
    def humanize_callbacks_get(human_survey_uuid, callback_uuid):
        """Get a human survey callback."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().get_human_survey_callback(human_survey_uuid, callback_uuid)))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_callbacks.command("patch")
    @click.argument("human_survey_uuid")
    @click.argument("callback_uuid")
    @click.option("--name", default=None, help="New callback name.")
    def humanize_callbacks_patch(human_survey_uuid, callback_uuid, name):
        """Patch a human survey callback."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().patch_human_survey_callback(
                human_survey_uuid,
                callback_uuid,
                name=name,
            )))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_callbacks.command("activate")
    @click.argument("human_survey_uuid")
    @click.argument("callback_uuid")
    def humanize_callbacks_activate(human_survey_uuid, callback_uuid):
        """Activate a human survey callback."""
        _set_humanize_callback_active(human_survey_uuid, callback_uuid, True)


    @humanize_callbacks.command("deactivate")
    @click.argument("human_survey_uuid")
    @click.argument("callback_uuid")
    def humanize_callbacks_deactivate(human_survey_uuid, callback_uuid):
        """Deactivate a human survey callback."""
        _set_humanize_callback_active(human_survey_uuid, callback_uuid, False)


    @humanize_callbacks.command("delete")
    @click.argument("human_survey_uuid")
    @click.argument("callback_uuid")
    def humanize_callbacks_delete(human_survey_uuid, callback_uuid):
        """Delete a human survey callback."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().delete_human_survey_callback(human_survey_uuid, callback_uuid)))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_callbacks.command("route-add")
    @click.argument("human_survey_uuid")
    @click.argument("callback_uuid")
    @click.option("--route", "route_path", default=None, type=click.Path(exists=True), help="Route JSON object.")
    @click.option("--owner-email-template", default=None, type=click.Choice(["owner_response_received", "owner_transcript"]), help="Create an owner email route with this built-in template.")
    @click.option("--respondent-email-template", default=None, type=click.Choice(["respondent_invitation", "respondent_transcript"]), help="Create a respondent email route with this built-in template.")
    @click.option("--template_file", default=None, type=click.Path(exists=True), help="Inline HTML template file for a respondent email route.")
    @click.option("--respondent_filter", "respondent_filter_path", default=None, type=click.Path(exists=True), help="Respondent filter JSON for respondent email route.")
    @click.option("--subject", default=None, help="Email subject for generated route.")
    def humanize_callbacks_route_add(
        human_survey_uuid,
        callback_uuid,
        route_path,
        owner_email_template,
        respondent_email_template,
        template_file,
        respondent_filter_path,
        subject,
    ):
        """Add a route to a human survey callback."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().add_human_survey_callback_route(
                human_survey_uuid,
                callback_uuid,
                _build_route_input(
                    route_path,
                    owner_email_template,
                    respondent_email_template,
                    template_file,
                    respondent_filter_path,
                    subject,
                ),
            )))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_callbacks.command("route-delete")
    @click.argument("human_survey_uuid")
    @click.argument("callback_uuid")
    @click.argument("route_uuid")
    def humanize_callbacks_route_delete(human_survey_uuid, callback_uuid, route_uuid):
        """Delete a route from a human survey callback."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().delete_human_survey_callback_route(
                human_survey_uuid,
                callback_uuid,
                route_uuid,
            )))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize_callbacks.command("route-patch-respondent-email")
    @click.argument("human_survey_uuid")
    @click.argument("callback_uuid")
    @click.argument("route_uuid")
    @click.option("--template_file", default=None, type=click.Path(exists=True), help="HTML email template file.")
    @click.option("--respondent_filter", "respondent_filter_path", default=None, type=click.Path(exists=True), help="Respondent filter JSON.")
    @click.option("--subject", default=None, help="Email subject.")
    def humanize_callbacks_route_patch_respondent_email(human_survey_uuid, callback_uuid, route_uuid, template_file, respondent_filter_path, subject):
        """Patch a respondent email route on a human survey callback."""
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().patch_human_survey_callback_respondent_email_route(
                human_survey_uuid,
                callback_uuid,
                route_uuid,
                delivery_template=_read_optional_text(template_file),
                respondent_filter=_read_json_or_gzip(respondent_filter_path) if respondent_filter_path else None,
                subject=subject,
            )))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    def _set_humanize_schedule_active(human_survey_uuid, schedule_uuid, is_active):
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().set_human_survey_schedule_active(
                human_survey_uuid,
                schedule_uuid,
                is_active,
            )))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    def _set_humanize_callback_active(human_survey_uuid, callback_uuid, is_active):
        try:
            from edsl.coop import Coop

            output(jsonable(Coop().set_human_survey_callback_active(
                human_survey_uuid,
                callback_uuid,
                is_active,
            )))
        except SystemExit:
            raise
        except Exception as e:
            error("HUMANIZE_ERROR", str(e), exit_code=EXIT_REMOTE)


    @humanize.command("create")
    @click.option("--survey", "survey_path", default=None, type=click.Path(exists=True), help="Survey .ep, JSON, or package directory.")
    @click.option("--jobs", "jobs_path", default=None, type=click.Path(exists=True), help="Jobs .ep, JSON, or package directory.")
    @click.option("--name", "human_survey_name", default="New survey", help="Human survey name.")
    @click.option("--schema", "schema_path", default=None, type=click.Path(exists=True), help="Humanize schema JSON.")
    @click.option("--scenario_list", "scenario_list_path", default=None, type=click.Path(exists=True), help="ScenarioList .ep, JSON, or package directory.")
    @click.option("--scenario_method", default=None, type=click.Choice(["randomize", "loop", "single_scenario", "ordered"]), help="Scenario assignment method.")
    @click.option("--agent_list", "agent_list_path", default=None, type=click.Path(exists=True), help="AgentList .ep, JSON, or package directory.")
    @click.option("--survey_description", default=None, help="Description for uploaded survey.")
    @click.option("--survey_alias", default=None, help="Alias for uploaded survey.")
    @click.option("--survey_visibility", default="private", help="private, public, or unlisted.")
    @click.option("--scenario_list_description", default=None, help="Description for uploaded scenario list.")
    @click.option("--scenario_list_alias", default=None, help="Alias for uploaded scenario list.")
    @click.option("--scenario_list_visibility", default="private", help="private, public, or unlisted.")
    @click.option("--agent_list_description", default=None, help="Description for uploaded agent list.")
    @click.option("--agent_list_alias", default=None, help="Alias for uploaded agent list.")
    @click.option("--agent_list_visibility", default="private", help="private, public, or unlisted.")
    @click.option("--delivery_map", "delivery_map_path", default=None, type=click.Path(exists=True), help="Delivery map JSON.")
    def humanize_create(
        survey_path,
        jobs_path,
        human_survey_name,
        schema_path,
        scenario_list_path,
        scenario_method,
        agent_list_path,
        survey_description,
        survey_alias,
        survey_visibility,
        scenario_list_description,
        scenario_list_alias,
        scenario_list_visibility,
        agent_list_description,
        agent_list_alias,
        agent_list_visibility,
        delivery_map_path,
    ):
        """Create a human survey."""
        if bool(survey_path) == bool(jobs_path):
            error(
                "USAGE_ERROR",
                "Provide exactly one of --survey or --jobs.",
                exit_code=EXIT_USAGE,
            )
        if bool(scenario_list_path) != bool(scenario_method):
            error(
                "USAGE_ERROR",
                "--scenario_list and --scenario_method must be supplied together.",
                exit_code=EXIT_USAGE,
            )
        if jobs_path and (scenario_list_path or agent_list_path):
            error(
                "USAGE_ERROR",
                "--scenario_list and --agent_list cannot be used with --jobs.",
                suggestion="Include scenarios and agents in the Jobs object instead.",
                exit_code=EXIT_USAGE,
            )

        try:
            from edsl.coop import Coop

            humanize_schema_data = _read_json_or_gzip(schema_path) if schema_path else None
            delivery_map_data = _read_json_or_gzip(delivery_map_path) if delivery_map_path else None

            if jobs_path:
                jobs_obj = _load_jobs_object(jobs_path)
                if len(jobs_obj.models) > 0:
                    error(
                        "VALIDATION_ERROR",
                        "Humanize does not support Jobs with models.",
                        exit_code=EXIT_VALIDATION,
                    )
                survey = jobs_obj.survey
                agent_list = jobs_obj.agents if len(jobs_obj.agents) > 0 else None
                scenario_list = jobs_obj.scenarios if len(jobs_obj.scenarios) > 0 else None
                if scenario_list is not None and scenario_method is None:
                    error(
                        "USAGE_ERROR",
                        "Jobs with scenarios require --scenario_method.",
                        exit_code=EXIT_USAGE,
                    )
            else:
                survey = _load_survey_object(survey_path)
                agent_list = _load_agent_list_object(agent_list_path) if agent_list_path else None
                scenario_list = (
                    _load_scenario_list_object(scenario_list_path)
                    if scenario_list_path
                    else None
                )

            result = Coop().create_human_survey(
                survey=survey,
                scenario_list=scenario_list,
                scenario_list_method=scenario_method,
                human_survey_name=human_survey_name,
                survey_description=survey_description,
                survey_alias=survey_alias,
                survey_visibility=survey_visibility,
                scenario_list_description=scenario_list_description,
                scenario_list_alias=scenario_list_alias,
                scenario_list_visibility=scenario_list_visibility,
                agent_list=agent_list,
                agent_list_description=agent_list_description,
                agent_list_alias=agent_list_alias,
                agent_list_visibility=agent_list_visibility,
                humanize_schema=humanize_schema_data,
                delivery_map=delivery_map_data,
            )
            output(jsonable(result))
        except SystemExit:
            raise
        except Exception as e:
            error(
                "HUMANIZE_ERROR",
                str(e),
                suggestion="Check the input objects, schema, aliases, visibility values, and Expected Parrot API key.",
                exit_code=EXIT_REMOTE,
            )


    def _load_costable_object(path: Path):
        if path.is_dir() or path.suffix == ".ep":
            return load_git_object(path)
        return load_openable_json(path)


    def _load_survey_object(path: str):
        from edsl.surveys import Survey

        obj = _load_costable_object(Path(path))
        if not isinstance(obj, Survey):
            error(
                "UNSUPPORTED_OBJECT",
                f"Expected a Survey object, got {type(obj).__name__}.",
                exit_code=EXIT_VALIDATION,
            )
        return obj


    def _load_jobs_object(path: str):
        from edsl.jobs import Jobs

        obj = _load_costable_object(Path(path))
        if not isinstance(obj, Jobs):
            error(
                "UNSUPPORTED_OBJECT",
                f"Expected a Jobs object, got {type(obj).__name__}.",
                exit_code=EXIT_VALIDATION,
            )
        return obj


    def _load_agent_list_object(path: str):
        from edsl.agents import AgentList

        obj = _load_costable_object(Path(path))
        if not isinstance(obj, AgentList):
            error(
                "UNSUPPORTED_OBJECT",
                f"Expected an AgentList object, got {type(obj).__name__}.",
                exit_code=EXIT_VALIDATION,
            )
        return obj


    def _load_scenario_list_object(path: str):
        from edsl.scenarios import ScenarioList

        obj = _load_costable_object(Path(path))
        if not isinstance(obj, ScenarioList):
            error(
                "UNSUPPORTED_OBJECT",
                f"Expected a ScenarioList object, got {type(obj).__name__}.",
                exit_code=EXIT_VALIDATION,
            )
        return obj


    def _read_json_or_gzip(path: str) -> dict:
        return read_serialized_object(Path(path))


    def _read_routes_json(path: Optional[str]):
        if path is None:
            return None
        return _build_routes_input(path, None, None, None, None, None)


    def _build_routes_input(
        routes_path: Optional[str],
        owner_email_template: Optional[str],
        respondent_email_template: Optional[str],
        template_file: Optional[str],
        respondent_filter_path: Optional[str],
        subject: Optional[str],
    ):
        return build_routes_input_helper(
            routes_path,
            owner_email_template,
            respondent_email_template,
            template_file,
            respondent_filter_path,
            subject,
            read_json=_read_json_or_gzip,
            usage_error=_humanize_usage_error,
        )


    def _build_route_input(
        route_path: Optional[str],
        owner_email_template: Optional[str],
        respondent_email_template: Optional[str],
        template_file: Optional[str],
        respondent_filter_path: Optional[str],
        subject: Optional[str],
        required: bool = True,
    ):
        return build_route_input_helper(
            route_path,
            owner_email_template,
            respondent_email_template,
            template_file,
            respondent_filter_path,
            subject,
            read_json=_read_json_or_gzip,
            usage_error=_humanize_usage_error,
            required=required,
        )


    def _read_optional_text(path: Optional[str]) -> Optional[str]:
        return read_optional_text_helper(path)


    def _humanize_usage_error(message: str) -> None:
        error("USAGE_ERROR", message, exit_code=EXIT_USAGE)


    def _save_edsl_object(obj, output_path: str) -> dict:
        path = Path(output_path)
        object_type = type(obj).__name__
        if path.suffix == ".ep":
            if not hasattr(obj, "git"):
                error(
                    "UNSUPPORTED_OBJECT",
                    f"{object_type} cannot be saved as a .ep package.",
                    exit_code=EXIT_VALIDATION,
                )
            info = obj.git.save(path)
            return {
                "path": info.get("path", str(path)),
                "format": "ep",
                "object_type": object_type,
                "commit": info.get("commit"),
                "branch": info.get("branch"),
            }
        if path.name.endswith(".json.gz"):
            with gzip.open(path, "wt", encoding="utf-8") as f:
                json.dump(obj.to_dict(), f, indent=2, default=str)
            return {"path": str(path), "format": "json.gz", "object_type": object_type}
        if path.suffix == ".json":
            path.write_text(json.dumps(obj.to_dict(), indent=2, default=str), encoding="utf-8")
            return {"path": str(path), "format": "json", "object_type": object_type}
        error(
            "USAGE_ERROR",
            f"Unsupported output extension: {path}",
            suggestion="Use .ep, .json, or .json.gz.",
            exit_code=EXIT_USAGE,
        )


    def _wait_for_humanize_delivery(
        coop,
        human_survey_uuid: str,
        delivery_uuid: str,
        poll_interval: float,
        timeout: Optional[float],
    ) -> dict:
        return jsonable(wait_for_delivery_helper(
            coop,
            human_survey_uuid,
            delivery_uuid,
            poll_interval,
            timeout,
        ))
