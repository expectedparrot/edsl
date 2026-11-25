"""Replay portable experiments without importing experiment-specific Python.

python -m edsl.workflows.replay --experiment experiment.json \
    --responses responses.json --output replay
"""

import argparse
import json
from pathlib import Path

from .experiment import WorkflowExperiment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--responses", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    try:
        experiment = WorkflowExperiment.load(args.experiment)
        result = experiment.run(
            args.output,
            responses=json.loads(args.responses.read_text()),
            resume=args.resume,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": {"code": "REPLAY_ERROR", "message": str(exc)},
                }
            )
        )
        raise SystemExit(1)
    print(json.dumps({"status": "ok", "data": result, "warnings": []}))


if __name__ == "__main__":
    main()
