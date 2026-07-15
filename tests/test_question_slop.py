import pytest

from edsl import QuestionSlop, Scenario, Survey
from edsl.agents import Agent
from edsl.invigilators.invigilator_slop import (
    InvigilatorSlop,
    PangramConfigurationError,
    PangramHTTPError,
)
from edsl.language_models import Model
from edsl.questions import QuestionBase
from edsl.surveys.memory import MemoryPlan


class FakePangramClient:
    async def score_text(self, text, **kwargs):
        return {
            "stage": "STAGE_SUCCESS",
            "version": "3.3.2",
            "headline": "Human Written",
            "prediction": "We are confident this document is human-written.",
            "prediction_short": "Human",
            "fraction_ai": 0.0,
            "fraction_ai_assisted": 0.0,
            "fraction_human": 1.0,
            "num_ai_segments": 0,
            "num_ai_assisted_segments": 0,
            "num_human_segments": 1,
            "windows": [
                {
                    "text": text,
                    "start_index": 0,
                    "end_index": len(text),
                    "label": "Human-Written",
                    "ai_assistance_score": 0.0,
                    "confidence": "High",
                    "word_count": len(text.split()),
                    "token_length": len(text.split()),
                }
            ],
        }


class ErrorPangramClient:
    async def score_text(self, text, **kwargs):
        raise PangramHTTPError(402, '{"detail":"Insufficient credits"}')


def make_invigilator(question, scenario=None, current_answers=None):
    survey = Survey([question])
    return InvigilatorSlop(
        agent=Agent(),
        question=question,
        scenario=scenario or Scenario({}),
        model=Model("test"),
        memory_plan=MemoryPlan(survey=survey),
        current_answers=current_answers or {},
        survey=survey,
    )


def test_question_slop_registered_and_round_trips():
    q = QuestionSlop(
        question_name="slop",
        question_text="{{ text }}",
        min_text_length=10,
    )

    restored = QuestionBase.from_dict(q.to_dict())

    assert isinstance(restored, QuestionSlop)
    assert restored.question_type == "slop"
    assert restored.question_text == "{{ text }}"
    assert restored.min_text_length == 10


@pytest.mark.asyncio
async def test_invigilator_slop_normalizes_pangram_response(monkeypatch):
    monkeypatch.setattr(InvigilatorSlop, "client_class", FakePangramClient)
    q = QuestionSlop(question_name="slop", question_text="{{ text }}")
    invigilator = make_invigilator(q, Scenario({"text": "This is a test."}))

    result = await invigilator.async_answer_question()

    assert result.answer["classification"] == "human"
    assert result.answer["provider_model"] == "3.3.2"
    assert result.answer["human_score"] == 1.0
    assert result.answer["segments"][0]["text"] == "This is a test."
    assert result.raw_model_response["prediction_short"] == "Human"


@pytest.mark.asyncio
async def test_invigilator_slop_renders_prior_answer(monkeypatch):
    monkeypatch.setattr(InvigilatorSlop, "client_class", FakePangramClient)
    q = QuestionSlop(question_name="slop", question_text="{{ essay.answer }}")
    invigilator = make_invigilator(q, current_answers={"essay": "Prior answer text."})

    result = await invigilator.async_answer_question()

    assert result.generated_tokens == "Prior answer text."
    assert result.answer["segments"][0]["text"] == "Prior answer text."


@pytest.mark.asyncio
async def test_invigilator_slop_short_text_returns_structured_answer(monkeypatch):
    monkeypatch.setattr(InvigilatorSlop, "client_class", FakePangramClient)
    q = QuestionSlop(
        question_name="slop",
        question_text="short",
        min_text_length=80,
        on_short_text="return_null",
    )
    invigilator = make_invigilator(q)

    result = await invigilator.async_answer_question()

    assert result.answer["classification"] == "too_short"
    assert result.answer["text_length"] == 5
    assert result.raw_model_response is None


@pytest.mark.asyncio
async def test_invigilator_slop_provider_error_is_structured(monkeypatch):
    monkeypatch.setattr(InvigilatorSlop, "client_class", ErrorPangramClient)
    q = QuestionSlop(question_name="slop", question_text="This is long enough.")
    invigilator = make_invigilator(q)

    result = await invigilator.async_answer_question()

    assert result.answer["classification"] == "error"
    assert result.answer["error_code"] == "insufficient_credits"


def test_pangram_client_requires_local_api_key(monkeypatch):
    from edsl.invigilators.invigilator_slop import PangramClient

    monkeypatch.delenv("PANGRAM_API_KEY", raising=False)

    with pytest.raises(PangramConfigurationError):
        PangramClient()
