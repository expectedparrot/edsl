"""Run the paper's CSQA example through the local EDSL/OpenAI pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from edsl import Model
from edsl.sharedstate import SQLiteStateBackend
from edsl.sharedstate.model import resolve_read
from edsl.sharedstate.steps import StepContext
from edsl.workflows import (
    EDSLAgentAnswerer,
    SQLiteWorkflowStore,
    WorkflowCoordinator,
    WorkflowSimulation,
)

from .debate_experiment import (
    EXAMPLE_ITEM,
    analyze_responses,
    build_debate_workflow,
    build_debaters,
)


def run(output_dir: Path, model_name: str = "gpt-4o-mini") -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    databases = (output_dir / "workflow.sqlite", output_dir / "shared-state.sqlite")
    if any(path.exists() for path in databases):
        raise FileExistsError(
            f"pilot output directory already contains execution state: {output_dir}; "
            "choose a fresh directory to avoid mixing runs"
        )
    workflow, state = build_debate_workflow(EXAMPLE_ITEM)
    agents = build_debaters(("gpt", "gpt", "gpt"))
    workflow_store = SQLiteWorkflowStore(databases[0])
    state_backend = SQLiteStateBackend(state, databases[1])
    coordinator = WorkflowCoordinator(
        workflow,
        workflow_store,
        state_backends={state.state_id: state_backend},
    )
    instance_id = coordinator.launch(agents, instance_id="csqa-gpt-4o-mini-pilot")
    answerer = EDSLAgentAnswerer(
        Model(model_name),
        run_options={
            "disable_remote_inference": True,
            "disable_remote_cache": True,
            "cache": False,
            "stop_on_exceptions": True,
        },
    )
    WorkflowSimulation(
        coordinator,
        {agent.name: agent for agent in agents},
        answerer,
    ).run(instance_id)

    ledger = state.by(EXAMPLE_ITEM.item_id).debate
    observed = state_backend.read(
        resolve_read(ledger.read(), StepContext({}, "pilot-summary"))
    )
    responses = observed.value["responses"]
    summary = {
        "instance_id": instance_id,
        "model": model_name,
        "item": EXAMPLE_ITEM.to_dict(),
        "analysis": analyze_responses(responses, EXAMPLE_ITEM.correct_answer),
        "responses": responses,
        "workflow_events": workflow_store.events(instance_id),
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", default="gpt-4o-mini")
    args = parser.parse_args()
    print(run(args.output_dir, args.model))
