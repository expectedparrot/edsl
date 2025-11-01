from __future__ import annotations

from pathlib import Path

import pytest
import sys


@pytest.fixture
def pipeline_components(tmp_path, monkeypatch):
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    monkeypatch.setenv("HOME", str(tmp_path))

    from conjure.pipelines import normalize_survey_file
    from conjure.pipelines.profiles import CsvFormat, detect_csv_profile
    from conjure.pipelines.writers import (
        write_agent_responses_csv,
        write_questions_yaml,
    )
    from conjure.input_data_yaml import InputDataYAML

    return {
        "normalize": normalize_survey_file,
        "CsvFormat": CsvFormat,
        "detect_csv_profile": detect_csv_profile,
        "write_questions_yaml": write_questions_yaml,
        "write_agent_responses_csv": write_agent_responses_csv,
        "InputDataYAML": InputDataYAML,
    }


def test_detect_csv_profile_simple(tmp_path, pipeline_components):
    csv_path = tmp_path / "simple.csv"
    csv_path.write_text(
        "color,shape\n" "blue,circle\n" "green,square\n",
        encoding="utf-8",
    )

    profile = pipeline_components["detect_csv_profile"](csv_path)
    assert profile.format == pipeline_components["CsvFormat"].SIMPLE
    assert profile.header_rows == 1
    assert profile.delimiter == ","


def test_detect_csv_profile_qualtrics(tmp_path, pipeline_components):
    csv_path = tmp_path / "qualtrics.csv"
    csv_path.write_text(
        "Column1,Column2\n"
        "Q1,Q2\n"
        "First question?,Second question?\n"
        '{"ImportId":"QID1"},{"ImportId":"QID2"}\n'
        "1,2\n",
        encoding="utf-8",
    )

    profile = pipeline_components["detect_csv_profile"](csv_path)
    assert profile.format == pipeline_components["CsvFormat"].QUALTRICS_THREE_ROW
    assert profile.header_rows == 4


def test_normalize_and_roundtrip_simple_csv(tmp_path, pipeline_components):
    yaml = pytest.importorskip("yaml")

    csv_path = tmp_path / "survey.csv"
    csv_path.write_text(
        "respondent,preference\n" "r1,apples\n" "r2,oranges\n",
        encoding="utf-8",
    )

    normalized = pipeline_components["normalize"](csv_path)
    assert normalized.questions, "expected at least one question"

    output_dir = tmp_path / "normalized"
    questions_yaml = pipeline_components["write_questions_yaml"](
        normalized, output_dir / "questions.yaml"
    )
    responses_csv = pipeline_components["write_agent_responses_csv"](
        normalized, output_dir / "agent_responses.csv"
    )

    input_data = pipeline_components["InputDataYAML"](
        str(questions_yaml), responses_file=str(responses_csv)
    )
    assert input_data.num_observations == 2
    assert "preference" in input_data.question_names


def test_conjure_auto_normalizes_qualtrics(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    csv_path = tmp_path / "qualtrics.csv"
    csv_path.write_text(
        "Column1,Column2\n"
        "Q1,Q2\n"
        "First question?,Second question?\n"
        '{"ImportId":"QID1"},{"ImportId":"QID2"}\n'
        "1,2\n",
        encoding="utf-8",
    )

    from conjure import Conjure
    from conjure.input_data_normalized import InputDataNormalized

    instance = Conjure(str(csv_path))
    assert isinstance(instance, InputDataNormalized)
