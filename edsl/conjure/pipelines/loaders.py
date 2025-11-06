from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

from .models import AgentResponseRecord, QuestionSpec


def load_questions_yaml(path: Path) -> Tuple[List[QuestionSpec], Dict[str, Any]]:
    """
    Load questions YAML and return question specs plus survey metadata.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8")

    try:
        import yaml  # type: ignore
    except ImportError as exc:  # pragma: no cover - dependency error path
        raise ImportError(
            "PyYAML is required to load questions YAML files. "
            "Install it with `pip install pyyaml`."
        ) from exc

    payload = yaml.safe_load(text) or {}
    survey_meta = payload.get("survey") or {}
    question_entries = payload.get("questions") or []

    questions: List[QuestionSpec] = []
    for entry in question_entries:
        questions.append(
            QuestionSpec(
                question_name=entry.get("question_name"),
                question_text=entry.get("question_text", ""),
                question_type=entry.get("question_type", "unknown"),
                question_options=entry.get("question_options"),
                derived_hints=entry.get("derived_hints") or {},
            )
        )

    return questions, dict(survey_meta)


def load_agent_responses(path: Path) -> List[AgentResponseRecord]:
    """
    Load agent responses CSV and return response records.
    """
    path = Path(path)
    df = pd.read_csv(path, dtype=str, keep_default_na=False)

    records: List[AgentResponseRecord] = []

    for _, row in df.iterrows():
        respondent_id = str(row["respondent_id"])
        question_name = str(row["question_name"])
        response_kind = row.get("response_kind", "scalar") or "scalar"
        response_text = row.get("response", "")
        metadata_text = row.get("response_metadata", "")

        if response_kind in {"list", "dict"} and response_text:
            try:
                response_value = ast.literal_eval(response_text)
            except Exception:
                response_value = response_text
        else:
            response_value = response_text if response_text != "" else "missing"

        response_metadata: Dict[str, Any]
        if metadata_text:
            try:
                response_metadata = json.loads(metadata_text)
            except json.JSONDecodeError:
                response_metadata = {}
        else:
            response_metadata = {}

        records.append(
            AgentResponseRecord(
                respondent_id=respondent_id,
                question_name=question_name,
                response=response_value,
                response_kind=response_kind,
                response_metadata=response_metadata,
            )
        )

    return records
