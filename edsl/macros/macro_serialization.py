from __future__ import annotations

from typing import Any, Type

from .output_formatter import OutputFormatters


class MacroSerialization:
    @staticmethod
    def to_dict(macro: Any, add_edsl_version: bool = True) -> dict:
        # Get application_type - handle both class attribute and property
        macro_type = getattr(macro.__class__, "application_type", "base")
        if isinstance(macro_type, property):
            # If it's a property, get it from the instance
            macro_type = getattr(macro, "_application_type", "base")

        # Serialize attachment_formatters
        attachment_formatters_data = None
        if hasattr(macro, "attachment_formatters") and macro.attachment_formatters:
            attachment_formatters_data = [
                formatter.to_dict()
                if hasattr(formatter, "to_dict")
                else formatter.__dict__
                for formatter in macro.attachment_formatters
            ]

        return {
            "initial_survey": (
                macro.initial_survey.to_dict(add_edsl_version=add_edsl_version)
                if macro.initial_survey
                else None
            ),
            "jobs_object": macro.jobs_object.to_dict(add_edsl_version=add_edsl_version),
            "application_type": macro_type,
            "application_name": macro.application_name,
            "display_name": macro.display_name,
            "short_description": macro.short_description,
            "long_description": macro.long_description,
            "output_formatters": macro.output_formatters.to_dict(
                add_edsl_version=add_edsl_version
            ),
            "attachment_formatters": attachment_formatters_data,
        }

    @staticmethod
    def from_dict(macro_cls: Type, data: dict):
        from ..jobs import Jobs
        from ..surveys import Survey
        from .macro import Macro  # for registry

        # Check if this is a composite macro and dispatch accordingly
        macro_type = data.get("application_type")
        if macro_type == "composite":
            from .composite_macro import CompositeMacro

            return CompositeMacro.from_dict(data)

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
            "application_name": data.get("application_name"),
            "display_name": data.get("display_name"),
            "short_description": data.get("short_description"),
            "long_description": data.get("long_description"),
            "initial_survey": Survey.from_dict(data.get("initial_survey")),
            "jobs_object": jobs_object,
            "output_formatters": OutputFormatters.from_dict(
                data.get("output_formatters")
            ),
            "attachment_formatters": attachment_formatters,
            "client_mode": data.get("client_mode", False),
        }
        kwargs = {k: v for k, v in kwargs.items() if v is not None}

        if "initial_survey" not in kwargs or kwargs["initial_survey"] is None:
            raise ValueError("Macro.from_dict requires 'initial_survey' in data.")

        target_cls = macro_cls
        if isinstance(macro_type, str) and macro_type in Macro._registry:
            target_cls = Macro._registry[macro_type]

        return target_cls(**kwargs)
