#!/usr/bin/env python3
"""Summarize current and archived inference attempts without losing provenance."""

import json
from pathlib import Path

from edsl import Results


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    attempts = []
    for path in sorted((ROOT / "data" / "attempts").glob("*-cost.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        attempts.append({"artifact": path.name, "cost": payload["data"]["cost"]})
    current = ROOT / "data" / "results.ep"
    if current.is_file():
        attempts.append({
            "artifact": "results.ep",
            "cost": Results.git.load(str(current)).compute_job_cost(),
        })
    print(json.dumps({
        "attempt_count": len(attempts),
        "attempts": attempts,
        "total_cost": sum(float(item["cost"]) for item in attempts),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
