"""Tests for prompt templates."""

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.prompts.base import BasePrompt
from src.prompts.strategies import STRATEGIES, get_strategy_instructions, get_available_strategies
from src.prompts.storyteller import TruthTellerPrompt, FibberPrompt, StorytellerAnswerPrompt
from src.prompts.judge import JudgeReviewPrompt, JudgeQuestionPrompt, JudgeVerdictPrompt
from src.facts.database import Fact


class TestStrategies:
    """Tests for strategy definitions."""

    def test_all_strategies_exist(self):
        """Test that expected strategies are defined."""
        expected = ["baseline", "level_k_0", "level_k_1", "source_heavy", "detail_granular"]
        for strategy in expected:
            assert strategy in STRATEGIES

    def test_get_strategy_instructions(self):
        """Test getting strategy instructions."""
        instructions = get_strategy_instructions("source_heavy")
        assert "sources" in instructions.lower()

    def test_unknown_strategy_raises_error(self):
        """Test that unknown strategy raises ValueError."""
        with pytest.raises(ValueError):
            get_strategy_instructions("nonexistent_strategy")

    def test_get_available_strategies(self):
        """Test getting list of available strategies."""
        strategies = get_available_strategies()
        assert "baseline" in strategies
        assert len(strategies) >= 5


class TestStorytellerPrompts:
    """Tests for storyteller prompts."""

    @pytest.fixture
    def sample_fact(self):
        return Fact(
            id="test_001",
            category="science",
            title="Test Fact",
            content="This is a fascinating test fact about science.",
            source="Test Source",
            strangeness_rating=7
        )

    def test_truth_teller_prompt_renders(self, sample_fact):
        """Test that truth-teller prompt renders correctly."""
        prompt = TruthTellerPrompt(fact=sample_fact, strategy="baseline")
        rendered = prompt.render()

        assert "TRUTH-TELLER" in rendered
        assert sample_fact.content in rendered
        assert "science" in rendered.lower()

    def test_fibber_prompt_renders(self):
        """Test that fibber prompt renders correctly."""
        prompt = FibberPrompt(category="history", strategy="baseline")
        rendered = prompt.render()

        assert "FIBBER" in rendered
        assert "history" in rendered.lower()
        assert "fabricate" in rendered.lower()

    def test_truth_fibber_structural_parity(self, sample_fact):
        """Test that truth and fibber prompts have similar structure.

        This is critical to avoid giving the judge unintended tells.
        """
        truth_prompt = TruthTellerPrompt(fact=sample_fact, strategy="baseline")
        fibber_prompt = FibberPrompt(category="science", strategy="baseline")

        truth_rendered = truth_prompt.render()
        fibber_rendered = fibber_prompt.render()

        # Both should have the same key sections
        for section in [
            "STORYTELLING REQUIREMENTS",
            "SOURCE CITATION",
            "CATEGORY",
            "Why Would I Lie"
        ]:
            assert section in truth_rendered, f"Missing '{section}' in truth prompt"
            assert section in fibber_rendered, f"Missing '{section}' in fibber prompt"

    def test_strategy_injection(self, sample_fact):
        """Test that strategy instructions are injected."""
        prompt = TruthTellerPrompt(fact=sample_fact, strategy="source_heavy")
        rendered = prompt.render()

        assert "source" in rendered.lower()
        assert "credible" in rendered.lower()

    def test_answer_prompt_renders(self):
        """Test that answer prompt renders correctly."""
        prompt = StorytellerAnswerPrompt(
            story_content="My test story content.",
            question="What is the source?",
            is_truth_teller=True,
            word_min=25,
            word_max=150
        )
        rendered = prompt.render()

        assert "My test story content" in rendered
        assert "What is the source?" in rendered


class TestJudgePrompts:
    """Tests for judge prompts."""

    def test_review_prompt_renders(self):
        """Test that review prompt renders correctly."""
        stories = {
            "A": "Story from A about science.",
            "B": "Story from B about history.",
            "C": "Story from C about biology.",
        }
        prompt = JudgeReviewPrompt(stories=stories)
        rendered = prompt.render()

        assert "STORYTELLER A" in rendered
        assert "STORYTELLER B" in rendered
        assert "STORYTELLER C" in rendered
        assert "Story from A" in rendered

    def test_question_prompt_renders(self):
        """Test that question prompt renders correctly."""
        prompt = JudgeQuestionPrompt(
            target_id="B",
            story_content="Test story content.",
            question_number=2,
            total_questions=3,
            question_style="adversarial"
        )
        rendered = prompt.render()

        assert "STORYTELLER B" in rendered
        assert "Test story content" in rendered
        assert "question 2 of 3" in rendered.lower()
        assert "ADVERSARIAL" in rendered

    def test_question_prompt_with_previous_qa(self):
        """Test question prompt with previous Q&A context."""
        previous_qa = [
            {"question": "First question?", "answer": "First answer."}
        ]
        prompt = JudgeQuestionPrompt(
            target_id="A",
            story_content="Test story.",
            question_number=2,
            total_questions=3,
            previous_qa=previous_qa
        )
        rendered = prompt.render()

        assert "First question?" in rendered
        assert "First answer." in rendered

    def test_verdict_prompt_renders(self):
        """Test that verdict prompt renders correctly."""
        stories = {
            "A": "Story A",
            "B": "Story B",
        }
        qa_exchanges = {
            "A": [{"question": "Q1?", "answer": "A1."}],
            "B": [{"question": "Q2?", "answer": "A2."}],
        }
        prompt = JudgeVerdictPrompt(stories=stories, qa_exchanges=qa_exchanges)
        rendered = prompt.render()

        assert "ACCUSED" in rendered
        assert "CONFIDENCE" in rendered
        assert "REASONING" in rendered
        assert "Story A" in rendered
        assert "Q1?" in rendered
