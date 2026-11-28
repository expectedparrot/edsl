"""Combine the saved task Results packages without changing their rows."""

from __future__ import annotations

import argparse
from pathlib import Path

from edsl import Results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("result_paths", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    results = Results.load(str(args.result_paths[0]))
    for path in args.result_paths[1:]:
        next_results = Results.load(str(path))
        results.extend(next_results)
        results.task_history.total_interviews.extend(
            next_results.task_history.total_interviews
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    results.save(str(args.output))


if __name__ == "__main__":
    main()
