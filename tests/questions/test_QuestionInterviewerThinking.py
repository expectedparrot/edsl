"""Tests for QuestionInterviewerThinking.

This module tests the QuestionInterviewerThinking question type which makes
direct LLM calls bypassing normal EDSL agent/prompt processing.
"""

import pytest
from pydantic import BaseModel
from typing import Optional

from edsl.questions import QuestionBase
from edsl.questions.question_interviewer_thinking import (
    QuestionInterviewerThinking,
    InterviewerThinkingResponse,
    InterviewerThinkingResponseValidator,
)
from edsl.language_models import Model


class TestInterviewerThinkingResponse:
    """Tests for the InterviewerThinkingResponse Pydantic model."""

    def test_valid_string_response(self):
        """Test valid string response."""
        response = InterviewerThinkingResponse(answer="What is your favorite food?")
        assert response.answer == "What is your favorite food?"
        assert response.generated_tokens is None

    def test_valid_dict_response(self):
        """Test valid dict response (for structured outputs)."""
        response = InterviewerThinkingResponse(
            answer={"question": "Why?", "category": "follow-up"}
        )
        assert response.answer == {"question": "Why?", "category": "follow-up"}

    def test_valid_list_response(self):
        """Test valid list response."""
        response = InterviewerThinkingResponse(answer=["item1", "item2"])
        assert response.answer == ["item1", "item2"]

    def test_none_converts_to_empty_string(self):
        """Test that None converts to empty string."""
        response = InterviewerThinkingResponse(answer=None)
        assert response.answer == ""

    def test_with_generated_tokens(self):
        """Test response with generated_tokens."""
        response = InterviewerThinkingResponse(
            answer="Follow-up question",
            generated_tokens="Follow-up question"
        )
        assert response.answer == "Follow-up question"
        assert response.generated_tokens == "Follow-up question"


class TestInterviewerThinkingResponseValidator:
    """Tests for the response validator."""

    def test_fix_none_answer_with_generated_tokens(self):
        """Test that fix() uses generated_tokens when answer is None."""
        validator = InterviewerThinkingResponseValidator(
            question=None, 
            response_model=InterviewerThinkingResponse
        )
        response = {"answer": None, "generated_tokens": "Some text"}
        fixed = validator.fix(response)
        assert fixed["answer"] == "Some text"

    def test_fix_none_answer_without_generated_tokens(self):
        """Test that fix() returns empty string when both are None."""
        validator = InterviewerThinkingResponseValidator(
            question=None, 
            response_model=InterviewerThinkingResponse
        )
        response = {"answer": None, "generated_tokens": None}
        fixed = validator.fix(response)
        assert fixed["answer"] == ""

    def test_fix_json_in_generated_tokens(self):
        """Test that fix() parses JSON in generated_tokens."""
        validator = InterviewerThinkingResponseValidator(
            question=None, 
            response_model=InterviewerThinkingResponse
        )
        response = {
            "answer": None,
            "generated_tokens": '{"question": "Why?", "reasoning": "To learn more"}'
        }
        fixed = validator.fix(response)
        assert fixed["answer"] == {"question": "Why?", "reasoning": "To learn more"}


class TestQuestionInterviewerThinkingConstruction:
    """Tests for question construction."""

    def test_basic_construction(self):
        """Test basic construction with required parameters."""
        model = Model("gpt-4o-mini")
        q = QuestionInterviewerThinking(
            question_name="follow_up",
            question_text="Generate a follow-up question.",
            model=model,
        )
        assert q.question_name == "follow_up"
        assert q.question_text == "Generate a follow-up question."
        assert q.question_type == "interviewer_thinking"
        assert q.system_prompt == ""  # Default is empty string

    def test_construction_with_system_prompt(self):
        """Test construction with system prompt."""
        model = Model("gpt-4o-mini")
        q = QuestionInterviewerThinking(
            question_name="analyze",
            question_text="Analyze this response.",
            system_prompt="You are a helpful survey researcher.",
            model=model,
        )
        assert q.system_prompt == "You are a helpful survey researcher."

    def test_construction_with_response_model(self):
        """Test construction with Pydantic response model."""
        class FollowUp(BaseModel):
            question: str
            reasoning: str
            category: Optional[str] = None

        model = Model("gpt-4o-mini")
        q = QuestionInterviewerThinking(
            question_name="structured",
            question_text="Generate a structured follow-up.",
            model=model,
            response_model=FollowUp,
        )
        assert q.user_response_model == FollowUp
        assert q.get_response_schema() is not None
        assert "properties" in q.get_response_schema()
        assert "question" in q.get_response_schema()["properties"]
        assert "reasoning" in q.get_response_schema()["properties"]

    def test_construction_with_dict_model(self):
        """Test construction with model dict (for deserialization)."""
        model_dict = {"model": "gpt-4o-mini", "parameters": {}, "inference_service": "openai"}
        q = QuestionInterviewerThinking(
            question_name="test",
            question_text="Test question.",
            model=model_dict,
        )
        assert q.model_dict == model_dict

    def test_example_creation(self):
        """Test the example() class method."""
        q = QuestionInterviewerThinking.example()
        assert q.question_name == "generate_follow_up"
        assert "follow-up" in q.question_text
        assert q.system_prompt != ""
        assert q.question_type == "interviewer_thinking"


class TestQuestionInterviewerThinkingSerialization:
    """Tests for serialization and deserialization."""

    def test_to_dict_basic(self):
        """Test basic serialization to dict."""
        model = Model("gpt-4o-mini")
        q = QuestionInterviewerThinking(
            question_name="test",
            question_text="Test question.",
            model=model,
        )
        d = q.to_dict()
        
        assert d["question_name"] == "test"
        assert d["question_text"] == "Test question."
        assert d["question_type"] == "interviewer_thinking"
        assert "model" in d
        assert d["system_prompt"] == ""

    def test_to_dict_with_response_model(self):
        """Test serialization includes response model schema."""
        class FollowUp(BaseModel):
            question: str
            reasoning: str

        model = Model("gpt-4o-mini")
        q = QuestionInterviewerThinking(
            question_name="test",
            question_text="Test question.",
            model=model,
            response_model=FollowUp,
        )
        d = q.to_dict()
        
        assert "response_model_schema" in d
        assert "response_model_name" in d
        assert d["response_model_name"] == "FollowUp"

    def test_from_dict_basic(self):
        """Test deserialization from dict."""
        model = Model("gpt-4o-mini")
        q = QuestionInterviewerThinking(
            question_name="test",
            question_text="Test question.",
            system_prompt="Be helpful.",
            model=model,
        )
        d = q.to_dict()
        
        q2 = QuestionInterviewerThinking.from_dict(d)
        
        assert q2.question_name == q.question_name
        assert q2.question_text == q.question_text
        assert q2.system_prompt == q.system_prompt
        assert q2.model_dict == q.model_dict

    def test_from_dict_with_response_model(self):
        """Test deserialization recreates response model from schema."""
        class FollowUp(BaseModel):
            question: str
            reasoning: str

        model = Model("gpt-4o-mini")
        q = QuestionInterviewerThinking(
            question_name="test",
            question_text="Test question.",
            model=model,
            response_model=FollowUp,
        )
        d = q.to_dict()
        
        q2 = QuestionInterviewerThinking.from_dict(d)
        
        # Should have a dynamically created response model
        assert q2.user_response_model is not None
        schema = q2.get_response_schema()
        assert "question" in schema["properties"]
        assert "reasoning" in schema["properties"]

    def test_round_trip_via_question_base(self):
        """Test round-trip serialization via QuestionBase.from_dict."""
        model = Model("gpt-4o-mini")
        q = QuestionInterviewerThinking(
            question_name="test",
            question_text="Test question.",
            system_prompt="Be helpful.",
            model=model,
        )
        d = q.to_dict()
        
        q2 = QuestionBase.from_dict(d)
        
        assert isinstance(q2, QuestionInterviewerThinking)
        assert q2.question_name == q.question_name
        assert q2.question_text == q.question_text


class TestQuestionInterviewerThinkingMethods:
    """Tests for question methods."""

    def test_get_model(self):
        """Test that get_model returns a working Model instance."""
        model = Model("gpt-4o-mini")
        q = QuestionInterviewerThinking(
            question_name="test",
            question_text="Test question.",
            model=model,
        )
        
        retrieved_model = q.get_model()
        assert retrieved_model.model == "gpt-4o-mini"

    def test_get_response_schema_without_model(self):
        """Test get_response_schema returns None when no response_model."""
        model = Model("gpt-4o-mini")
        q = QuestionInterviewerThinking(
            question_name="test",
            question_text="Test question.",
            model=model,
        )
        assert q.get_response_schema() is None

    def test_simulate_answer_free_text(self):
        """Test _simulate_answer for free text mode."""
        model = Model("gpt-4o-mini")
        q = QuestionInterviewerThinking(
            question_name="test",
            question_text="Test question.",
            model=model,
        )
        
        simulated = q._simulate_answer()
        assert "answer" in simulated
        assert isinstance(simulated["answer"], str)
        assert "generated_tokens" in simulated

    def test_simulate_answer_structured(self):
        """Test _simulate_answer for structured output mode."""
        class FollowUp(BaseModel):
            question: str
            reasoning: str

        model = Model("gpt-4o-mini")
        q = QuestionInterviewerThinking(
            question_name="test",
            question_text="Test question.",
            model=model,
            response_model=FollowUp,
        )
        
        simulated = q._simulate_answer()
        assert "answer" in simulated
        assert isinstance(simulated["answer"], dict)
        assert "question" in simulated["answer"]
        assert "reasoning" in simulated["answer"]

    def test_question_html_content(self):
        """Test HTML content generation."""
        model = Model("gpt-4o-mini")
        q = QuestionInterviewerThinking(
            question_name="test",
            question_text="Test question.",
            system_prompt="Be helpful.",
            model=model,
        )
        
        html = q.question_html_content
        assert "Test question." in html
        assert "Be helpful." in html
        assert "gpt-4o-mini" in html

    def test_data_property(self):
        """Test the data property returns expected fields."""
        model = Model("gpt-4o-mini")
        q = QuestionInterviewerThinking(
            question_name="test",
            question_text="Test question.",
            system_prompt="Be helpful.",
            model=model,
        )
        
        data = q.data
        assert data["question_name"] == "test"
        assert data["question_text"] == "Test question."
        assert data["system_prompt"] == "Be helpful."
        assert "model" in data


class TestInvigilatorSelection:
    """Tests for correct invigilator selection."""

    def test_agent_selects_correct_invigilator(self):
        """Test that Agent selects InvigilatorInterviewerThinking for this question type."""
        from edsl.agents import Agent
        from edsl.invigilators import InvigilatorInterviewerThinking
        
        agent = Agent(traits={"age": 30})
        q = QuestionInterviewerThinking.example()
        
        invigilator_class = agent.invigilator.get_invigilator_class(q)
        
        assert invigilator_class == InvigilatorInterviewerThinking


class TestQuestionInterviewerThinkingInSurvey:
    """Tests for using the question in surveys."""

    def test_question_in_survey(self):
        """Test that the question can be added to a survey."""
        from edsl.surveys import Survey
        from edsl.questions import QuestionFreeText
        
        q1 = QuestionFreeText(
            question_name="q1",
            question_text="What is your favorite food?"
        )
        q2 = QuestionInterviewerThinking.example()
        
        survey = Survey([q1, q2])
        
        assert len(survey.questions) == 2
        assert survey.questions[1].question_type == "interviewer_thinking"

    def test_question_with_jinja_template(self):
        """Test that question text can contain Jinja2 templates."""
        model = Model("gpt-4o-mini")
        q = QuestionInterviewerThinking(
            question_name="follow_up",
            question_text="The subject said {{ q1.answer }}. What's a follow-up?",
            model=model,
        )
        
        # The template shouldn't be rendered at construction time
        assert "{{ q1.answer }}" in q.question_text
