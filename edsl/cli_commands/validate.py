"""Validation command for the EDSL CLI."""

from __future__ import annotations

import json
import sys
from typing import Optional

import click

from edsl.cli_shared import EXIT_USAGE, EXIT_VALIDATION, error, output, read_json_file


def register(app: click.Group) -> None:
    # ---------------------------------------------------------------------------
    # ep validate
    # ---------------------------------------------------------------------------

    @app.command()
    @click.option("--file", "file_path", default=None, help="Path to JSON file to validate.")
    @click.option("--json", "--json_data", "json_data", default=None, help="Inline JSON string.")
    @click.option("--type", "force_type", default=None, help="Force validation as type.")
    def validate(file_path, json_data, force_type):
        """Validate a question, survey, or job spec without executing."""
        raw = None
        if file_path:
            raw = read_json_file(file_path)
        elif json_data:
            try:
                raw = json.loads(json_data)
            except json.JSONDecodeError as e:
                error("INVALID_JSON", f"Failed to parse JSON: {e}",
                       exit_code=EXIT_USAGE)
        else:
            stdin_data = read_stdin()
            if stdin_data:
                try:
                    raw = json.loads(stdin_data)
                except json.JSONDecodeError as e:
                    error("INVALID_JSON", f"Failed to parse JSON from stdin: {e}",
                           exit_code=EXIT_USAGE)

        if raw is None:
            error("USAGE_ERROR", "No input provided.",
                   suggestion="Use --file, --json_data, or pipe JSON via stdin.",
                   exit_code=EXIT_USAGE)

        warnings_list = []

        # Detect object type
        obj_type = force_type
        if not obj_type:
            if "survey" in raw and isinstance(raw.get("survey"), dict):
                obj_type = "job"
            elif "questions" in raw and isinstance(raw.get("questions"), list):
                obj_type = "job_lightweight"
            elif "type" in raw and "question_text" in raw:
                obj_type = "question"
            else:
                obj_type = "unknown"

        try:
            if obj_type == "question":
                normalized = _validate_question(raw, warnings_list)
                output({"valid": True, "object_type": "question", "normalized": normalized}, warnings=warnings_list)
            elif obj_type == "job":
                from edsl.jobs import Jobs
                Jobs.from_dict(raw)
                output({"valid": True, "object_type": "job", "normalized": raw}, warnings=warnings_list)
            elif obj_type == "job_lightweight":
                _validate_lightweight_job(raw, warnings_list)
                output({"valid": True, "object_type": "job_lightweight", "normalized": raw}, warnings=warnings_list)
            elif obj_type == "survey":
                from edsl.surveys import Survey
                Survey.from_dict(raw)
                output({"valid": True, "object_type": "survey", "normalized": raw}, warnings=warnings_list)
            elif obj_type == "agent_list":
                from edsl.agents import AgentList
                AgentList.from_dict(raw)
                output({"valid": True, "object_type": "agent_list", "normalized": raw}, warnings=warnings_list)
            elif obj_type == "scenario_list":
                from edsl.scenarios import ScenarioList
                ScenarioList.from_dict(raw)
                output({"valid": True, "object_type": "scenario_list", "normalized": raw}, warnings=warnings_list)
            else:
                error("VALIDATION_ERROR", "Could not determine object type from input.",
                       suggestion="Use --type to specify: question, survey, job, agent_list, scenario_list.",
                       exit_code=EXIT_VALIDATION)
        except SystemExit:
            raise
        except Exception as e:
            error("VALIDATION_ERROR", f"Input failed validation: {e}",
                   suggestion="Check the input against 'ep schema' output.",
                   exit_code=EXIT_VALIDATION)


    def _validate_question(raw: dict, warnings_list: list) -> dict:
        """Validate and normalize a single question dict."""
        from edsl.questions.register_questions_meta import RegisterQuestionsMeta


        qtype = raw.get("type", raw.get("question_type", "free_text"))
        type_map = RegisterQuestionsMeta.question_types_to_classes()

        if qtype not in type_map:
            error("VALIDATION_ERROR", f"Unknown question type: '{qtype}'",
                   suggestion=f"Available: {', '.join(sorted(type_map.keys()))}",
                   exit_code=EXIT_VALIDATION)

        if "question_name" not in raw:
            raw["question_name"] = "q0"
            warnings_list.append({
                "code": "AUTO_GENERATED_NAME",
                "message": "question_name was omitted and set to 'q0'",
            })

        kwargs = {k: v for k, v in raw.items() if k not in ("type", "question_type")}

        cls = type_map[qtype]
        q = cls(**kwargs)
        normalized = {"type": qtype, **{k: v for k, v in raw.items() if k != "type" and k != "question_type"}}
        return normalized


    def _validate_lightweight_job(raw: dict, warnings_list: list) -> None:
        """Validate a lightweight job spec."""
        questions = raw.get("questions", [])
        if not questions:
            error("VALIDATION_ERROR", "Job spec has empty 'questions' array.",
                   exit_code=EXIT_VALIDATION)

        for i, q in enumerate(questions):
            if "question_text" not in q:
                error("VALIDATION_ERROR",
                       f"questions[{i}] missing 'question_text'.",
                       exit_code=EXIT_VALIDATION)
            if "question_name" not in q:
                q["question_name"] = f"q{i}"
                warnings_list.append({
                    "code": "AUTO_GENERATED_NAME",
                    "message": f"questions[{i}].question_name was omitted and set to 'q{i}'",
                })






    def read_stdin() -> Optional[str]:
        if sys.stdin.isatty():
            return None
        return sys.stdin.read()
