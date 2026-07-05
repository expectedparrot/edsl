"""Schema inspection commands for the EDSL CLI."""

from __future__ import annotations

import click

from edsl.cli_shared import EXIT_ERROR, EXIT_NOT_FOUND, EXIT_USAGE, error, output


def register(schema: click.Group) -> None:
    # ---------------------------------------------------------------------------
    # ep schema
    # ---------------------------------------------------------------------------

    def _get_schema_classes():
        """Return a map of schema names to (class, description) for all introspectable types."""
        from edsl.agents import Agent, AgentList
        from edsl.scenarios import Scenario, ScenarioList
        from edsl.surveys import Survey
        from edsl.language_models import Model
        from edsl.language_models.model_list import ModelList
        from edsl.jobs import Jobs
        from edsl.results import Results
        from edsl.questions.register_questions_meta import RegisterQuestionsMeta

        # Force import of question types

        classes = {
            "Agent": (Agent, "A respondent with traits and optional instructions."),
            "AgentList": (AgentList, "A list of Agent objects. Pass to 'ep run --agent_list'."),
            "Scenario": (Scenario, "Template parameters for questions using Jinja2 {{variable}} syntax."),
            "ScenarioList": (ScenarioList, "A list of Scenario objects. Pass to 'ep run --scenario_list'."),
            "Survey": (Survey, "A collection of questions with optional flow logic."),
            "Model": (Model, "An LLM configuration. Pass to 'ep run --model'."),
            "ModelList": (ModelList, "A list of Model objects. Pass to 'ep run --model_list'."),
            "Jobs": (Jobs, "A complete job spec (survey + agents + models + scenarios). Pass to 'ep run --jobs'."),
            "Results": (Results, "Output from a job run. Pass to 'ep results select --file'."),
        }

        # Add question types
        type_map = RegisterQuestionsMeta.question_types_to_classes()
        for qtype, cls in sorted(type_map.items()):
            classes[qtype] = (cls, f"Question type '{qtype}'.")

        return classes


    @schema.command("list")
    def schema_list():
        """List all types available for schema introspection.

        \b
        Examples:
          ep schema list
          ep schema show --class Survey
          ep schema show --question_type free_text
        """
        classes = _get_schema_classes()

        object_types = []
        question_types = []
        for name, (cls, desc) in classes.items():
            entry = {"name": name, "description": desc}
            if name[0].isupper():
                object_types.append(entry)
            else:
                question_types.append(entry)

        output({"object_types": object_types, "question_types": question_types})


    @schema.command("show")
    @click.option("--class", "class_name", default=None, help="EDSL class to inspect (e.g. Agent, ScenarioList, Survey, Jobs).")
    @click.option("--question_type", default=None, help="Question type to inspect (e.g. free_text, multiple_choice).")
    def schema_show(class_name, question_type):
        """Show the serialized schema of an EDSL type via its .example().to_dict().

        \b
        Examples:
          ep schema show --class Survey
          ep schema show --class AgentList
          ep schema show --class Jobs
          ep schema show --question_type multiple_choice
          ep schema show --question_type free_text
        """
        if class_name and question_type:
            error("USAGE_ERROR", "--class and --question_type are mutually exclusive.",
                   exit_code=EXIT_USAGE)
        if not class_name and not question_type:
            error("USAGE_ERROR", "Provide one of --class or --question_type.",
                   suggestion="Use 'ep schema list' to see available types.",
                   exit_code=EXIT_USAGE)

        classes = _get_schema_classes()
        schema_type = class_name or question_type

        if schema_type not in classes:
            # Suggest from the right category
            if class_name:
                available = sorted(n for n in classes if n[0].isupper())
            else:
                available = sorted(n for n in classes if n[0].islower())
            error("NOT_FOUND", f"Unknown type: '{schema_type}'",
                   suggestion=f"Available: {', '.join(available)}",
                   exit_code=EXIT_NOT_FOUND)

        cls, desc = classes[schema_type]

        try:
            example = cls.example()
            serialized = example.to_dict()
        except Exception as e:
            error("RUN_ERROR", f"Failed to generate example for '{schema_type}': {e}",
                   exit_code=EXIT_ERROR)

        output({
            "type": schema_type,
            "description": desc,
            "example": serialized,
        })


    @schema.command("error")
    def schema_error():
        """Documents the error envelope and all known error codes.

        \b
        Examples:
          ep schema error
          ep validate --file survey.json --type Survey
        """
        output({
            "envelope": {
                "status": "error",
                "error": {
                    "code": "string — error code",
                    "message": "string — human-readable description",
                    "suggestion": "string — what to do next (optional)",
                    "details": "array — detailed sub-errors for validation (optional)",
                },
            },
            "exit_codes": {
                "0": "Success",
                "1": "General error",
                "2": "Usage error (bad arguments, conflicting flags)",
                "3": "Resource not found",
                "4": "Authentication error",
                "5": "Validation error",
                "6": "Remote service error",
            },
            "known_error_codes": [
                "FILE_NOT_FOUND", "INVALID_JSON", "USAGE_ERROR",
                "UNKNOWN_QUESTION_TYPE", "INVALID_MODEL", "MODEL_LIST_ERROR",
                "AUTH_TIMEOUT", "AUTH_ERROR",
                "VALIDATION_ERROR", "RUN_ERROR",
                "COOP_ERROR", "BALANCE_ERROR", "AUTH_REQUIRED", "NOT_FOUND",
                "CONFIRMATION_REQUIRED", "DELETE_ERROR", "DEPENDENCY_ERROR",
                "HUMANIZE_ERROR", "JOBS_ERROR", "METADATA_ERROR", "PROFILE_ERROR",
                "RESULTS_NOT_AVAILABLE", "SEARCH_ERROR", "SETTINGS_ERROR",
                "SHARE_ERROR", "UNSUPPORTED_OBJECT",
            ],
        })
