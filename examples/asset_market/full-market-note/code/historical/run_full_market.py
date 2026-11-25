"""Run a fresh native 30-round market, with no observation pauses.

python -m examples.asset_market.run_full_market --output runs/new-market
Use --resume only to recover an interrupted execution from its pinned JSON.
"""

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path

from dotenv import load_dotenv
from edsl.sharedstate import SQLiteStateBackend
from edsl.workflows import WorkflowExperiment


def prepare():
    from .portable import build

    pilot = build()
    workflow = replace(
        pilot.workflow,
        name="Speculative asset market: full 30-round session",
        pause_rules=(),
        metadata={
            **pilot.workflow.metadata,
            "observation_design": "Full 30 rounds fixed before execution; no early observation pauses.",
        },
    )
    return WorkflowExperiment(
        workflow,
        pilot.states,
        pilot.agents,
        pilot.execution_plan,
        metadata={
            "seed": pilot.metadata["seed"],
            "prompt_variant": "speculative-v1",
            "economic_horizon": 30,
            "observation_horizon": 30,
            "fresh_model_calls": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    specification = args.output / ("experiment.json" if args.resume else "specification.json")
    if args.prepare_only:
        args.output.mkdir(parents=True, exist_ok=True)
        if specification.exists():
            raise FileExistsError(specification)
        prepare().save(specification)
        print(json.dumps({"status": "ok", "prepared": str(specification)}))
        return
    load_dotenv()
    experiment = (
        WorkflowExperiment.load(specification) if specification.exists() else prepare()
    )
    result = experiment.run(args.output, resume=args.resume)
    (args.output / "completion.json").write_text(json.dumps(result, indent=2) + "\n")
    state = (
        SQLiteStateBackend(experiment.states[0], args.output / "state-0.sqlite")
        .snapshot("session")
        .state["market"]
    )
    (args.output / "market.json").write_text(json.dumps(state, indent=2) + "\n")
    assert result["status"] == "completed" and result["completed_items"] == 390
    assert state["finished"] and len(state["tape"]) == 30
    assert len(state["order_log"]) == 360
    assert all(a["shares"] == 0 for a in state["accounts"].values())
    print(json.dumps({"status": "ok", "data": result, "warnings": []}))


if __name__ == "__main__":
    main()
