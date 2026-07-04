"""Opt-in live CLI tests for Expected Parrot-backed flows.

Run with:
    EDSL_RUN_LIVE_CLI_TESTS=1 EDSL_LIVE_HUMAN_SURVEY_UUID=<uuid> pytest -q tests/test_cli_live.py
"""

import json
import os
import subprocess
import sys

import pytest


pytestmark = pytest.mark.skipif(
    os.environ.get("EDSL_RUN_LIVE_CLI_TESTS") != "1",
    reason="Set EDSL_RUN_LIVE_CLI_TESTS=1 to run live CLI tests.",
)


def run_cli(*args, expect_exit=0):
    result = subprocess.run(
        [sys.executable, "-m", "edsl", *args],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == expect_exit, (
        f"Expected exit {expect_exit}, got {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    return json.loads(result.stdout)


def test_live_humanize_read_paths():
    human_survey_uuid = os.environ.get("EDSL_LIVE_HUMAN_SURVEY_UUID")
    if not human_survey_uuid:
        pytest.skip("Set EDSL_LIVE_HUMAN_SURVEY_UUID to run live humanize read tests.")

    status = run_cli("humanize", "status", human_survey_uuid)
    assert status["data"]["uuid"] == human_survey_uuid

    respondents = run_cli(
        "humanize",
        "respondents",
        human_survey_uuid,
        "--page",
        "1",
        "--page_size",
        "5",
    )
    assert "respondents" in respondents["data"]

    deliveries = run_cli(
        "humanize",
        "deliveries",
        "list",
        human_survey_uuid,
        "--page",
        "1",
        "--page_size",
        "5",
    )
    assert "deliveries" in deliveries["data"]
