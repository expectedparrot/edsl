"""Authoring and local simulation commands for shared-state machines."""

from __future__ import annotations

import click

from edsl.cli_shared import (
    EXIT_ERROR,
    EXIT_NOT_FOUND,
    EXIT_USAGE,
    EXIT_VALIDATION,
    error,
    load_results_object,
    output,
    read_json_file,
)


def _load_machine(path: str):
    from edsl.sharedstate import Machine

    payload = read_json_file(path)
    try:
        machine = Machine.from_dict(payload)
        machine.validate()
        return machine
    except Exception as exc:
        error(
            "VALIDATION_ERROR",
            f"Invalid machine definition: {exc}",
            suggestion="Check the serialized Machine format and run 'ep state validate --file <path>'.",
            exit_code=EXIT_VALIDATION,
        )


def register(app: click.Group, results: click.Group) -> None:
    @app.group("state")
    def state_group():
        """Validate, inspect, and simulate serialized shared-state machines."""

    @state_group.command("validate")
    @click.option(
        "--file",
        "file_path",
        required=True,
        help="Serialized Machine JSON file, or - for stdin.",
    )
    def state_validate(file_path):
        """Validate a serialized state machine definition."""
        machine = _load_machine(file_path)
        from edsl.sharedstate.dsl_runtime import Runtime

        data = {
            "valid": True,
            "name": machine.name,
            "fields": sorted(machine.fields),
            "commands": sorted(machine.commands),
            "required_capabilities": machine.required_capabilities(),
        }
        try:
            runtime = Runtime()
            initial = runtime.initial_state(machine)
            data["locally_executable"] = True
            data["initial_state"] = initial
            data["initial_view"] = runtime.render_view(machine, initial)
        except Exception as exc:
            data["locally_executable"] = False
            data["execution_error"] = str(exc)
        output(data)

    @state_group.command("inspect")
    @click.option(
        "--file",
        "file_path",
        required=True,
        help="Serialized Machine JSON file, or - for stdin.",
    )
    def state_inspect(file_path):
        """Summarize a machine definition and its available commands."""
        machine = _load_machine(file_path)
        output(
            {
                "name": machine.name,
                "version": 1,
                "constants": machine.constants,
                "fields": machine.to_dict()["fields"],
                "commands": {
                    name: {
                        "inputs": sorted(command.inputs),
                        "effects": len(command.effects),
                        "timing": command.timing,
                        "requires_condition": command.require is not None,
                    }
                    for name, command in machine.commands.items()
                },
                "view_fields": sorted(machine.view),
                "has_completion_condition": machine.complete_when is not None,
                "close_effects": len(machine.close_effects),
                "algorithms": list(machine.algorithms),
                "required_capabilities": machine.required_capabilities(),
            }
        )

    @state_group.command("simulate")
    @click.option(
        "--file", "file_path", required=True, help="Serialized Machine JSON file."
    )
    @click.option(
        "--transitions",
        required=True,
        type=click.Path(),
        help="JSON array of {command, inputs} transitions.",
    )
    def state_simulate(file_path, transitions):
        """Run transitions against a machine locally and return each state/view."""
        machine = _load_machine(file_path)
        transition_data = read_json_file(transitions)
        if isinstance(transition_data, dict):
            transition_data = transition_data.get("transitions")
        if not isinstance(transition_data, list):
            error(
                "USAGE_ERROR",
                "Transitions must be a JSON array or an object with a transitions array.",
                exit_code=EXIT_USAGE,
            )

        from edsl.sharedstate.dsl_runtime import Runtime

        runtime = Runtime()
        try:
            state = runtime.initial_state(machine)
            steps = []
            for index, transition in enumerate(transition_data):
                if not isinstance(transition, dict) or not isinstance(
                    transition.get("command"), str
                ):
                    error(
                        "USAGE_ERROR",
                        f"Transition {index} must contain a command string and inputs object.",
                        exit_code=EXIT_USAGE,
                    )
                inputs = transition.get("inputs", {})
                if not isinstance(inputs, dict):
                    error(
                        "USAGE_ERROR",
                        f"Transition {index} inputs must be an object.",
                        exit_code=EXIT_USAGE,
                    )
                result = runtime.execute(
                    machine,
                    state,
                    transition["command"],
                    inputs,
                    current=transition.get("current"),
                )
                state = result.state
                steps.append(
                    {
                        "index": index,
                        "event": result.event,
                        "state": state,
                        "view": runtime.render_view(
                            machine, state, current=transition.get("current")
                        ),
                        "complete": runtime.complete(machine, state),
                    }
                )
            output(
                {
                    "machine": machine.name,
                    "initial_state": runtime.initial_state(machine),
                    "steps": steps,
                    "final_state": state,
                }
            )
        except SystemExit:
            raise
        except Exception as exc:
            error(
                "VALIDATION_ERROR",
                f"Simulation failed: {exc}",
                exit_code=EXIT_VALIDATION,
            )

    @results.command("state")
    @click.option(
        "--file", "file_path", required=True, help="Results .ep, JSON, or JSON.gz file."
    )
    @click.option(
        "--binding",
        type=int,
        default=None,
        help="Return one shared-state binding by zero-based index.",
    )
    def results_state(file_path, binding):
        """Inspect shared-state bindings and snapshots stored in Results."""
        try:
            result = load_results_object(file_path)
        except Exception as exc:
            error(
                "VALIDATION_ERROR",
                f"Failed to load Results: {exc}",
                exit_code=EXIT_ERROR,
            )
        shared_state = result.shared_state
        if not shared_state:
            error(
                "NOT_FOUND",
                "Results contain no shared-state data.",
                suggestion="Run a Jobs package configured with shared state and save the resulting Results.",
                exit_code=EXIT_NOT_FOUND,
            )
        bindings = (
            shared_state.get("bindings", []) if isinstance(shared_state, dict) else []
        )
        if binding is not None:
            if binding < 0 or binding >= len(bindings):
                error(
                    "NOT_FOUND",
                    f"Shared-state binding index {binding} is out of range.",
                    suggestion=f"Available bindings: 0 through {max(0, len(bindings) - 1)}.",
                    exit_code=EXIT_NOT_FOUND,
                )
            output({"binding_index": binding, "binding": bindings[binding]})
        else:
            output({"binding_count": len(bindings), "shared_state": shared_state})
