"""Tests for InvigilatorInterviewerThinking.

This module tests the InvigilatorInterviewerThinking invigilator which handles
the execution of QuestionInterviewerThinking questions.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pydantic import BaseModel

from edsl.invigilators.invigilator_interviewer_thinking import InvigilatorInterviewerThinking
from edsl.questions.question_interviewer_thinking import QuestionInterviewerThinking
from edsl.language_models import Model
from edsl.agents import Agent
from edsl.scenarios import Scenario
from edsl.surveys import Survey


class TestInvigilatorInterviewerThinkingPrompts:
    """Tests for prompt handling in InvigilatorInterviewerThinking."""

    def test_get_prompts_basic(self):
        """Test that get_prompts returns user and system prompts."""
        model = Model("gpt-4o-mini")
        question = QuestionInterviewerThinking(
            question_name="test",
            question_text="Generate a follow-up question.",
            system_prompt="You are a researcher.",
            model=model,
        )
        
        agent = Agent()
        scenario = Scenario()
        survey = Survey([question])
        
        invigilator = InvigilatorInterviewerThinking(
            agent=agent,
            question=question,
            scenario=scenario,
            model=model,  # This is the interview's model, but should be ignored
            memory_plan=survey.memory_plan,
            current_answers={},
            survey=survey,
        )
        
        prompts = invigilator.get_prompts()
        
        assert "user_prompt" in prompts
        assert "system_prompt" in prompts
        assert prompts["user_prompt"].text == "Generate a follow-up question."
        assert prompts["system_prompt"].text == "You are a researcher."

    def test_render_template_with_prior_answers(self):
        """Test that Jinja2 templates in prompts are rendered with prior answers."""
        from edsl.questions import QuestionFreeText
        
        q1 = QuestionFreeText(
            question_name="q1",
            question_text="What is your favorite food?"
        )
        
        model = Model("gpt-4o-mini")
        question = QuestionInterviewerThinking(
            question_name="follow_up",
            question_text="The subject said {{ q1.answer }}. What's a follow-up?",
            model=model,
        )
        
        agent = Agent()
        scenario = Scenario()
        survey = Survey([q1, question])
        
        invigilator = InvigilatorInterviewerThinking(
            agent=agent,
            question=question,
            scenario=scenario,
            model=model,
            memory_plan=survey.memory_plan,
            current_answers={"q1": "pizza"},
            survey=survey,
        )
        
        prompts = invigilator.get_prompts()
        
        assert "pizza" in prompts["user_prompt"].text
        assert "{{ q1.answer }}" not in prompts["user_prompt"].text

    def test_render_template_with_scenario(self):
        """Test that Jinja2 templates are rendered with scenario variables."""
        model = Model("gpt-4o-mini")
        question = QuestionInterviewerThinking(
            question_name="analyze",
            question_text="Analyze the topic: {{ topic }}",
            model=model,
        )
        
        agent = Agent()
        scenario = Scenario({"topic": "climate change"})
        survey = Survey([question])
        
        invigilator = InvigilatorInterviewerThinking(
            agent=agent,
            question=question,
            scenario=scenario,
            model=model,
            memory_plan=survey.memory_plan,
            current_answers={},
            survey=survey,
        )
        
        prompts = invigilator.get_prompts()
        
        assert "climate change" in prompts["user_prompt"].text
        assert "{{ topic }}" not in prompts["user_prompt"].text

    def test_render_empty_template(self):
        """Test that empty system prompt is handled correctly."""
        model = Model("gpt-4o-mini")
        question = QuestionInterviewerThinking(
            question_name="test",
            question_text="Test question.",
            model=model,
            # No system_prompt specified
        )
        
        agent = Agent()
        scenario = Scenario()
        survey = Survey([question])
        
        invigilator = InvigilatorInterviewerThinking(
            agent=agent,
            question=question,
            scenario=scenario,
            model=model,
            memory_plan=survey.memory_plan,
            current_answers={},
            survey=survey,
        )
        
        prompts = invigilator.get_prompts()
        
        assert prompts["system_prompt"].text == ""


class TestInvigilatorInterviewerThinkingConstruction:
    """Tests for invigilator construction."""

    def test_basic_construction(self):
        """Test basic construction of the invigilator."""
        model = Model("gpt-4o-mini")
        question = QuestionInterviewerThinking.example()
        agent = Agent()
        scenario = Scenario()
        survey = Survey([question])
        
        invigilator = InvigilatorInterviewerThinking(
            agent=agent,
            question=question,
            scenario=scenario,
            model=model,
            memory_plan=survey.memory_plan,
            current_answers={},
            survey=survey,
        )
        
        assert invigilator.agent == agent
        assert invigilator.question == question
        assert invigilator.scenario == scenario


class TestInvigilatorInterviewerThinkingUsesQuestionModel:
    """Tests to verify the invigilator uses the question's embedded model."""

    @pytest.mark.asyncio
    async def test_uses_question_model_not_interview_model(self):
        """Test that async_answer_question uses the question's model."""
        from edsl.caching import Cache
        
        # Create two different models
        interview_model = Model("test", canned_response="Interview model response")
        question_model = Model("test", canned_response="Question model response")
        
        question = QuestionInterviewerThinking(
            question_name="test",
            question_text="Test question.",
            model=question_model,
        )
        
        agent = Agent()
        scenario = Scenario()
        survey = Survey([question])
        cache = Cache()
        
        invigilator = InvigilatorInterviewerThinking(
            agent=agent,
            question=question,
            scenario=scenario,
            model=interview_model,  # This should be ignored
            memory_plan=survey.memory_plan,
            current_answers={},
            survey=survey,
            cache=cache,
        )
        
        # The invigilator should use question.get_model() which returns question_model
        result = await invigilator.async_answer_question()
        
        # The answer should come from the question's model, not the interview's model
        assert result.answer == "Question model response"


class TestInvigilatorInterviewerThinkingStructuredOutput:
    """Tests for structured output handling."""

    @pytest.mark.asyncio
    async def test_json_parsing_without_response_model(self):
        """Test that JSON responses are correctly passed through."""
        from edsl.caching import Cache
        
        # Create a model that returns JSON (without using response_model to avoid test model limitations)
        model = Model("test", canned_response='{"question": "Why do you like that?", "reasoning": "To understand preferences"}')
        
        question = QuestionInterviewerThinking(
            question_name="test",
            question_text="Generate a follow-up.",
            model=model,
            # Note: not using response_model because test model doesn't support it
        )
        
        agent = Agent()
        scenario = Scenario()
        survey = Survey([question])
        cache = Cache()
        
        invigilator = InvigilatorInterviewerThinking(
            agent=agent,
            question=question,
            scenario=scenario,
            model=model,
            memory_plan=survey.memory_plan,
            current_answers={},
            survey=survey,
            cache=cache,
        )
        
        result = await invigilator.async_answer_question()
        
        # The answer should be the JSON string (without response_model, it's not parsed)
        assert result.answer is not None
        # The canned response is returned as-is for the test model
        assert "Why do you like that?" in str(result.answer)

    def test_structured_response_model_schema(self):
        """Test that response_model produces correct schema."""
        class FollowUp(BaseModel):
            question: str
            reasoning: str
        
        model = Model("gpt-4o-mini")
        
        question = QuestionInterviewerThinking(
            question_name="test",
            question_text="Generate a follow-up.",
            model=model,
            response_model=FollowUp,
        )
        
        # Verify the schema is correctly generated
        schema = question.get_response_schema()
        assert schema is not None
        assert "properties" in schema
        assert "question" in schema["properties"]
        assert "reasoning" in schema["properties"]


class TestInvigilatorInterviewerThinkingErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_error_handling_in_async_answer(self):
        """Test that error handling structures are in place."""
        from edsl.caching import Cache
        
        # Create a simple model for testing
        model = Model("test", canned_response="test response")
        
        question = QuestionInterviewerThinking(
            question_name="test",
            question_text="Test question.",
            model=model,
        )
        
        agent = Agent()
        scenario = Scenario()
        survey = Survey([question])
        cache = Cache()
        
        invigilator = InvigilatorInterviewerThinking(
            agent=agent,
            question=question,
            scenario=scenario,
            model=model,
            memory_plan=survey.memory_plan,
            current_answers={},
            survey=survey,
            cache=cache,
        )
        
        result = await invigilator.async_answer_question()
        
        # For a successful call, exception should be None
        assert result.exception_occurred is None
        # Answer should be present
        assert result.answer is not None
        # Validated should be True for successful calls
        assert result.validated is True
