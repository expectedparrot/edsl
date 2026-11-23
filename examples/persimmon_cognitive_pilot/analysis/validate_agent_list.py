#!/usr/bin/env python3
"""Validate the scaffold-owned AgentList package and source provenance."""

import ast
import hashlib
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from edsl import AgentList

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "data" / "cooked" / "agent_list.ep"
PROVENANCE = ROOT / "data" / "raw" / "provenance.json"
EXPECTED_AGENTS = 12
REQUIRED_TRAITS = []
GROUP_TRAIT = None
EXPECTED_GROUP_SIZE = None
REQUIRED_SOURCE_DOMAIN = None


def main() -> int:
    agents = AgentList.git.load(str(ARTIFACT))
    errors = []
    names = [agent.name for agent in agents]
    if len(agents) != EXPECTED_AGENTS:
        errors.append(f"expected {EXPECTED_AGENTS} agents; found {len(agents)}")
    if len(set(names)) != len(names) or any(not name for name in names):
        errors.append("agent names must be non-empty and unique")
    missing = {
        trait: sum(agent.traits.get(trait) in (None, "") for agent in agents)
        for trait in REQUIRED_TRAITS
    }
    missing = {key: value for key, value in missing.items() if value}
    if missing:
        errors.append(f"missing required traits: {missing}")
    groups = Counter(agent.traits.get(GROUP_TRAIT) for agent in agents) if GROUP_TRAIT else Counter()
    bad_groups = {
        str(key): value for key, value in groups.items()
        if key in (None, "") or value != EXPECTED_GROUP_SIZE
    }
    if bad_groups:
        errors.append(f"invalid {GROUP_TRAIT} group sizes: {bad_groups}")
    provenance = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    for field in ("source_url", "retrieval_date", "raw_source_path", "source_sha256"):
        if not provenance.get(field):
            errors.append(f"provenance missing {field}")
    raw_source = (ROOT / provenance.get("raw_source_path", "")).resolve()
    try:
        raw_source.relative_to(ROOT)
    except ValueError:
        errors.append("raw_source_path must stay inside the study root")
    if not raw_source.is_file():
        errors.append(f"raw source not found: {raw_source}")
    elif provenance.get("source_sha256"):
        digest = hashlib.sha256(raw_source.read_bytes()).hexdigest()
        if digest != provenance["source_sha256"]:
            errors.append("raw source SHA-256 does not match provenance")
    embedded = []
    for path in ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if any(
            isinstance(node, ast.Constant) and isinstance(node.value, str)
            and len(node.value) > 4096
            for node in ast.walk(tree)
        ):
            embedded.append(str(path.relative_to(ROOT)))
    if embedded:
        errors.append(f"large source payload embedded in Python: {embedded}")
    source_host = urlparse(provenance.get("source_url", "")).hostname or ""
    if REQUIRED_SOURCE_DOMAIN and not (
        source_host == REQUIRED_SOURCE_DOMAIN or
        source_host.endswith("." + REQUIRED_SOURCE_DOMAIN)
    ):
        errors.append(
            f"source must be on {REQUIRED_SOURCE_DOMAIN}; found {source_host or 'none'}"
        )
    print(json.dumps({
        "status": "error" if errors else "ok",
        "data": {
            "agent_count": len(agents), "unique_names": len(set(names)),
            "required_traits": REQUIRED_TRAITS,
            "group_trait": GROUP_TRAIT, "group_count": len(groups),
            "source_url": provenance.get("source_url"),
            "retrieval_date": provenance.get("retrieval_date"),
        },
        "errors": errors,
    }, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
