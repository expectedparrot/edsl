"""Tests for data models."""

import pytest
import json

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.storyteller import Storyteller, Judge
from src.models.story import Story
from src.models.qa import Question, Answer, QAExchange
from src.models.verdict import Verdict
from src.models.round import RoundSetup, RoundOutcome


class TestStoryteller:
    """Tests for Storyteller model."""

    def test_truth_teller_creation(self):
        """Test creating a truth-teller."""
        st = Storyteller(
            id="A",
            model="claude-3-5-sonnet",
            role="truth_teller",
            strategy="baseline",
            fact_id="fact_001"
        )
        assert st.is_truth_teller
        assert not st.is_fibber
        assert st.fact_id == "fact_001"

    def test_fibber_creation(self):
        """Test creating a fibber."""
        st = Storyteller(
            id="B",
            model="claude-3-5-sonnet",
            role="fibber",
            strategy="baseline",
            fact_id=None
        )
        assert st.is_fibber
        assert not st.is_truth_teller
        assert st.fact_id is None

    def test_truth_teller_requires_fact_id(self):
        """Test that truth-tellers must have a fact_id."""
        with pytest.raises(ValueError):
            Storyteller(
                id="A",
                model="claude-3-5-sonnet",
                role="truth_teller",
                strategy="baseline",
                fact_id=None
            )

    def test_fibber_rejects_fact_id(self):
        """Test that fibbers should not have a fact_id."""
        with pytest.raises(ValueError):
            Storyteller(
                id="A",
                model="claude-3-5-sonnet",
                role="fibber",
                strategy="baseline",
                fact_id="fact_001"
            )

    def test_serialization_roundtrip(self):
        """Test JSON serialization and deserialization."""
        st = Storyteller(
            id="A",
            model="claude-3-5-sonnet",
            role="truth_teller",
            strategy="level_k_1",
            fact_id="fact_001"
        )
        json_str = st.to_json()
        st2 = Storyteller.from_json(json_str)
        assert st == st2


class TestJudge:
    """Tests for Judge model."""

    def test_judge_creation(self):
        """Test creating a judge."""
        judge = Judge(
            model="claude-3-5-sonnet",
            temperature=0.8,
            question_style="adversarial"
        )
        assert judge.model == "claude-3-5-sonnet"
        assert judge.temperature == 0.8
        assert judge.question_style == "adversarial"


class TestStory:
    """Tests for Story model."""

    def test_story_creation(self):
        """Test creating a story with factory method."""
        story = Story.create(
            storyteller_id="A",
            content="This is a test story with multiple words.",
            source_cited="Test Source"
        )
        assert story.storyteller_id == "A"
        assert story.word_count == 8
        assert story.source_cited == "Test Source"

    def test_story_preview(self):
        """Test story preview generation."""
        long_content = " ".join(["word"] * 100)
        story = Story.create(storyteller_id="A", content=long_content)
        preview = story.get_preview(10)
        assert preview.endswith("...")
        assert len(preview.split()) <= 12  # 10 words + "..."


class TestVerdict:
    """Tests for Verdict model."""

    def test_verdict_creation(self):
        """Test creating a verdict."""
        verdict = Verdict(
            judge_model="claude-3-5-sonnet",
            accused_id="B",
            confidence=8,
            reasoning="The story had inconsistencies."
        )
        assert verdict.accused_id == "B"
        assert verdict.confidence == 8
        assert verdict.is_high_confidence

    def test_confidence_range_validation(self):
        """Test that confidence must be 1-10."""
        with pytest.raises(ValueError):
            Verdict(
                judge_model="claude-3-5-sonnet",
                accused_id="A",
                confidence=0,
                reasoning="Test"
            )

        with pytest.raises(ValueError):
            Verdict(
                judge_model="claude-3-5-sonnet",
                accused_id="A",
                confidence=11,
                reasoning="Test"
            )

    def test_confidence_properties(self):
        """Test high/low confidence properties."""
        high = Verdict(
            judge_model="test", accused_id="A",
            confidence=8, reasoning="Test"
        )
        assert high.is_high_confidence
        assert not high.is_low_confidence

        low = Verdict(
            judge_model="test", accused_id="A",
            confidence=2, reasoning="Test"
        )
        assert low.is_low_confidence
        assert not low.is_high_confidence


class TestRoundOutcome:
    """Tests for RoundOutcome model."""

    def test_correct_detection(self):
        """Test outcome when judge correctly identifies fibber."""
        # Create a mock setup with fibber at B
        storytellers = [
            Storyteller(id="A", model="test", role="truth_teller", fact_id="f1"),
            Storyteller(id="B", model="test", role="fibber"),
            Storyteller(id="C", model="test", role="truth_teller", fact_id="f2"),
        ]
        judge = Judge(model="test")
        setup = RoundSetup.create(
            storytellers=storytellers,
            judge=judge,
            fact_category="science"
        )

        verdict = Verdict(
            judge_model="test",
            accused_id="B",
            confidence=8,
            reasoning="Test"
        )

        outcome = RoundOutcome.calculate(setup, verdict)
        assert outcome.detection_correct
        assert not outcome.false_accusation
        assert outcome.fibber_id == "B"

    def test_incorrect_detection(self):
        """Test outcome when judge accuses wrong person."""
        storytellers = [
            Storyteller(id="A", model="test", role="truth_teller", fact_id="f1"),
            Storyteller(id="B", model="test", role="fibber"),
            Storyteller(id="C", model="test", role="truth_teller", fact_id="f2"),
        ]
        judge = Judge(model="test")
        setup = RoundSetup.create(
            storytellers=storytellers,
            judge=judge,
            fact_category="science"
        )

        verdict = Verdict(
            judge_model="test",
            accused_id="A",  # Wrong!
            confidence=7,
            reasoning="Test"
        )

        outcome = RoundOutcome.calculate(setup, verdict)
        assert not outcome.detection_correct
        assert outcome.false_accusation
        assert outcome.fibber_id == "B"
        assert outcome.accused_id == "A"
