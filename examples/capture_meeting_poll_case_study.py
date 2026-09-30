"""Run the meeting-time poll and retain its prompts and state audit."""

from __future__ import annotations

import json
from pathlib import Path

from edsl import Model

from examples.shared_state_gemini_game_smoke import GAMES


HERE = Path(__file__).resolve().parent


def main() -> None:
    survey, agents, schedule = GAMES["meeting_poll"]()
    results = (
        survey.by(agents)
        .by(
            Model(
                "gemini-2.5-flash",
                service_name="google",
                maxOutputTokens=2_048,
                thinking_budget=0,
            )
        )
        .run(
            cache=False,
            disable_remote_cache=True,
            disable_remote_inference=True,
            interview_schedule=schedule,
            max_concurrency=4,
            stop_on_exceptions=True,
        )
    )
    results.save(
        HERE / "shared_state_meeting_poll_results.ep", allow_new_commit=True
    )
    rows = []
    for result in results:
        prompts = result.data["prompt"]
        rows.append(
            {
                "agent": result.agent.name,
                "round": result.agent.traits["turn"],
                "user_prompt": prompts["available_slots_user_prompt"].text,
                "system_prompt": prompts["available_slots_system_prompt"].text,
                "answer": result.answer["available_slots"],
                "comment": result.data["comments_dict"].get(
                    "available_slots_comment", ""
                ),
            }
        )
    artifact = {
        "model": "gemini-2.5-flash",
        "rows": rows,
        "shared_state": results.shared_state,
    }
    (HERE / "shared_state_meeting_poll_results.json").write_text(
        json.dumps(artifact, indent=2, default=str) + "\n"
    )
    print(f"Captured {len(rows)} Results rows")


if __name__ == "__main__":
    main()
