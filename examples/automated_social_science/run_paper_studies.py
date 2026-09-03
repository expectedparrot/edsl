"""Run the bail, job-interview, and auction designs with durable cell state."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from edsl import Model
from edsl.causal import CausalExperimentRunner, EDSLCausalAdapter
from edsl.conversations import SQLiteConversationStore

from examples.automated_social_science.paper_studies import STUDIES


BENCHMARKS = {
    "bail": {
        # Figure 3 says 243, but 7 x 7 x 5 = 245 and Appendix Figure A.5
        # explicitly confirms that 245 simulations were actually run.
        "outcome": "bail_amount", "mean": 54428.57, "n": 245,
        "coefficients": {"criminal_history": 521.53, "judge_case_count": -74.632, "defendant_remorse": -1153.061},
        "standard_errors": {"criminal_history": 206.567, "judge_case_count": 109.263, "defendant_remorse": 603.325},
    },
    "interview": {
        "outcome": "hired", "mean": 0.62, "n": 80,
        "coefficients": {"passed_bar": 0.75, "interviewer_friendliness": -0.002, "applicant_height": 0.003},
        "standard_errors": {"passed_bar": 0.068, "interviewer_friendliness": 0.005, "applicant_height": 0.003},
    },
    "auction": {
        "outcome": "final_price", "mean": 186.53, "n": 343,
        "coefficients": {"bidder_1_budget": 0.35, "bidder_2_budget": 0.29, "bidder_3_budget": 0.31},
        "standard_errors": {"bidder_1_budget": 0.015, "bidder_2_budget": 0.015, "bidder_3_budget": 0.015},
    },
}


def write_json(path: Path, value: Any):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def run_cell(replication, compiled, conversation, root, model_name, service):
    cell_root = root / "cells" / replication.cell_id
    cell_root.mkdir(parents=True, exist_ok=True)
    observation_path = cell_root / "observation.json"
    if observation_path.exists():
        return
    adapter = EDSLCausalAdapter(Model(model_name, service_name=service))
    store = SQLiteConversationStore(cell_root / "conversation.sqlite")
    outcome = compiled.measurements[0].variable
    runner = CausalExperimentRunner(
        compiled, conversation, store,
        speakers={role: adapter.speak for role in conversation.roles},
        semantic_judge=adapter.judge,
        measurers={outcome: adapter.measure},
    )
    observation = runner.run(replication).to_dict()
    write_json(observation_path, observation)
    write_json(cell_root / "transcript.json", store.transcript(replication.instance_id))
    write_json(cell_root / "provenance.json", adapter.provenance())


def analyze(study, root, plan, model_name, service):
    observations = [json.loads(path.read_text()) for path in sorted((root / "cells").glob("*/observation.json"))]
    rows = [item["values"] for item in observations]
    fitted = plan.fit(rows)
    outcome = BENCHMARKS[study]["outcome"]
    values = [float(row[outcome]) for row in rows]
    result = {
        "status": "complete", "study": study,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": {"name": model_name, "service": service},
        "design": {"completed": len(rows), "expected": BENCHMARKS[study]["n"]},
        "outcomes": {
            "mean": sum(values) / len(values),
            "minimum": min(values), "maximum": max(values),
            "mean_turns": sum(item["transcript_version"] for item in observations) / len(observations),
            "maximum_turns": max(item["transcript_version"] for item in observations),
        },
        "fit": fitted.to_dict(), "paper_benchmark": BENCHMARKS[study],
    }
    write_json(root / "results.json", result)
    return result


def run_study(study, args):
    compiled, conversation, plan = STUDIES[study]()
    root = args.root / study
    root.mkdir(parents=True, exist_ok=True)
    write_json(root / "compiled_experiment.json", compiled.to_dict())
    write_json(root / "conversation.json", conversation.to_dict())
    write_json(root / "analysis_plan.json", plan.to_dict())
    write_json(root / "paper_benchmark.json", BENCHMARKS[study])
    failures = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        replications = compiled.replications[: args.limit] if args.limit else compiled.replications
        futures = {executor.submit(run_cell, item, compiled, conversation, root, args.model, args.service): item for item in replications}
        for number, future in enumerate(as_completed(futures), 1):
            try:
                future.result()
            except Exception as exc:
                failures.append({"cell_id": futures[future].cell_id, "error": f"{type(exc).__name__}: {exc}"})
            if number % 10 == 0 or number == len(futures):
                print(json.dumps({"study": study, "attempted": number, "total": len(futures), "failures": len(failures)}), flush=True)
    write_json(root / "failures.json", failures)
    completed = len(list((root / "cells").glob("*/observation.json")))
    result = analyze(study, root, plan, args.model, args.service) if completed == len(compiled.replications) else None
    return {"study": study, "completed": completed, "expected": len(compiled.replications), "failures": len(failures), "analyzed": result is not None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--study", choices=[*STUDIES, "all"], default="all")
    parser.add_argument("--root", type=Path, default=Path("examples/automated_social_science/runs/paper-replications"))
    parser.add_argument("--model", default="gemini-2.5-flash-lite")
    parser.add_argument("--service", default="google")
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--limit", type=int, help="Run only the first N cells as a resumable preflight")
    args = parser.parse_args()
    # Keep EDSL's content-addressed run state with the study artifacts. This
    # makes the experiment portable and avoids dependence on a user-level CAS.
    from edsl.object_store.store import ObjectStore
    ObjectStore.default_root = staticmethod(lambda: args.root / "_object_store")
    selected = list(STUDIES) if args.study == "all" else [args.study]
    summaries = [run_study(study, args) for study in selected]
    print(json.dumps({"status": "ok" if all(item["analyzed"] for item in summaries) else "partial", "studies": summaries}))


if __name__ == "__main__":
    main()
