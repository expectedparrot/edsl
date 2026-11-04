"""Refresh selected case studies and retain every executed prompt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from edsl import Model

from examples.shared_state_gemini_game_smoke import GAMES


HERE = Path(__file__).resolve().parent
DEFAULT_CASES = ("ultimatum", "agenda", "message_board", "work_pool")


def capture(game: str) -> None:
    survey, agents, schedule = GAMES[game]()
    results = (
        survey.by(agents)
        .by(
            Model(
                "gemini-2.5-flash",
                service_name="google",
                maxOutputTokens=4_096,
                thinking_budget=0,
            )
        )
        .run(
            cache=False,
            disable_remote_cache=True,
            disable_remote_inference=True,
            interview_schedule=schedule,
            max_concurrency=6,
            stop_on_exceptions=True,
        )
    )
    package = HERE / f"shared_state_{game}_results.ep"
    results.save(package, allow_new_commit=True)
    rows = []
    for result in results:
        prompts = result.data["prompt"]
        for key, user_prompt in prompts.items():
            if not key.endswith("_user_prompt"):
                continue
            question = key.removesuffix("_user_prompt")
            system_prompt = prompts[f"{question}_system_prompt"]
            rows.append(
                {
                    "agent": result.agent.name,
                    "round": result.agent.traits.get("turn", 1),
                    "question": question,
                    "user_prompt": user_prompt.text,
                    "system_prompt": system_prompt.text,
                    "answer": result.answer.get(question),
                    "comment": result.data["comments_dict"].get(
                        f"{question}_comment"
                    ),
                }
            )
    artifact = {
        "game": game,
        "model": "gemini-2.5-flash",
        "result_count": len(results),
        "answers": [result.answer for result in results],
        "rows": rows,
        "shared_state": results.shared_state,
    }
    (HERE / f"shared_state_{game}_results.json").write_text(
        json.dumps(artifact, indent=2, default=str) + "\n"
    )
    print(f"{game}: {len(results)} Results rows, {len(rows)} prompt rows")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("game", nargs="*")
    args = parser.parse_args()
    selected = args.game or DEFAULT_CASES
    invalid = sorted(set(selected) - GAMES.keys())
    if invalid:
        parser.error(f"unknown games: {invalid}; choose from {sorted(GAMES)}")
    for game in selected:
        capture(game)


if __name__ == "__main__":
    main()
