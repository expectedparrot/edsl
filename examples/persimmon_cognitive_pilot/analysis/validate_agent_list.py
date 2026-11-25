#!/usr/bin/env python3
"""Validate the fictional personas defined by the pilot itself."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from run_pilot import make_agents  # noqa: E402


EXPECTED_AGENTS = 12
REQUIRED_TRAITS = {"age", "occupation", "style"}


def main() -> int:
    agents = make_agents()
    names = [agent.name for agent in agents]
    errors = []
    if len(agents) != EXPECTED_AGENTS:
        errors.append(f"expected {EXPECTED_AGENTS} personas; found {len(agents)}")
    if len(set(names)) != len(names) or any(not name for name in names):
        errors.append("persona names must be non-empty and unique")
    missing_traits = {
        agent.name: sorted(REQUIRED_TRAITS - agent.traits.keys())
        for agent in agents
        if REQUIRED_TRAITS - agent.traits.keys()
    }
    if missing_traits:
        errors.append(f"personas are missing required traits: {missing_traits}")
    missing_instructions = [agent.name for agent in agents if not agent.instruction]
    if missing_instructions:
        errors.append(f"personas are missing instructions: {missing_instructions}")

    print(
        json.dumps(
            {
                "status": "error" if errors else "ok",
                "data": {"persona_count": len(agents), "unique_names": len(set(names))},
                "errors": errors,
            },
            indent=2,
        )
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
