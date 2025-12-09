from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from .models import NormalizedSurvey


def write_questions_yaml(normalized: NormalizedSurvey, path: Path) -> Path:
    """
    Write questions YAML to the provided path.
    """
    payload: Dict[str, Any] = {
        "survey": {
            "source": normalized.source_metadata.get("source"),
            "metadata": normalized.source_metadata,
            "respondent_count": len(normalized.respondent_order),
        },
        "questions": list(normalized.iter_question_mappings()),
    }

    yaml_text = _dump_yaml(payload)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml_text, encoding="utf-8")
    return path


def write_agent_responses_csv(normalized: NormalizedSurvey, path: Path) -> Path:
    """
    Write agent responses in long-form CSV.
    """
    rows: List[Dict[str, Any]] = []

    for record in normalized.iter_response_mappings():
        response_value = record["response"]
        response_kind = record["response_kind"]
        if response_kind in {"list", "dict"}:
            response_str = repr(response_value)
        elif response_value is None:
            response_str = ""
        else:
            response_str = str(response_value)

        response_metadata = record.get("response_metadata") or {}
        rows.append(
            {
                "respondent_id": record["respondent_id"],
                "question_name": record["question_name"],
                "response": response_str,
                "response_kind": response_kind,
                "response_metadata": (
                    json.dumps(response_metadata, ensure_ascii=False)
                    if response_metadata
                    else ""
                ),
            }
        )

    df = pd.DataFrame(rows)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path


def _dump_yaml(data: Any) -> str:
    """
    Dump YAML using PyYAML when available, otherwise use a simple fallback.
    """
    try:
        import yaml  # type: ignore

        return yaml.safe_dump(
            data,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )
    except ImportError:
        return _simple_yaml_dump(data)


def _simple_yaml_dump(data: Any, indent: int = 0) -> str:
    """
    Minimal YAML serializer supporting the structures produced by this module.
    """
    space = "  " * indent
    if isinstance(data, dict):
        lines: List[str] = []
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{space}{key}:")
                lines.append(_simple_yaml_dump(value, indent + 1))
            else:
                rendered = _render_scalar(value)
                lines.append(f"{space}{key}: {rendered}")
        return "\n".join(lines)
    if isinstance(data, list):
        lines: List[str] = []
        for item in data:
            if isinstance(item, (dict, list)):
                lines.append(f"{space}-")
                lines.append(_simple_yaml_dump(item, indent + 1))
            else:
                rendered = _render_scalar(item)
                lines.append(f"{space}- {rendered}")
        return "\n".join(lines)
    return f"{space}{_render_scalar(data)}"


def _render_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    # Quote strings containing colon, hash, or leading special chars
    if (
        any(ch in text for ch in [":", "#", "{", "}", ",", "[", "]"])
        or text.strip() != text
    ):
        escaped = text.replace("'", "''")
        return f"'{escaped}'"
    return text
