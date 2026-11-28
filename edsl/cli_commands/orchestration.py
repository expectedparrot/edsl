"""CLI for portable respondent workflow experiments."""

from __future__ import annotations

import json
import shlex
from pathlib import Path

import click

from edsl._data_contracts import definition_fingerprint
from edsl.cli_shared import (
    EXIT_ERROR,
    EXIT_NOT_FOUND,
    EXIT_REMOTE,
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


def _state_backends(experiment, output_dir: Path, *, create: bool):
    from edsl.sharedstate import SQLiteStateBackend

    backends = {}
    for index, state_map in enumerate(experiment.states):
        path = output_dir / f"state-{index}.sqlite"
        if not create and not path.exists():
            error(
                "FILE_NOT_FOUND",
                f"State database is missing: {path}",
                suggestion="Restore the run directory from backup before continuing.",
                exit_code=EXIT_VALIDATION,
            )
        backends[state_map.state_id] = SQLiteStateBackend(
            state_map, path, runtime=experiment.runtime
        )
    return backends


def _load_humanize_run(output_dir: str, instance_id: str | None):
    from edsl.workflows import SQLiteWorkflowStore, WorkflowCoordinator

    root = Path(output_dir)
    experiment_path = root / "experiment.json"
    manifest_path = root / "run.json"
    store_path = root / "workflow.sqlite"
    for path in (experiment_path, manifest_path, store_path):
        if not path.exists():
            error(
                "FILE_NOT_FOUND",
                f"Workflow run file not found: {path}",
                suggestion="Start a Humanize workflow with 'ep orchestration start'.",
                exit_code=EXIT_NOT_FOUND,
            )
    experiment = _load_experiment(str(experiment_path))
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        error(
            "VALIDATION_ERROR",
            f"Invalid workflow run manifest: {exc}",
            exit_code=EXIT_VALIDATION,
        )
    expected_hash = definition_fingerprint(experiment.to_dict())
    if manifest.get("type") != "edsl_orchestration_run" or manifest.get("version") != 1:
        error(
            "VALIDATION_ERROR",
            "Unsupported workflow run manifest.",
            exit_code=EXIT_VALIDATION,
        )
    if manifest.get("mode") != "humanize":
        error(
            "VALIDATION_ERROR",
            "This run was not initialized for Humanize delivery.",
            exit_code=EXIT_VALIDATION,
        )
    if manifest.get("experiment_fingerprint") != expected_hash:
        error(
            "VALIDATION_ERROR",
            "The experiment file changed after this run was initialized.",
            suggestion="Restore the pinned experiment.json from the run directory backup.",
            exit_code=EXIT_VALIDATION,
        )
    stored_instance = manifest.get("instance_id")
    if instance_id is not None and instance_id != stored_instance:
        error(
            "USAGE_ERROR",
            f"Run instance is {stored_instance!r}, not {instance_id!r}.",
            exit_code=EXIT_USAGE,
        )
    instance_id = stored_instance
    store = SQLiteWorkflowStore(store_path)
    backends = _state_backends(experiment, root, create=False)
    try:
        coordinator = WorkflowCoordinator.restore(
            instance_id, store, state_backends=backends
        )
        if coordinator.workflow.to_dict() != experiment.workflow.to_dict():
            raise ValueError("workflow definition does not match the experiment file")
    except Exception as exc:
        error(
            "VALIDATION_ERROR",
            f"Could not restore workflow coordinator: {exc}",
            exit_code=EXIT_VALIDATION,
        )
    return experiment, store, coordinator, instance_id


def register(app: click.Group) -> None:
    @app.group("orchestration")
    def orchestration_group():
        """Validate and execute portable respondent workflow experiments."""

    from .workflow_item import check_item

    orchestration_group.add_command(check_item)

    @orchestration_group.command("start")
    @click.option(
        "--file", "file_path", required=True, help="Workflow experiment JSON file."
    )
    @click.option(
        "--output",
        "output_dir",
        required=True,
        type=click.Path(file_okay=False),
        help="New directory for the pinned experiment and SQLite databases.",
    )
    @click.option(
        "--instance-id",
        default="experiment",
        show_default=True,
        help="Workflow instance identifier.",
    )
    def orchestration_start(file_path, output_dir, instance_id):
        """Initialize a durable run for Humanize delivery without sending invites."""
        from edsl.workflows import SQLiteWorkflowStore, WorkflowCoordinator

        experiment = _load_experiment(file_path)
        try:
            kinds = {
                experiment.execution_plan.resolve(agent.traits).kind
                for agent in experiment.agents
            }
        except Exception as exc:
            error(
                "VALIDATION_ERROR",
                f"Invalid executor routing: {exc}",
                exit_code=EXIT_VALIDATION,
            )
        if kinds != {"human"}:
            error(
                "VALIDATION_ERROR",
                "Humanize start currently requires every participant to use the human executor.",
                suggestion="Use 'ep orchestration run' for scripted or LLM executors.",
                exit_code=EXIT_VALIDATION,
            )
        missing_email = [
            agent.name or f"participant-{index + 1}"
            for index, agent in enumerate(experiment.agents)
            if not isinstance(agent.traits.get("email"), str)
            or not agent.traits["email"].strip()
        ]
        if missing_email:
            error(
                "VALIDATION_ERROR",
                f"Humanize delivery requires an email trait; missing for: {missing_email}",
                suggestion="Add a non-empty email trait to each human participant and save the experiment again.",
                exit_code=EXIT_VALIDATION,
            )

        root = Path(output_dir)
        if root.exists() and any(root.iterdir()):
            error(
                "USAGE_ERROR",
                f"Output directory is not empty: {root}",
                suggestion="Choose a new empty output directory for this run.",
                exit_code=EXIT_USAGE,
            )
        root.mkdir(parents=True, exist_ok=True)
        try:
            experiment.save(root / "experiment.json")
            store = SQLiteWorkflowStore(root / "workflow.sqlite")
            backends = _state_backends(experiment, root, create=True)
            coordinator = WorkflowCoordinator(
                experiment.workflow, store, state_backends=backends
            )
            coordinator.launch(
                experiment.agents,
                instance_id=instance_id,
                random_seed=experiment.metadata.get("seed", instance_id),
            )
            manifest = {
                "type": "edsl_orchestration_run",
                "version": 1,
                "mode": "humanize",
                "instance_id": instance_id,
                "experiment_fingerprint": definition_fingerprint(experiment.to_dict()),
            }
            manifest_path = root / "run.json"
            temporary = manifest_path.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(manifest, indent=2) + "\n")
            temporary.replace(manifest_path)
            output(
                {
                    "instance_id": instance_id,
                    "status": store.instance_status(instance_id),
                    "output_dir": str(root),
                    "ready_items": sum(
                        item["status"] == "ready" for item in store.items(instance_id)
                    ),
                    "next_command_args": [
                        "ep",
                        "orchestration",
                        "sync",
                        "--output",
                        str(root),
                    ],
                }
            )
        except SystemExit:
            raise
        except Exception as exc:
            error(
                "RUN_ERROR",
                f"Could not start workflow: {exc}",
                suggestion="Inspect the output directory before retrying; initialization may have written run files.",
                exit_code=EXIT_ERROR,
            )

    @orchestration_group.command("status")
    @click.option(
        "--output",
        "output_dir",
        required=True,
        type=click.Path(file_okay=False, exists=True),
        help="Directory created by 'ep orchestration start'.",
    )
    @click.option("--instance-id", default=None, help="Verify the stored instance ID.")
    def orchestration_status(output_dir, instance_id):
        """Show run status, work items, and event count."""
        _, store, _, instance_id = _load_humanize_run(output_dir, instance_id)
        items = [dict(item) for item in store.items(instance_id)]
        counts = {}
        for item in items:
            counts[item["status"]] = counts.get(item["status"], 0) + 1
        output(
            {
                "instance_id": instance_id,
                "status": store.instance_status(instance_id),
                "item_counts": counts,
                "items": [
                    {
                        "id": item["id"],
                        "step": item["step_name"],
                        "participant": item["participant_id"],
                        "status": item["status"],
                    }
                    for item in items
                ],
                "event_count": len(store.events(instance_id)),
            }
        )

    @orchestration_group.command("sync")
    @click.option(
        "--output",
        "output_dir",
        required=True,
        type=click.Path(file_okay=False, exists=True),
        help="Directory created by 'ep orchestration start'.",
    )
    @click.option("--instance-id", default=None, help="Verify the stored instance ID.")
    @click.option(
        "--subject-prefix",
        default=None,
        help="Prefix for generated Humanize survey and delivery names.",
    )
    def orchestration_sync(output_dir, instance_id, subject_prefix):
        """Send ready Humanize invitations and import completed responses once."""
        from edsl.workflows import HumanizeDeliveryAdapter, OutboxDispatcher

        experiment, store, coordinator, instance_id = _load_humanize_run(
            output_dir, instance_id
        )
        try:
            adapter = HumanizeDeliveryAdapter(
                coordinator,
                subject_prefix=subject_prefix or experiment.workflow.name,
            )
            dispatcher = OutboxDispatcher(store, adapter)
            sent_before_poll = dispatcher.dispatch()
            imported = adapter.poll_completed()
            sent_after_poll = dispatcher.dispatch()
            output(
                {
                    "instance_id": instance_id,
                    "status": store.instance_status(instance_id),
                    "imported_responses": imported,
                    "deliveries": [
                        receipt.external_id
                        for receipt in (*sent_before_poll, *sent_after_poll)
                    ],
                    "pending_ready_items": sum(
                        item["status"] in {"ready", "in_progress"}
                        for item in store.items(instance_id)
                    ),
                }
            )
        except Exception as exc:
            error(
                "REMOTE_ERROR",
                f"Humanize synchronization failed: {exc}",
                suggestion="Check authentication and run status. If a delivery may have succeeded before the failure, reconcile its Humanize survey before retrying.",
                exit_code=EXIT_REMOTE,
            )

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
            check_command = ["ep", "orchestration", "check-item", str(output_dir)]
            if instance_id != "experiment":
                check_command.extend(["--instance-id", instance_id])
            check_command.extend(["--step", "STEP", "--participant", "ID"])
            data = {
                "run": result,
                "output_dir": str(output_dir),
                "completion_file": str(completion_path),
                "check_item_command": shlex.join(check_command),
            }
            warnings = []
            if responses:
                scripted = {
                    agent.name for agent in experiment.agents
                    if experiment.execution_plan.resolve(agent.traits).kind == "scripted"
                }
                ignored = sorted({row["participant"] for row in responses} & scripted)
                if ignored:
                    data["scripted_replay_participants"] = ignored
                    warnings.append(
                        "These participants use the scripted answers in the definition, even when "
                        "--responses supplies their answers. To rehearse different answers, bind "
                        "these participants to human() and supply --responses."
                    )
            output(data, warnings=warnings)
        except Exception as exc:
            error(
                "RUN_ERROR",
                f"Workflow orchestration failed: {exc}",
                suggestion="Check the experiment and replay answers. Use --resume with the same run settings only when recovering an interrupted run.",
                exit_code=EXIT_ERROR,
            )
