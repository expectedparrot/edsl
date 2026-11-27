"""Replay brief-derived expectations against a local Survey's routing rules."""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from edsl.cli_shared import EXIT_USAGE, EXIT_VALIDATION, error, output
from edsl.surveys.base import EndOfSurvey


class PathCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    expected_path: list[str]
    answers: dict[str, Any] = Field(default_factory=dict)
    scenario: dict[str, Any] = Field(default_factory=dict)
    agent: dict[str, Any] = Field(default_factory=dict)


class PathSuite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cases: list[PathCase] = Field(min_length=1)


def _replay(survey, case, routing_inputs):
    context = {f"scenario.{k}": v for k, v in case.scenario.items()}
    context.update({f"agent.{k}": v for k, v in case.agent.items()})
    visited = []
    record = {"name": case.name, "passed": False, "visited": visited}

    unknown = case.answers.keys() - set(survey.question_names) - set(case.expected_path)
    if unknown:
        return {
            **record,
            "message": f"Unknown answer keys: {', '.join(sorted(unknown))}.",
        }

    try:
        question = survey.next_question()
        if (
            question != EndOfSurvey
            and survey.rule_collection.skip_question_before_running(0, context)
        ):
            question = survey.next_question(question, context)

        # Compare the end as a final step; a matching prefix alone cannot pass.
        for expected in [*case.expected_path, None]:
            actual = None if question == EndOfSurvey else question.question_name
            previous = visited[-1] if visited else None
            if actual is not None:
                visited.append(actual)
            if actual != expected:
                location = (
                    f"after {previous!r}" if previous is not None else "at the start"
                )
                message = f"{location}, expected {expected or 'end of survey'!r}, got {actual or 'end of survey'!r}."
                return {
                    **record,
                    "after": previous,
                    "expected": expected,
                    "actual": actual,
                    "message": message,
                }
            if actual is None:
                break
            if actual in case.answers:
                context[f"{actual}.answer"] = case.answers[actual]
            elif actual in routing_inputs:
                return {
                    **record,
                    "message": f"Supply an answer for routing input {actual!r}.",
                }
            question = survey.next_question(question, context)
    except Exception as exc:
        return {
            **record,
            "message": f"Could not evaluate routing after {visited}: {exc}",
        }
    return {**record, "passed": True}


def check_question_paths(survey, cases_path: Path):
    """Check every named case and emit the CLI's JSON result."""
    try:
        raw = json.loads(cases_path.read_text(encoding="utf-8"))
        suite = PathSuite.model_validate(raw)
    except ValidationError as exc:
        error(
            "INVALID_PATH_CASES",
            "Invalid question path cases.",
            "Check the cases file against the example in --help.",
            EXIT_USAGE,
            details=exc.errors(include_input=False, include_url=False),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        error(
            "INVALID_PATH_CASES",
            str(exc),
            "Provide a readable UTF-8 JSON file.",
            EXIT_USAGE,
        )

    if survey.question_order.get("blocks") or survey.question_sampling:
        error(
            "UNSUPPORTED_ROUTING",
            "The survey assigns randomized question order or samples questions.",
            "Use check-paths for fixed-order, question-level routing.",
            EXIT_USAGE,
        )

    names = survey.question_names
    routing_inputs = {
        names[index]
        for rule in survey.rule_collection
        for index in rule.named_questions_by_index
    }
    checked = [_replay(survey, case, routing_inputs) for case in suite.cases]
    failures = [case for case in checked if not case["passed"]]
    if failures:
        first = failures[0]
        error(
            "PATH_CHECK_FAILED",
            f"{len(failures)} of {len(checked)} cases failed. {first['name']}: {first['message']}",
            "Compare the saved rules with the expected paths, then rerun all cases.",
            EXIT_VALIDATION,
            details=failures,
        )
    output({"passed": len(checked), "cases": checked})
