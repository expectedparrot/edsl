"""Routing for agents that replay recorded answers.

An agent built from a stored human response tags its direct-answering method
with ``stored_answer_question_names``. Those names have to outrank a question's
own ``answer_question_directly``, otherwise question types that can answer
themselves - image generation above all - re-execute and throw away what the
respondent's session actually produced.
"""

import pytest

from edsl.agents import Agent
from edsl.questions import QuestionFreeText, QuestionCompute, QuestionImageGeneration
from edsl.runner.direct_answer import detect_execution_type


def _replaying_agent(response_data, question_names=None):
    """An agent that answers from a recorded response dict."""

    def f(self, question, scenario):
        return response_data.get(question.question_name)

    names = question_names if question_names is not None else response_data
    f.stored_answer_question_names = set(names) | set(response_data)

    agent = Agent(traits={})
    agent.add_direct_question_answering_method(f)
    return agent


def _plain_agent():
    def f(self, question, scenario):
        return "direct"

    agent = Agent(traits={})
    agent.add_direct_question_answering_method(f)
    return agent


IMAGE_Q = QuestionImageGeneration(
    question_name="portrait",
    question_text="Draw a house.",
    model="test-image",
    service_name="test",
)
COMPUTE_Q = QuestionCompute(question_name="total", question_text="{{ n }}")
TEXT_Q = QuestionFreeText(question_name="why", question_text="Why?")


class TestStoredAnswersOutrankSelfAnsweringQuestions:
    def test_image_generation_replays_instead_of_regenerating(self):
        agent = _replaying_agent({"portrait": {"base64_string": "abc"}})
        assert detect_execution_type(agent, IMAGE_Q) == "agent_direct"

    def test_compute_replays_instead_of_recomputing(self):
        agent = _replaying_agent({"total": 42})
        assert detect_execution_type(agent, COMPUTE_Q) == "agent_direct"

    def test_plain_question_still_routes_to_agent(self):
        agent = _replaying_agent({"why": "because"})
        assert detect_execution_type(agent, TEXT_Q) == "agent_direct"

    def test_missing_answer_still_replays_when_question_is_in_the_survey(self):
        """A failed image generation has no stored value, but must not re-run.

        Coverage is survey-scoped, so the name is authoritative even though the
        response dict has no entry for it. The answer resolves to None.
        """
        agent = _replaying_agent({"why": "because"}, question_names=["why", "portrait"])
        assert detect_execution_type(agent, IMAGE_Q) == "agent_direct"

    def test_question_outside_the_covered_set_keeps_old_behavior(self):
        agent = _replaying_agent({"why": "because"})
        assert detect_execution_type(agent, IMAGE_Q) == "functional"


class TestOptInDoesNotDisturbNormalJobs:
    def test_self_answering_question_still_wins_without_the_tag(self):
        assert detect_execution_type(_plain_agent(), IMAGE_Q) == "functional"
        assert detect_execution_type(_plain_agent(), COMPUTE_Q) == "functional"

    def test_agent_without_direct_answering_routes_to_llm(self):
        assert detect_execution_type(Agent(traits={}), TEXT_Q) == "llm"

    def test_no_agent_routes_to_llm(self):
        assert detect_execution_type(None, TEXT_Q) == "llm"

    def test_empty_covered_set_falls_through(self):
        """An empty set means nothing recorded - don't hijack routing."""
        agent = _replaying_agent({})
        assert detect_execution_type(agent, IMAGE_Q) == "functional"


class TestTagSurvivesAgentDuplication:
    """Agents round-trip through to_dict/from_dict during a run.

    Only the direct-answering method is carried across, by transfer_to, so the
    tag has to travel on that wrapper. If it doesn't, routing silently reverts
    and the regression is invisible.
    """

    def test_duplicate_preserves_the_covered_set(self):
        agent = _replaying_agent({"portrait": None}, question_names=["portrait"])
        copy = agent.duplicate()
        assert copy.answer_question_directly.stored_answer_question_names == {
            "portrait"
        }

    def test_duplicate_preserves_routing(self):
        agent = _replaying_agent({"portrait": None}, question_names=["portrait"])
        assert detect_execution_type(agent.duplicate(), IMAGE_Q) == "agent_direct"

    def test_duplicate_without_the_tag_is_unaffected(self):
        copy = _plain_agent().duplicate()
        assert getattr(
            copy.answer_question_directly, "stored_answer_question_names", None
        ) is None
        assert detect_execution_type(copy, IMAGE_Q) == "functional"


class TestStoredImagesDecodeToFileStore:
    """The wire form of a stored image has to come back as a real FileStore.

    ImageGenerationResponse rejects anything without .base64_string/.mime_type,
    so a raw dict off json.loads would fail validation downstream.
    """

    def test_filestore_round_trips(self):
        from edsl.runner.models import _encode_answer_value, _decode_answer_value
        from edsl.scenarios import FileStore

        # example() returns None when the handler for a suffix isn't registered
        original = FileStore.example("png")
        if original is None:
            pytest.skip("png FileStore handler unavailable")

        decoded = _decode_answer_value(_encode_answer_value(original))
        assert isinstance(decoded, FileStore)
        assert decoded.base64_string == original.base64_string
        assert decoded.mime_type == original.mime_type

    def test_none_passes_through(self):
        from edsl.runner.models import _decode_answer_value

        assert _decode_answer_value(None) is None

    def test_scalars_pass_through(self):
        from edsl.runner.models import _decode_answer_value

        assert _decode_answer_value("because") == "because"
        assert _decode_answer_value(42) == 42
