"""Run the forecast case and retain its complete prompts and shared-state audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from edsl import Model, Results

from examples.shared_state_gemini_game_smoke import GAMES


HERE = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--from-saved",
        action="store_true",
        help="Refresh prompt rows from the saved Results package without model calls.",
    )
    args = parser.parse_args()
    package = HERE / "shared_state_forecast_results.ep"
    artifact_path = HERE / "shared_state_forecast_results.json"
    if args.from_saved:
        results = Results.git.load(package)
        shared_state = json.loads(artifact_path.read_text())["shared_state"]
    else:
        survey, agents, schedule = GAMES["forecast"]()
        results = (
            survey.by(agents)
            .by(Model("gemini-2.5-flash", service_name="google"))
            .run(
                cache=False,
                disable_remote_cache=True,
                disable_remote_inference=True,
                interview_schedule=schedule,
                max_concurrency=5,
                stop_on_exceptions=True,
            )
        )
        results.save(package, allow_new_commit=True)
        shared_state = results.shared_state
    rounds_by_agent: dict[str, int] = {}
    rows = []
    for result in results:
        name = result.agent.name
        rounds_by_agent[name] = rounds_by_agent.get(name, 0) + 1
        prompts = result.data["prompt"]
        rows.append(
            {
                "agent": name,
                "round": rounds_by_agent[name],
                "user_prompt": prompts["probability_user_prompt"].text,
                "system_prompt": prompts["probability_system_prompt"].text,
                "answer": result.answer["probability"],
                "comment": result.data["comments_dict"].get(
                    "probability_comment", ""
                ),
            }
        )
    artifact = {
        "model": "gemini-2.5-flash",
        "rows": rows,
        "shared_state": shared_state,
    }
    artifact_path.write_text(
        json.dumps(artifact, indent=2, default=str) + "\n"
    )
    print(f"Captured {len(rows)} Results rows")


if __name__ == "__main__":
    main()
