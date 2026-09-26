"""Discover and validate every migrated per-target recipe."""

from importlib import import_module
import json
from pathlib import Path


def validate_all() -> dict:
    root = Path(__file__).parent
    targets = sorted(
        path.stem
        for path in root.glob("shared_*.py")
        if path.stem not in {"shared_state"}
    )
    specs = {}
    for target in targets:
        spec = import_module(f"examples.shared_state_dsl.{target}").SPEC
        spec.validate()
        specs[spec.name] = spec.to_dict()
    return {"target_count": len(specs), "targets": sorted(specs), "specs": specs}


if __name__ == "__main__":
    result = validate_all()
    print(json.dumps({"target_count": result["target_count"], "targets": result["targets"]}, indent=2))
