"""CLI for portable respondent workflow experiments."""

from __future__ import annotations

import json
from pathlib import Path

import click

from edsl.cli_shared import (
    EXIT_ERROR,
    EXIT_USAGE,
    EXIT_VALIDATION,
    error,
    output,
    read_json_file,
)


def _load_experiment(file_path: str):
    from edsl.workflows import WorkflowExperiment

    payload = read_json_file(file_path)
    try:
        experiment = WorkflowExperiment.from_dict(payload)
        experiment.validate()
        return experiment
    except Exception as exc:
        error(
            "VALIDATION_ERROR",
            f"Invalid workflow experiment: {exc}",
            suggestion="Check the workflow experiment JSON and use 'ep orchestration validate --file <path>'.",
            exit_code=EXIT_VALIDATION,
        )


def register(app: click.Group) -> None:
    @app.group("orchestration")
    def orchestration_group():
        """Validate and execute portable respondent workflow experiments."""

    @orchestration_group.command("validate")
    @click.option(
        "--file", "file_path", required=True, help="Workflow experiment JSON file."
    )
    def orchestration_validate(file_path):
        """Validate a portable workflow, participant, state, and executor bundle."""
        experiment = _load_experiment(file_path)
        output(
            {
                "valid": True,
                "name": experiment.workflow.name,
                "steps": len(experiment.workflow.steps),
                "participants": len(experiment.agents),
                "state_maps": len(experiment.states),
                "executor_bindings": len(experiment.execution_plan.bindings),
            }
        )

    @orchestration_group.command("inspect")
    @click.option(
        "--file", "file_path", required=True, help="Workflow experiment JSON file."
    )
    def orchestration_inspect(file_path):
        """Summarize the steps, assignments, and executors in an experiment."""
        experiment = _load_experiment(file_path)
        output(
            {
                "name": experiment.workflow.name,
                "metadata": experiment.metadata,
                "participants": [
                    {"name": agent.name, "traits": agent.traits}
                    for agent in experiment.agents
                ],
                "steps": [
                    {
                        "name": step.name,
                        "questions": [
                            question.question_name for question in step.survey.questions
                        ],
                        "after": list(step.after),
                        "settled_after": list(step.settled_after),
                        "assignee": step.assignee.to_dict(),
                        "completion": step.completion.to_dict(),
                        "has_condition": step.enabled_when is not None,
                    }
                    for step in experiment.workflow.steps
                ],
                "state_maps": [state.state_id for state in experiment.states],
                "executors": [
                    {
                        "selector": binding.selector.to_dict(),
                        "executor": binding.executor.to_dict(),
                    }
                    for binding in experiment.execution_plan.bindings
                ],
            }
        )

    @orchestration_group.command("run")
    @click.option(
        "--file", "file_path", required=True, help="Workflow experiment JSON file."
    )
    @click.option(
        "--output",
        "output_dir",
        required=True,
        type=click.Path(file_okay=False),
        help="Directory for the durable workflow run and SQLite state files.",
    )
    @click.option(
        "--responses",
        "responses_path",
        type=click.Path(exists=True, dir_okay=False),
        help="Replay answers from a JSON list; supplying this prevents model calls.",
    )
    @click.option(
        "--resume", is_flag=True, help="Recover and continue an existing run."
    )
    @click.option(
        "--instance-id",
        default="experiment",
        show_default=True,
        help="Workflow instance identifier.",
    )
    def orchestration_run(file_path, output_dir, responses_path, resume, instance_id):
        """Run or resume an experiment; configured LLM executors may call providers."""
        experiment = _load_experiment(file_path)
        responses = None
        if responses_path:
            responses = read_json_file(responses_path)
            if isinstance(responses, dict):
                responses = responses.get("responses")
            if not isinstance(responses, list):
                error(
                    "USAGE_ERROR",
                    "Replay responses must be a JSON array or an object with a responses array.",
                    exit_code=EXIT_USAGE,
                )
        try:
            result = experiment.run(
                output_dir,
                responses=responses,
                resume=resume,
                instance_id=instance_id,
            )
            completion_path = Path(output_dir) / "completion.json"
            completion_path.write_text(json.dumps(result, indent=2) + "\n")
            output(
                {
                    "run": result,
                    "output_dir": str(output_dir),
                    "completion_file": str(completion_path),
                }
            )
        except Exception as exc:
            error(
                "RUN_ERROR",
                f"Workflow orchestration failed: {exc}",
                suggestion="Inspect the run directory and use --resume to recover an interrupted run.",
                exit_code=EXIT_ERROR,
            )
