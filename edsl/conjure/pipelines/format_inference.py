from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from .profiles import CsvFormat, CsvProfile


def refine_profile_with_llm(path: Path, profile: CsvProfile) -> CsvProfile:
    """
    Use an LLM to refine the detected CSV profile when heuristics are uncertain.

    Returns the original profile if the LLM is unavailable or the output is invalid.
    """
    if profile.format != CsvFormat.SIMPLE:
        return profile

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return profile

    try:
        import openai  # type: ignore
    except ImportError:
        return profile

    sample_text = _read_sample(path)
    if not sample_text.strip():
        return profile

    prompt = (
        "You are helping detect the structure of a CSV survey export. "
        "Based on the snippet below, decide if this file is a Qualtrics export "
        "with multiple header rows or a simple single-header CSV.\n\n"
        "Respond ONLY with a compact JSON object like:\n"
        '{"format": "qualtrics_three_row", "header_rows": 4}\n'
        'or\n'
        '{"format": "simple", "header_rows": 1}\n\n'
        "Choose header_rows 3 or 4 for Qualtrics exports depending on whether the first row "
        "contains generic placeholders (Column1, Column2, ...). When uncertain, prefer 3.\n"
        "CSV sample:\n```csv\n"
        f"{sample_text}\n```"
    )

    try:
        openai.api_key = api_key  # type: ignore
        response = openai.ChatCompletion.create(  # type: ignore
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You output only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        content = response["choices"][0]["message"]["content"]  # type: ignore
        parsed = json.loads(content)
    except Exception:
        return profile

    fmt = str(parsed.get("format", "")).lower()
    header_rows = int(parsed.get("header_rows", profile.header_rows))

    if fmt == "qualtrics_three_row":
        return CsvProfile(
            format=CsvFormat.QUALTRICS_THREE_ROW,
            header_rows=header_rows if header_rows in {3, 4} else 3,
            delimiter=profile.delimiter,
            respondent_id_column=profile.respondent_id_column,
        )
    return profile


def _read_sample(path: Path, max_lines: int = 20) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            lines = [next(f).rstrip("\n") for _ in range(max_lines)]
    except (StopIteration, FileNotFoundError, OSError):
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                lines = f.read(2048).splitlines()
        except Exception:
            return ""
    return "\n".join(lines)
