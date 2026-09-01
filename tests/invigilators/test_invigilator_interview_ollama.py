import os
import shutil

import pytest
import requests

from edsl import Agent, Model, QuestionInterview, Scenario, Survey


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def _available_ollama_model():
    configured_model = os.getenv("EDSL_OLLAMA_TEST_MODEL")
    if configured_model:
        return configured_model

    response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
    response.raise_for_status()
    models = response.json().get("models", [])
    if not models:
        return None
    return models[0]["name"]


def _require_local_ollama():
    if shutil.which("ollama") is None:
        pytest.skip("ollama is not installed")

    try:
        model_name = _available_ollama_model()
    except Exception as exc:
        pytest.skip(f"ollama server is not available: {exc}")

    if not model_name:
        pytest.skip("ollama is running but no local models are installed")

    return model_name


def test_interview_question_runs_with_ollama():
    model_name = _require_local_ollama()

    question = QuestionInterview(
        question_name="local_interview",
        question_text="Understand the respondent's experience using a local LLM.",
        interview_guide="Ask what works well and what does not. Stop after a short interview.",
        max_turns=2,
    )

    survey = Survey([question])
    agent = Agent(
        traits={
            "occupation": "software engineer",
            "experience_level": "senior",
            "tooling_preference": "local-first",
        },
        instruction="Answer naturally as the person described.",
    )
    model = Model(model_name, service_name="ollama")

    result = survey.by(agent).by(Scenario()).by(model).run(
        progress_bar=False, verbose=False
    )

    transcript = result.select("answer.local_interview").to_list()[0]

    assert isinstance(transcript, list)
    assert len(transcript) >= 2
    assert transcript[0]["role"] == "interviewer"
    assert transcript[1]["role"] == "respondent"
