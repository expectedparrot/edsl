"""Shared test fixtures and mock data generators."""

import uuid
from typing import Optional

from src.models import (
    Round, RoundSetup, RoundOutcome, Story, Verdict,
    Storyteller, Judge, Question, Answer, QAExchange
)
from src.config.schema import GameConfig


def create_mock_storyteller(
    storyteller_id: str = "A",
    role: str = "truth_teller",
    model: str = "claude-3-5-haiku-20241022",
    strategy: str = "baseline",
    fact_id: Optional[str] = "fact_001"
) -> Storyteller:
    """Create a mock storyteller for testing."""
    return Storyteller(
        id=storyteller_id,
        model=model,
        role=role,
        strategy=strategy,
        fact_id=fact_id
    )


def create_mock_judge(
    model: str = "claude-3-5-haiku-20241022",
    question_style: str = "curious",
    temperature: float = 0.7
) -> Judge:
    """Create a mock judge for testing."""
    return Judge(
        model=model,
        question_style=question_style,
        temperature=temperature
    )


def create_mock_setup(
    round_id: Optional[str] = None,
    judge_model: str = "claude-3-5-haiku-20241022",
    storyteller_model: str = "claude-3-5-haiku-20241022",
    strategy: str = "baseline",
    question_style: str = "curious",
    category: str = "science"
) -> RoundSetup:
    """Create a mock round setup for testing."""
    if round_id is None:
        round_id = str(uuid.uuid4())[:8]

    storytellers = [
        create_mock_storyteller("A", "truth_teller", storyteller_model, strategy, "fact_001"),
        create_mock_storyteller("B", "truth_teller", storyteller_model, strategy, "fact_002"),
        create_mock_storyteller("C", "fibber", storyteller_model, strategy, None),
    ]

    judge = create_mock_judge(judge_model, question_style)

    return RoundSetup(
        round_id=round_id,
        storytellers=storytellers,
        judge=judge,
        story_order=["A", "B", "C"],
        fact_category=category,
        condition_id=None
    )


def create_mock_story(
    storyteller_id: str = "A",
    word_count: int = 200
) -> Story:
    """Create a mock story for testing."""
    content = " ".join(["word"] * word_count)
    return Story.create(
        storyteller_id=storyteller_id,
        content=content,
        source_cited=None
    )


def create_mock_question(
    target_id: str = "A",
    question_number: int = 1,
    judge_model: str = "claude-3-5-haiku-20241022"
) -> Question:
    """Create a mock question for testing."""
    return Question(
        judge_model=judge_model,
        target_storyteller_id=target_id,
        content=f"Test question {question_number} for storyteller {target_id}?",
        question_number=question_number,
        generation_metadata={}
    )


def create_mock_answer(
    storyteller_id: str = "A",
    question_number: int = 1
) -> Answer:
    """Create a mock answer for testing."""
    return Answer.create(
        storyteller_id=storyteller_id,
        question_number=question_number,
        content="This is a test answer with some content.",
        generation_metadata={}
    )


def create_mock_qa_exchange(
    storyteller_id: str = "A",
    question_number: int = 1
) -> QAExchange:
    """Create a mock Q&A exchange for testing."""
    question = create_mock_question(storyteller_id, question_number)
    answer = create_mock_answer(storyteller_id, question_number)
    return QAExchange(question=question, answer=answer)


def create_mock_verdict(
    accused_id: str = "C",
    confidence: int = 8,
    judge_model: str = "claude-3-5-haiku-20241022"
) -> Verdict:
    """Create a mock verdict for testing."""
    return Verdict(
        judge_model=judge_model,
        accused_id=accused_id,
        confidence=confidence,
        reasoning="Test reasoning for the verdict.",
        frame_break_attempted=False,
        raw_response="ACCUSED: C\nCONFIDENCE: 8\nREASONING: Test reasoning."
    )


def create_mock_outcome(
    fibber_id: str = "C",
    accused_id: str = "C",
    detection_correct: bool = True,
    confidence: int = 8
) -> RoundOutcome:
    """Create a mock outcome for testing."""
    false_accusation = not detection_correct
    return RoundOutcome(
        detection_correct=detection_correct,
        false_accusation=false_accusation,
        fibber_id=fibber_id,
        accused_id=accused_id,
        confidence=confidence
    )


def create_mock_round(
    round_id: Optional[str] = None,
    judge_model: str = "claude-3-5-haiku-20241022",
    storyteller_model: str = "claude-3-5-haiku-20241022",
    strategy: str = "baseline",
    question_style: str = "curious",
    category: str = "science",
    confidence: int = 8,
    detection_correct: bool = True,
    duration: float = 60.0
) -> Round:
    """Create a complete mock round for testing.

    Args:
        round_id: Optional round ID (auto-generated if None)
        judge_model: Model name for judge
        storyteller_model: Model name for storytellers
        strategy: Storytelling strategy
        question_style: Judge question style
        category: Fact category
        confidence: Verdict confidence (1-10)
        detection_correct: Whether judge correctly identified fibber
        duration: Round duration in seconds

    Returns:
        Complete Round object
    """
    setup = create_mock_setup(
        round_id=round_id,
        judge_model=judge_model,
        storyteller_model=storyteller_model,
        strategy=strategy,
        question_style=question_style,
        category=category
    )

    # Create stories for each storyteller
    stories = [
        create_mock_story("A", 200),
        create_mock_story("B", 210),
        create_mock_story("C", 190)
    ]

    # Create Q&A exchanges (one per storyteller for simplicity)
    qa_exchanges = [
        create_mock_qa_exchange("A", 1),
        create_mock_qa_exchange("B", 1),
        create_mock_qa_exchange("C", 1)
    ]

    # Create verdict
    fibber_id = "C"
    accused_id = fibber_id if detection_correct else "A"
    verdict = create_mock_verdict(accused_id, confidence, judge_model)

    # Create outcome
    outcome = create_mock_outcome(fibber_id, accused_id, detection_correct, confidence)

    return Round(
        setup=setup,
        stories=stories,
        qa_exchanges=qa_exchanges,
        verdict=verdict,
        outcome=outcome,
        duration_seconds=duration
    )
