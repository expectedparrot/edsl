from __future__ import annotations

from typing import Any, Optional, Type

from .output_formatter import OutputFormatters


class AppRemote:
    @staticmethod
    def push(app: Any, visibility: Optional[str] = "unlisted", description: Optional[str] = None, alias: Optional[str] = None):
        from ..scenarios import Scenario

        job_info = app.jobs_object.push(visibility=visibility).to_dict()
        if app.initial_survey is not None:
            initial_survey_info = app.initial_survey.push(visibility=visibility).to_dict()
        else:
            initial_survey_info = None

        app_info = Scenario(
            {
                "description": app.description,
                "application_name": app.application_name,
                "initial_survey_info": initial_survey_info,
                "job_info": job_info,
                "application_type": app.application_type,
                "class_name": app.__class__.__name__,
                "output_formatters_info": app.output_formatters.to_dict(),
            }
        ).push(visibility=visibility, description=description, alias=alias)
        return app_info

    @staticmethod
    def pull(app_cls: Type, edsl_uuid: str):
        from ..surveys import Survey
        from ..jobs import Jobs
        from ..scenarios import Scenario
        from .app import App

        app_info = Scenario.pull(edsl_uuid)
        jobs_object = Jobs.pull(app_info["job_info"]["uuid"])
        if app_info["initial_survey_info"] is not None:
            initial_survey = Survey.pull(app_info["initial_survey_info"]["uuid"])
        else:
            initial_survey = None
        output_formatters = OutputFormatters.from_dict(app_info.get("output_formatters_info"))

        kwargs = {
            "jobs_object": jobs_object,
            "output_formatters": output_formatters,
            "description": app_info.get("description"),
            "application_name": app_info.get("application_name"),
            "initial_survey": initial_survey,
        }
        kwargs = {k: v for k, v in kwargs.items() if v is not None}

        if "initial_survey" not in kwargs or kwargs["initial_survey"] is None:
            raise ValueError("App.pull requires the remote App to include an initial_survey.")

        app_type = app_info.get("application_type")
        target_cls = app_cls
        if isinstance(app_type, str) and app_type in App._registry:
            target_cls = App._registry[app_type]

        return target_cls(**kwargs)


