from __future__ import annotations

from typing import Any, Optional, Type

from .output_formatter import OutputFormatters


class MacroRemote:
    @staticmethod
    def push(macro: Any, visibility: Optional[str] = "unlisted", description: Optional[str] = None, alias: Optional[str] = None):
        from ..scenarios import Scenario

        job_info = macro.jobs_object.push(visibility=visibility).to_dict()
        if macro.initial_survey is not None:
            initial_survey_info = macro.initial_survey.push(visibility=visibility).to_dict()
        else:
            initial_survey_info = None

        macro_info = Scenario(
            {
                "description": macro.description,
                "application_name": macro.application_name,
                "initial_survey_info": initial_survey_info,
                "job_info": job_info,
                "application_type": macro.application_type,
                "class_name": macro.__class__.__name__,
                "output_formatters_info": macro.output_formatters.to_dict(),
            }
        ).push(visibility=visibility, description=description, alias=alias)
        return macro_info

    @staticmethod
    def pull(macro_cls: Type, edsl_uuid: str):
        from ..surveys import Survey
        from ..jobs import Jobs
        from ..scenarios import Scenario
        from .macro import Macro

        macro_info = Scenario.pull(edsl_uuid)
        jobs_object = Jobs.pull(macro_info["job_info"]["uuid"])
        if macro_info["initial_survey_info"] is not None:
            initial_survey = Survey.pull(macro_info["initial_survey_info"]["uuid"])
        else:
            initial_survey = None
        output_formatters = OutputFormatters.from_dict(macro_info.get("output_formatters_info"))

        kwargs = {
            "jobs_object": jobs_object,
            "output_formatters": output_formatters,
            "description": macro_info.get("description"),
            "application_name": macro_info.get("application_name"),
            "initial_survey": initial_survey,
        }
        kwargs = {k: v for k, v in kwargs.items() if v is not None}

        if "initial_survey" not in kwargs or kwargs["initial_survey"] is None:
            raise ValueError("Macro.pull requires the remote Macro to include an initial_survey.")

        macro_type = macro_info.get("application_type")
        target_cls = macro_cls
        if isinstance(macro_type, str) and macro_type in Macro._registry:
            target_cls = Macro._registry[macro_type]

        return target_cls(**kwargs)


