"""Run and export the corpus without model calls: python -m examples.machine_primitives."""

import argparse
import importlib
import json
from pathlib import Path

from edsl.sharedstate import Machine
from edsl.sharedstate.dsl import Effect, Expr, walk
from edsl.sharedstate.dsl_runtime import Runtime

EXAMPLES = (
    "running_ledger",
    "serial_dictatorship",
    "deferred_acceptance",
    "double_auction",
    "binary_market",
    "batch_auction",
    "seeded_allocation",
    "monetary_settlement",
    "survey_quota",
    "reason_discovery",
    "question_coverage",
)


# Keep domain-specific reducers out too: an empty algorithm registry alone
# would not detect a built-in such as ranked_ballot_results.
GENERAL_REDUCERS = {"sort_records", "latest_by", "sum", "count_by"}


def run_example(name):
    module = importlib.import_module(f"examples.machine_primitives.{name}")
    machine = module.build_machine()
    # Execute the transported definition, not the original authoring objects.
    payload = json.loads(machine.to_json())
    machine = Machine.from_dict(payload)
    machine.validate()
    assert not machine.algorithms
    assert not any(
        isinstance(node, (Expr, Effect)) and node.op in {"algorithm", "algorithm_view"}
        for node in walk(machine)
    )
    assert all(
        node.args[0] in GENERAL_REDUCERS
        for node in walk(machine)
        if isinstance(node, Expr) and node.op == "reduce"
    )
    runtime = Runtime()  # Empty registry: examples cannot silently use built-ins.
    state = runtime.initial_state(machine)
    decisions = []
    for command, inputs in module.DEMO:
        result = (
            runtime.close_result(machine, state)
            if command == "$close"
            else runtime.execute(machine, state, command, inputs)
        )
        state = result.state
        decisions.append(
            {
                "command": command,
                "status": result.event["status"],
                "reason_code": result.event["reason_code"],
                "changed": result.event["changed"],
            }
        )
    return {
        "operations": sorted(
            {node.op for node in walk(machine) if isinstance(node, (Expr, Effect))}
        ),
        "capabilities": machine.required_capabilities(),
        "definition_bytes": len(machine.to_json().encode()),
        "definition": payload,
        "commands": module.DEMO,
        "decisions": decisions,
        "state": state,
        "view": runtime.render_view(machine, state, closed=True),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional directory for portable definitions and replay records",
    )
    args = parser.parse_args()
    report = {}
    for name in EXAMPLES:
        result = run_example(name)
        report[name] = result["view"]
        if args.output:
            args.output.mkdir(parents=True, exist_ok=True)
            (args.output / f"{name}.machine.json").write_text(
                json.dumps(result["definition"], indent=2) + "\n"
            )
            (args.output / f"{name}.replay.json").write_text(
                json.dumps(result, indent=2) + "\n"
            )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
