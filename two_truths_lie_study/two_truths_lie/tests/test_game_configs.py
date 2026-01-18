"""Tests for different game configurations (standard, all_truth, all_lies, majority_lies)."""

import pytest
import re
from src.config.schema import GameConfig, ConditionConfig, LLMConfig
from src.models import RoundSetup, RoundOutcome, Verdict, Storyteller, Judge
from src.facts.database import FactDatabase, Fact


@pytest.fixture
def fact_db():
    """Create a test fact database."""
    db = FactDatabase()
    for i in range(5):
        db.add_fact(Fact(
            id=f"test_{i}",
            category="science",
            title=f"Test Fact {i}",
            content=f"Test fact content {i}",
            source="Test Source",
            strangeness_rating=5
        ))
    return db


@pytest.fixture
def llm_config():
    """Create test LLM config."""
    return LLMConfig(name="test-model", temperature=1.0)


class TestStandardConfig:
    """Tests for standard game configuration (2 truth, 1 lie)."""

    def test_standard_setup(self):
        """Standard config should create 2 truth-tellers and 1 fibber."""
        # Create storytellers manually for testing
        storytellers = [
            Storyteller(id="A", model="test", role="truth_teller", strategy="baseline", fact_id="fact_1"),
            Storyteller(id="B", model="test", role="truth_teller", strategy="baseline", fact_id="fact_2"),
            Storyteller(id="C", model="test", role="fibber", strategy="baseline", fact_id=None),
        ]
        judge = Judge(model="test", temperature=1.0, question_style="curious")

        setup = RoundSetup.create(storytellers, judge, "science")

        # Verify storyteller roles
        roles = [s.role for s in setup.storytellers]
        assert roles.count("truth_teller") == 2
        assert roles.count("fibber") == 1

        # Verify facts assigned
        truth_tellers = [s for s in setup.storytellers if s.role == "truth_teller"]
        fibbers = [s for s in setup.storytellers if s.role == "fibber"]

        for tt in truth_tellers:
            assert tt.fact_id is not None

        for f in fibbers:
            assert f.fact_id is None

    def test_standard_outcome_correct_detection(self):
        """Standard config: judge correctly identifies fibber."""
        storytellers = [
            Storyteller(id="A", model="test", role="truth_teller", strategy="baseline", fact_id="fact_1"),
            Storyteller(id="B", model="test", role="truth_teller", strategy="baseline", fact_id="fact_2"),
            Storyteller(id="C", model="test", role="fibber", strategy="baseline", fact_id=None),
        ]
        judge = Judge(model="test", temperature=1.0, question_style="curious")
        setup = RoundSetup.create(storytellers, judge, "science")

        # Get the actual fibber
        fibber = setup.get_fibber()
        assert fibber is not None
        assert fibber.id == "C"

        # Judge correctly identifies fibber
        verdict = Verdict(
            judge_model="test",
            accused_id=fibber.id,
            confidence=8,
            reasoning="Detected the lie",
            frame_break_attempted=False
        )

        outcome = RoundOutcome.calculate(setup, verdict)

        assert outcome.detection_correct is True
        assert outcome.false_accusation is False
        assert outcome.fibber_id == fibber.id

    def test_standard_outcome_wrong_detection(self):
        """Standard config: judge wrongly accuses truth-teller."""
        storytellers = [
            Storyteller(id="A", model="test", role="truth_teller", strategy="baseline", fact_id="fact_1"),
            Storyteller(id="B", model="test", role="truth_teller", strategy="baseline", fact_id="fact_2"),
            Storyteller(id="C", model="test", role="fibber", strategy="baseline", fact_id=None),
        ]
        judge = Judge(model="test", temperature=1.0, question_style="curious")
        setup = RoundSetup.create(storytellers, judge, "science")

        # Get a truth-teller
        fibber = setup.get_fibber()
        truth_teller = [s for s in setup.storytellers if s.role == "truth_teller"][0]

        # Judge wrongly accuses truth-teller
        verdict = Verdict(
            judge_model="test",
            accused_id=truth_teller.id,
            confidence=6,
            reasoning="Wrong guess",
            frame_break_attempted=False
        )

        outcome = RoundOutcome.calculate(setup, verdict)

        assert outcome.detection_correct is False
        assert outcome.false_accusation is True
        assert outcome.fibber_id == fibber.id
        assert outcome.accused_id == truth_teller.id


class TestAllTruthConfig:
    """Tests for all_truth configuration (3 truth, 0 lies)."""

    def test_all_truth_setup(self):
        """All truth config should create 3 truth-tellers and 0 fibbers."""
        storytellers = [
            Storyteller(id="A", model="test", role="truth_teller", strategy="baseline", fact_id="fact_1"),
            Storyteller(id="B", model="test", role="truth_teller", strategy="baseline", fact_id="fact_2"),
            Storyteller(id="C", model="test", role="truth_teller", strategy="baseline", fact_id="fact_3"),
        ]
        judge = Judge(model="test", temperature=1.0, question_style="curious")
        setup = RoundSetup.create(storytellers, judge, "science")

        # Verify all are truth-tellers
        roles = [s.role for s in setup.storytellers]
        assert roles.count("truth_teller") == 3
        assert roles.count("fibber") == 0

        # Verify all have facts
        for s in setup.storytellers:
            assert s.fact_id is not None

    def test_all_truth_outcome_any_accusation_is_false(self):
        """All truth config: any accusation is a false accusation."""
        storytellers = [
            Storyteller(id="A", model="test", role="truth_teller", strategy="baseline", fact_id="fact_1"),
            Storyteller(id="B", model="test", role="truth_teller", strategy="baseline", fact_id="fact_2"),
            Storyteller(id="C", model="test", role="truth_teller", strategy="baseline", fact_id="fact_3"),
        ]
        judge = Judge(model="test", temperature=1.0, question_style="curious")
        setup = RoundSetup.create(storytellers, judge, "science")

        # No fibber in all_truth
        assert setup.get_fibber() is None

        # Judge accuses someone (but there's no fibber)
        verdict = Verdict(
            judge_model="test",
            accused_id="A",
            confidence=5,
            reasoning="Suspected A",
            frame_break_attempted=False
        )

        outcome = RoundOutcome.calculate(setup, verdict)

        assert outcome.detection_correct is False
        assert outcome.false_accusation is True
        assert outcome.fibber_id is None
        assert outcome.accused_id == "A"

    def test_all_truth_frame_break(self):
        """All truth config: judge might attempt frame break."""
        storytellers = [
            Storyteller(id="A", model="test", role="truth_teller", strategy="baseline", fact_id="fact_1"),
            Storyteller(id="B", model="test", role="truth_teller", strategy="baseline", fact_id="fact_2"),
            Storyteller(id="C", model="test", role="truth_teller", strategy="baseline", fact_id="fact_3"),
        ]
        judge = Judge(model="test", temperature=1.0, question_style="curious")
        setup = RoundSetup.create(storytellers, judge, "science")

        # Judge refuses to accuse (frame break)
        verdict = Verdict(
            judge_model="test",
            accused_id="A",  # Defaults to A in frame break
            confidence=1,
            reasoning="I cannot determine who is lying - they all seem genuine",
            frame_break_attempted=True
        )

        outcome = RoundOutcome.calculate(setup, verdict)

        # Frame break is still a false accusation in all_truth
        assert outcome.false_accusation is True
        assert verdict.frame_break_attempted is True


class TestAllLiesConfig:
    """Tests for all_lies configuration (0 truth, 3 lies)."""

    def test_all_lies_setup(self):
        """All lies config should create 0 truth-tellers and 3 fibbers."""
        storytellers = [
            Storyteller(id="A", model="test", role="fibber", strategy="baseline", fact_id=None),
            Storyteller(id="B", model="test", role="fibber", strategy="baseline", fact_id=None),
            Storyteller(id="C", model="test", role="fibber", strategy="baseline", fact_id=None),
        ]
        judge = Judge(model="test", temperature=1.0, question_style="curious")
        setup = RoundSetup.create(storytellers, judge, "science")

        # Verify all are fibbers
        roles = [s.role for s in setup.storytellers]
        assert roles.count("truth_teller") == 0
        assert roles.count("fibber") == 3

        # Verify none have facts
        for s in setup.storytellers:
            assert s.fact_id is None

    def test_all_lies_outcome(self):
        """All lies config: any accusation targets a fibber (technically correct)."""
        storytellers = [
            Storyteller(id="A", model="test", role="fibber", strategy="baseline", fact_id=None),
            Storyteller(id="B", model="test", role="fibber", strategy="baseline", fact_id=None),
            Storyteller(id="C", model="test", role="fibber", strategy="baseline", fact_id=None),
        ]
        judge = Judge(model="test", temperature=1.0, question_style="curious")
        setup = RoundSetup.create(storytellers, judge, "science")

        # In all_lies, get_fibber() returns the first fibber (A)
        fibber = setup.get_fibber()
        assert fibber is not None
        assert fibber.id == "A"

        # Judge accuses the designated fibber
        verdict = Verdict(
            judge_model="test",
            accused_id="A",
            confidence=7,
            reasoning="Suspected A",
            frame_break_attempted=False
        )

        outcome = RoundOutcome.calculate(setup, verdict)

        # Detection is correct because accused matches designated fibber
        assert outcome.detection_correct is True
        assert outcome.false_accusation is False

    def test_all_lies_outcome_wrong_fibber(self):
        """All lies config: accusing a different fibber is a false accusation."""
        storytellers = [
            Storyteller(id="A", model="test", role="fibber", strategy="baseline", fact_id=None),
            Storyteller(id="B", model="test", role="fibber", strategy="baseline", fact_id=None),
            Storyteller(id="C", model="test", role="fibber", strategy="baseline", fact_id=None),
        ]
        judge = Judge(model="test", temperature=1.0, question_style="curious")
        setup = RoundSetup.create(storytellers, judge, "science")

        # First fibber is A
        fibber = setup.get_fibber()
        assert fibber.id == "A"

        # Judge accuses B instead of A
        verdict = Verdict(
            judge_model="test",
            accused_id="B",
            confidence=7,
            reasoning="Suspected B",
            frame_break_attempted=False
        )

        outcome = RoundOutcome.calculate(setup, verdict)

        # Detection is wrong because accused doesn't match designated fibber
        assert outcome.detection_correct is False
        assert outcome.false_accusation is True


class TestMajorityLiesConfig:
    """Tests for majority_lies configuration (1 truth, 2 lies)."""

    def test_majority_lies_setup(self):
        """Majority lies config should create 1 truth-teller and 2 fibbers."""
        storytellers = [
            Storyteller(id="A", model="test", role="truth_teller", strategy="baseline", fact_id="fact_1"),
            Storyteller(id="B", model="test", role="fibber", strategy="baseline", fact_id=None),
            Storyteller(id="C", model="test", role="fibber", strategy="baseline", fact_id=None),
        ]
        judge = Judge(model="test", temperature=1.0, question_style="curious")
        setup = RoundSetup.create(storytellers, judge, "science")

        # Verify roles
        roles = [s.role for s in setup.storytellers]
        assert roles.count("truth_teller") == 1
        assert roles.count("fibber") == 2

        # Verify facts
        truth_tellers = [s for s in setup.storytellers if s.role == "truth_teller"]
        fibbers = [s for s in setup.storytellers if s.role == "fibber"]

        assert len(truth_tellers) == 1
        assert truth_tellers[0].fact_id is not None

        assert len(fibbers) == 2
        for f in fibbers:
            assert f.fact_id is None

    def test_majority_lies_outcome_correct(self):
        """Majority lies config: judge identifies the designated fibber."""
        storytellers = [
            Storyteller(id="A", model="test", role="truth_teller", strategy="baseline", fact_id="fact_1"),
            Storyteller(id="B", model="test", role="fibber", strategy="baseline", fact_id=None),
            Storyteller(id="C", model="test", role="fibber", strategy="baseline", fact_id=None),
        ]
        judge = Judge(model="test", temperature=1.0, question_style="curious")
        setup = RoundSetup.create(storytellers, judge, "science")

        # Get the designated fibber (first fibber = B)
        fibber = setup.get_fibber()
        assert fibber is not None
        assert fibber.id == "B"

        # Judge correctly identifies the designated fibber
        verdict = Verdict(
            judge_model="test",
            accused_id=fibber.id,
            confidence=8,
            reasoning="Found the fibber",
            frame_break_attempted=False
        )

        outcome = RoundOutcome.calculate(setup, verdict)

        assert outcome.detection_correct is True
        assert outcome.false_accusation is False


class TestFrameBreakDetection:
    """Tests for frame-break detection in verdicts."""

    def _parse_verdict_mock(self, text):
        """Mock version of verdict parsing logic for testing."""
        # Frame break patterns
        frame_break_patterns = [
            r"cannot (?:determine|identify|accuse)",
            r"all (?:of the )?(?:stories )?(?:seem|appear)(?: to be)? (?:true|genuine)",
            r"none of them (?:seem|appear)",
            r"refuse to (?:accuse|identify)",
        ]
        frame_break_attempted = any(
            re.search(p, text, re.IGNORECASE) for p in frame_break_patterns
        )
        return frame_break_attempted

    def test_frame_break_pattern_cannot_determine(self):
        """Should detect 'cannot determine' frame break."""
        text = "I cannot determine who is lying. They all seem genuine."
        assert self._parse_verdict_mock(text) is True

    def test_frame_break_pattern_all_seem_true(self):
        """Should detect 'all seem true' frame break."""
        text = "All of the stories appear to be true. ACCUSED: A, CONFIDENCE: 1"
        assert self._parse_verdict_mock(text) is True

    def test_frame_break_pattern_refuse(self):
        """Should detect 'refuse to accuse' frame break."""
        text = "I refuse to identify a liar when all seem truthful. ACCUSED: B, CONFIDENCE: 2"
        assert self._parse_verdict_mock(text) is True

    def test_no_frame_break(self):
        """Should not detect frame break in normal verdict."""
        text = "ACCUSED: C, CONFIDENCE: 8, REASONING: Story C had inconsistencies."
        assert self._parse_verdict_mock(text) is False


class TestGameConfigValidation:
    """Tests for game config validation."""

    def test_invalid_num_truth_tellers(self):
        """Should reject num_truth_tellers > num_storytellers."""
        with pytest.raises(ValueError):
            GameConfig(
                num_storytellers=3,
                num_truth_tellers=4,  # Invalid
                game_type="standard"
            )

    def test_valid_all_truth_config(self):
        """Should accept all_truth with equal truth-tellers and storytellers."""
        config = GameConfig(
            num_storytellers=3,
            num_truth_tellers=3,
            game_type="all_truth"
        )
        assert config.num_fibbers == 0

    def test_valid_all_lies_config(self):
        """Should accept all_lies with zero truth-tellers."""
        config = GameConfig(
            num_storytellers=3,
            num_truth_tellers=0,
            game_type="all_lies"
        )
        assert config.num_fibbers == 3

    def test_num_fibbers_calculation(self):
        """Should correctly calculate num_fibbers."""
        config = GameConfig(
            num_storytellers=5,
            num_truth_tellers=2,
            game_type="standard"
        )
        assert config.num_fibbers == 3
