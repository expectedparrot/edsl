"""Run and analyze the published 405-cell mug-negotiation design.

This is a design replication with a contemporary named model, not a claim that
the unavailable April 2024 GPT-4 snapshot and prompt stack are reproduced.
Runs are durable per cell and safe to resume.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Lock
from typing import Any

from edsl import Model
from edsl.causal import CausalExperimentRunner, EDSLCausalAdapter
from edsl.conversations import SQLiteConversationStore

from examples.automated_social_science.mug_causal_spec import (
    build_compiled_original_mug_experiment,
)


PAPER_BENCHMARK = {
    "n": 405,
    "deal_rate": 0.50,
    "coefficients": {
        "buyer_budget": 0.037,
        "seller_minimum_price": -0.035,
        "seller_attachment": -0.025,
    },
    "standard_errors": {
        "buyer_budget": 0.003,
        "seller_minimum_price": 0.002,
        "seller_attachment": 0.012,
    },
}


def _write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def run_cell(replication, compiled, conversation, root: Path, model_name: str, service: str):
    cell_root = root / "cells" / replication.cell_id
    cell_root.mkdir(parents=True, exist_ok=True)
    observation_path = cell_root / "observation.json"
    if observation_path.exists():
        return json.loads(observation_path.read_text()), True

    adapter = EDSLCausalAdapter(Model(model_name, service_name=service))
    store = SQLiteConversationStore(cell_root / "conversation.sqlite")
    runner = CausalExperimentRunner(
        compiled,
        conversation,
        store,
        speakers={"buyer": adapter.speak, "seller": adapter.speak},
        semantic_judge=adapter.judge,
        measurers={"deal_occurred": adapter.measure},
    )
    observation = runner.run(replication).to_dict()
    _write_json(observation_path, observation)
    _write_json(cell_root / "transcript.json", store.transcript(replication.instance_id))
    _write_json(cell_root / "provenance.json", adapter.provenance())
    return observation, False


def analyze(root: Path, plan, *, model_name: str, service: str) -> dict[str, Any]:
    observations = [
        json.loads(path.read_text())
        for path in sorted((root / "cells").glob("*/observation.json"))
    ]
    rows = [item["values"] for item in observations]
    fitted = plan.fit(rows)
    equation = fitted.equations[0]
    deal_rate = sum(row["deal_occurred"] for row in rows) / len(rows)
    turn_counts = [item["transcript_version"] for item in observations]
    result = {
        "status": "complete" if len(rows) == PAPER_BENCHMARK["n"] else "partial",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": {"name": model_name, "service": service},
        "design": {"completed": len(rows), "expected": PAPER_BENCHMARK["n"]},
        "outcomes": {
            "deal_rate": deal_rate,
            "deals": sum(row["deal_occurred"] for row in rows),
            "mean_turns": sum(turn_counts) / len(turn_counts),
            "minimum_turns": min(turn_counts),
            "maximum_turns": max(turn_counts),
        },
        "fit": fitted.to_dict(),
        "paper_benchmark": PAPER_BENCHMARK,
    }
    _write_json(root / "results.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("examples/automated_social_science/runs/mug-original-replication"))
    parser.add_argument("--model", default="gemini-2.5-flash-lite")
    parser.add_argument("--service", default="google")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    compiled, conversation, plan = build_compiled_original_mug_experiment()
    args.root.mkdir(parents=True, exist_ok=True)
    _write_json(args.root / "compiled_experiment.json", compiled.to_dict())
    _write_json(args.root / "conversation.json", conversation.to_dict())
    _write_json(args.root / "analysis_plan.json", plan.to_dict())
    _write_json(args.root / "paper_benchmark.json", PAPER_BENCHMARK)

    replications = list(compiled.replications[: args.limit])
    progress_lock = Lock()
    completed = 0
    failures: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(run_cell, item, compiled, conversation, args.root, args.model, args.service): item
            for item in replications
        }
        for future in as_completed(futures):
            item = futures[future]
            try:
                future.result()
            except Exception as exc:  # Preserve all other cells and make failures resumable.
                failures.append({"cell_id": item.cell_id, "error": f"{type(exc).__name__}: {exc}"})
            with progress_lock:
                completed += 1
                if completed % 10 == 0 or completed == len(replications):
                    print(json.dumps({"attempted": completed, "total": len(replications), "failures": len(failures)}), flush=True)

    _write_json(args.root / "failures.json", failures)
    observed = len(list((args.root / "cells").glob("*/observation.json")))
    if observed == PAPER_BENCHMARK["n"]:
        result = analyze(args.root, plan, model_name=args.model, service=args.service)
        print(json.dumps({"status": result["status"], "completed": observed, "failures": len(failures)}))
    else:
        print(json.dumps({"status": "partial", "completed": observed, "failures": len(failures)}))


if __name__ == "__main__":
    main()
