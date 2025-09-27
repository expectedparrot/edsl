from __future__ import annotations

from typing import Any, Optional, Type

from .output_formatter import OutputFormatters


class AppSerialization:
    @staticmethod
    def to_dict(app: Any, add_edsl_version: bool = True) -> dict:
        return {
            "initial_survey": (
                app.initial_survey.to_dict(add_edsl_version=add_edsl_version)
                if app.initial_survey
                else None
            ),
            "jobs_object": app.jobs_object.to_dict(add_edsl_version=add_edsl_version),
            "application_type": app.application_type,
            "application_name": app.application_name,
            "description": app.description,
            "output_formatters": app.output_formatters.to_dict(
                add_edsl_version=add_edsl_version
            ),
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

        kwargs = {
            "jobs_object": jobs_object,
            "output_formatters": OutputFormatters.from_dict(
                data.get("output_formatters")
            ),
            "description": data.get("description"),
            "application_name": data.get("application_name"),
            "initial_survey": Survey.from_dict(data.get("initial_survey")),
        }
        kwargs = {k: v for k, v in kwargs.items() if v is not None}

        if "initial_survey" not in kwargs or kwargs["initial_survey"] is None:
            raise ValueError("App.from_dict requires 'initial_survey' in data.")

        app_type = data.get("application_type")
        target_cls = app_cls
        if isinstance(app_type, str) and app_type in App._registry:
            target_cls = App._registry[app_type]

        return target_cls(**kwargs)


