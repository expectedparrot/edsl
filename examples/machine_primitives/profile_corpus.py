"""Development-only size/duplication/work probe; not a portable gas schedule.

Run: python -m examples.machine_primitives.profile_corpus
Measures the existing host Budget via instrumentation, without changing limits
or expression semantics. Metrics can change when interpreter accounting changes.
"""

from collections import Counter
import importlib
import json
from unittest.mock import patch

from edsl.sharedstate import Machine
from edsl.sharedstate.dsl import Expr, walk
from edsl.sharedstate.dsl_runtime import Runtime
from edsl.sharedstate.resources import Budget
from examples.machine_primitives.__main__ import EXAMPLES


def profile(name):
    module = importlib.import_module(f"examples.machine_primitives.{name}")
    machine = Machine.from_json(module.build_machine().to_json())
    machine.validate()
    expressions = Counter(
        json.dumps(node.to_dict(), sort_keys=True, separators=(",", ":"))
        for node in walk(machine)
        if isinstance(node, Expr)
    )
    budgets = []

    class CapturedBudget(Budget):
        def __init__(self, limits):
            super().__init__(limits)
            budgets.append(self)

    runtime = Runtime()
    state = runtime.initial_state(machine)
    transitions = []
    for command, inputs in module.DEMO:
        with patch("edsl.sharedstate.resources.Budget", CapturedBudget):
            result = (
                runtime.close_result(machine, state)
                if command == "$close"
                else runtime.execute(machine, state, command, inputs)
            )
        state = result.state
        transitions.append(
            {
                "command": command,
                "status": result.event["status"],
                "budget_steps": budgets[-1].steps,
            }
        )
    repeated = sorted(
        ((count, encoded) for encoded, count in expressions.items() if count > 1),
        reverse=True,
    )
    return {
        "definition_bytes": len(machine.to_json().encode("utf-8")),
        "expression_occurrences": sum(expressions.values()),
        "distinct_expression_trees": len(expressions),
        "repeated_occurrences": sum(count - 1 for count in expressions.values()),
        "most_repeated": [
            {"occurrences": count, "expression": json.loads(encoded)}
            for count, encoded in repeated[:3]
        ],
        "transitions": transitions,
        "max_transition_budget_steps": max(
            (r["budget_steps"] for r in transitions), default=0
        ),
    }


if __name__ == "__main__":
    print(json.dumps({name: profile(name) for name in EXAMPLES}, indent=2))
