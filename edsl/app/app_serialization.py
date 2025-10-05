from __future__ import annotations

from typing import Any, Optional, Type

from .output_formatter import OutputFormatters


class AppSerialization:
    @staticmethod
    def to_dict(app: Any, add_edsl_version: bool = True) -> dict:
        # Get application_type - handle both class attribute and property
        app_type = getattr(app.__class__, 'application_type', 'base')
        if isinstance(app_type, property):
            # If it's a property, get it from the instance
            app_type = getattr(app, '_application_type', 'base')

        # Serialize attachment_formatters
        attachment_formatters_data = None
        if hasattr(app, 'attachment_formatters') and app.attachment_formatters:
            attachment_formatters_data = [
                formatter.to_dict()
                if hasattr(formatter, 'to_dict')
                else formatter.__dict__
                for formatter in app.attachment_formatters
            ]

        # Serialize application_name and description (convert TypedDicts to dicts)
        app_name = app.application_name
        if isinstance(app_name, dict):
            app_name_data = dict(app_name)  # Convert TypedDict to regular dict
        else:
            app_name_data = app_name

        description = app.description
        if isinstance(description, dict):
            description_data = dict(description)  # Convert TypedDict to regular dict
        else:
            description_data = description

        return {
            "initial_survey": (
                app.initial_survey.to_dict(add_edsl_version=add_edsl_version)
                if app.initial_survey
                else None
            ),
            "jobs_object": app.jobs_object.to_dict(add_edsl_version=add_edsl_version),
            "application_type": app_type,
            "application_name": app_name_data,
            "description": description_data,
            "output_formatters": app.output_formatters.to_dict(
                add_edsl_version=add_edsl_version
            ),
            "attachment_formatters": attachment_formatters_data,
        }

    @staticmethod
    def from_dict(app_cls: Type, data: dict):
        from ..jobs import Jobs
        from ..surveys import Survey
        from .app import App  # for registry

        try:
            jobs_object = Jobs.from_dict(data.get("jobs_object"))
        except Exception:
            from .stub_job import StubJob as _StubJob

            jobs_object = _StubJob.from_dict(data.get("jobs_object"))

        # Deserialize attachment_formatters
        attachment_formatters = None
        if data.get("attachment_formatters"):
            from .output_formatter import ObjectFormatter
            attachment_formatters = []
            for formatter_data in data["attachment_formatters"]:
                if isinstance(formatter_data, dict):
                    formatter = ObjectFormatter.from_dict(formatter_data)
                    attachment_formatters.append(formatter)

        kwargs = {
            "jobs_object": jobs_object,
            "output_formatters": OutputFormatters.from_dict(
                data.get("output_formatters")
            ),
            "description": data.get("description"),
            "application_name": data.get("application_name"),
            "initial_survey": Survey.from_dict(data.get("initial_survey")),
            "attachment_formatters": attachment_formatters,
        }
        kwargs = {k: v for k, v in kwargs.items() if v is not None}

        if "initial_survey" not in kwargs or kwargs["initial_survey"] is None:
            raise ValueError("App.from_dict requires 'initial_survey' in data.")

        app_type = data.get("application_type")
        target_cls = app_cls
        if isinstance(app_type, str) and app_type in App._registry:
            target_cls = App._registry[app_type]

        return target_cls(**kwargs)


