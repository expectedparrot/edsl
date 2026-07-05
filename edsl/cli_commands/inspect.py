"""Object inspection commands for the EDSL CLI."""

from __future__ import annotations

from pathlib import Path

import click

from edsl.cli_shared import (
    EXIT_ERROR,
    error,
    jsonable,
    load_any_object,
    output,
    save_edsl_object,
)


def register(app: click.Group) -> None:
    @app.command("inspect")
    @click.argument("target")
    @click.option("--type", "object_type", default=None, help="Expected remote object type when inspecting a UUID or URL.")
    @click.option("--sample", default=3, type=int, show_default=True, help="Number of sample rows/items to include.")
    @click.option("--save", "save_path", default=None, help="Save the inspected object to a local .ep package or serialized file.")
    def inspect_object(
        target: str,
        object_type: str | None,
        sample: int,
        save_path: str | None,
    ):
        """Inspect a local EDSL object package/file or remote object."""
        try:
            obj = load_any_object(target, expected_object_type=object_type)
            data = _summary(obj, sample=max(0, sample))
            if save_path:
                data["saved"] = save_edsl_object(obj, save_path)
            output(data)
        except SystemExit:
            raise
        except Exception as e:
            error(
                "INSPECT_ERROR",
                f"Failed to inspect object: {e}",
                suggestion="Check the path, UUID, URL, or --type value.",
                exit_code=EXIT_ERROR,
            )


def _summary(obj, sample: int) -> dict:
    class_name = type(obj).__name__
    data = {
        "object_type": class_name,
        "length": len(obj) if hasattr(obj, "__len__") else None,
    }

    if class_name == "Survey":
        questions = getattr(obj, "questions", [])
        data.update(
            {
                "question_count": len(questions),
                "question_names": list(getattr(obj, "question_names", [])),
                "question_types": [
                    getattr(q, "question_type", type(q).__name__) for q in questions
                ],
            }
        )
    elif class_name == "AgentList":
        data.update(
            {
                "agent_count": len(obj),
                "trait_keys": _agent_trait_keys(obj),
                "sample": [_agent_summary(agent) for agent in list(obj)[:sample]],
            }
        )
    elif class_name == "ScenarioList":
        data.update(
            {
                "scenario_count": len(obj),
                "keys": _scenario_keys(obj),
                "sample": [jsonable(dict(scenario)) for scenario in list(obj)[:sample]],
            }
        )
    elif class_name == "ModelList":
        data.update(
            {
                "model_count": len(obj),
                "models": [
                    {
                        "model_name": getattr(model, "model", None),
                        "service_name": getattr(model, "_inference_service_", None),
                    }
                    for model in list(obj)[:sample or len(obj)]
                ],
            }
        )
    elif class_name == "Jobs":
        survey = getattr(obj, "survey", None)
        data.update(
            {
                "question_count": len(getattr(survey, "questions", []) or []),
                "question_names": list(getattr(survey, "question_names", []) or []),
                "agent_count": _safe_len(getattr(obj, "agents", None)),
                "scenario_count": _safe_len(getattr(obj, "scenarios", None)),
                "model_count": _safe_len(getattr(obj, "models", None)),
            }
        )
    elif class_name == "Results":
        columns = sorted(getattr(obj, "columns", []) or [])
        data.update(
            {
                "result_count": len(obj),
                "columns": columns,
                "answer_columns": [c for c in columns if c.startswith("answer.")],
                "scenario_columns": [c for c in columns if c.startswith("scenario.")],
                "agent_columns": [c for c in columns if c.startswith("agent.")],
                "model_columns": [c for c in columns if c.startswith("model.")],
            }
        )
    else:
        path = Path(str(obj))
        data["repr"] = str(path) if path.exists() else repr(obj)

    return data


def _safe_len(value) -> int | None:
    try:
        return len(value) if value is not None else 0
    except TypeError:
        return None


def _agent_trait_keys(agent_list) -> list[str]:
    keys = set()
    for agent in agent_list:
        keys.update((getattr(agent, "traits", None) or {}).keys())
    return sorted(keys)


def _agent_summary(agent) -> dict:
    return {
        "name": getattr(agent, "name", None),
        "traits": jsonable(getattr(agent, "traits", {}) or {}),
    }


def _scenario_keys(scenario_list) -> list[str]:
    keys = set()
    for scenario in scenario_list:
        keys.update(dict(scenario).keys())
    return sorted(keys)
