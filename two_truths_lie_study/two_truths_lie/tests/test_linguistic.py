"""Tests for linguistic analysis module."""

import pytest
from src.linguistic import (
    LinguisticAnalyzer,
    SpecificityScore,
    HedgingAnalysis,
    SourceCitationAnalysis,
    QuestionTypeAnalysis
)
from src.models import Story, Answer, Question


@pytest.fixture
def analyzer():
    """Create a linguistic analyzer instance."""
    return LinguisticAnalyzer()


@pytest.fixture
def specific_story():
    """Create a story with high specificity."""
    return Story.create(
        storyteller_id="A",
        content="""In 1969, Neil Armstrong landed on the Moon at 20:17 UTC.
        The Apollo 11 mission traveled 238,855 miles to reach its destination.
        Dr. Werner von Braun, Director of NASA's Marshall Space Flight Center,
        oversaw the Saturn V rocket development. The lunar module weighed 33,500 pounds
        and had a 95.8% mission success rate.""",
        source_cited="NASA Apollo Archives"
    )


@pytest.fixture
def vague_story():
    """Create a story with low specificity."""
    return Story.create(
        storyteller_id="B",
        content="""A long time ago, some people went to space. They went really far
        and did some interesting things. It was a big achievement for everyone involved.
        Many experts worked on the project for years."""
    )


@pytest.fixture
def hedged_story():
    """Create a story with heavy hedging."""
    return Story.create(
        storyteller_id="C",
        content="""I think it was maybe in the 1960s or around that time when
        apparently some scientists possibly discovered something interesting.
        It seems like they might have found evidence that could suggest there
        was probably some kind of phenomenon. It appears they were somewhat
        uncertain about the results."""
    )


@pytest.fixture
def confident_story():
    """Create a story with minimal hedging."""
    return Story.create(
        storyteller_id="D",
        content="""In 1953, Watson and Crick discovered the double helix structure
        of DNA. They published their findings in Nature. The discovery revolutionized
        biology and earned them the Nobel Prize in 1962."""
    )


class TestSpecificityAnalysis:
    """Tests for specificity scoring."""

    def test_high_specificity_score(self, analyzer, specific_story):
        """Story with dates, numbers, and names should score high."""
        analysis = analyzer.analyze_story(specific_story)

        assert analysis.specificity.score >= 7
        assert analysis.specificity.num_dates >= 1  # 1969
        assert analysis.specificity.num_numbers >= 3  # Multiple numbers
        assert analysis.specificity.num_proper_nouns >= 3  # Armstrong, Armstrong, Braun, etc.

    def test_low_specificity_score(self, analyzer, vague_story):
        """Vague story should score low."""
        analysis = analyzer.analyze_story(vague_story)

        assert analysis.specificity.score <= 4
        assert analysis.specificity.concrete_detail_density < 2.0

    def test_date_detection(self, analyzer):
        """Should detect various date formats."""
        text = "In 1969, on 7/20/69, and 07-20-1969"
        spec = analyzer.calculate_specificity(text, 10)

        assert spec.num_dates >= 2  # At least year and date formats

    def test_number_detection(self, analyzer):
        """Should detect numbers with various formats."""
        text = "The price was 1,000 dollars, approximately 99.5% accurate"
        spec = analyzer.calculate_specificity(text, 10)

        assert spec.num_numbers >= 1
        assert spec.num_percentages >= 1

    def test_measurement_detection(self, analyzer):
        """Should detect measurements with units."""
        text = "The distance was 238,855 miles or 384,400 km"
        spec = analyzer.calculate_specificity(text, 10)

        assert spec.num_measurements >= 1

    def test_proper_noun_detection(self, analyzer):
        """Should detect proper nouns (not sentence-initial)."""
        text = "The scientist was Albert Einstein. Marie Curie also contributed."
        spec = analyzer.calculate_specificity(text, 10)

        # Should detect Einstein and Curie (not "The" or "Marie" after period)
        assert spec.num_proper_nouns >= 2

    def test_concrete_detail_density(self, analyzer):
        """Should calculate density correctly."""
        # 5 concrete details in 20 words = 25 per 100 words
        text = "In 1969 at 100 km altitude, Dr. Smith measured 75% accuracy."
        spec = analyzer.calculate_specificity(text, 20)

        # Approximately 25 details per 100 words
        assert 20 <= spec.concrete_detail_density <= 30


class TestHedgingAnalysis:
    """Tests for hedging detection."""

    def test_high_hedging_score(self, analyzer, hedged_story):
        """Story with many hedges should score high."""
        analysis = analyzer.analyze_story(hedged_story)

        assert analysis.hedging.hedging_score >= 7
        assert analysis.hedging.hedge_count >= 8

    def test_low_hedging_score(self, analyzer, confident_story):
        """Confident story should score low."""
        analysis = analyzer.analyze_story(confident_story)

        assert analysis.hedging.hedging_score <= 3
        assert analysis.hedging.hedge_count <= 2

    def test_epistemic_hedges(self, analyzer):
        """Should detect epistemic hedges."""
        text = "Maybe it was possibly true, perhaps even probable."
        hedge = analyzer.calculate_hedging(text, 10)

        assert hedge.hedge_types['epistemic'] >= 3
        assert 'maybe' in hedge.hedging_words_found
        assert 'possibly' in hedge.hedging_words_found

    def test_approximator_hedges(self, analyzer):
        """Should detect approximators."""
        text = "About 100 people, roughly around 50%, approximately half."
        hedge = analyzer.calculate_hedging(text, 10)

        assert hedge.hedge_types['approximator'] >= 2

    def test_modal_hedges(self, analyzer):
        """Should detect modal hedges."""
        text = "It might be true, could be false, would depend on context."
        hedge = analyzer.calculate_hedging(text, 12)

        assert hedge.hedge_types['modal'] >= 3

    def test_indirect_speech(self, analyzer):
        """Should detect indirect speech."""
        text = "I think it's true. I believe it happened. It seems correct."
        hedge = analyzer.calculate_hedging(text, 12)

        assert hedge.hedge_types['indirect'] >= 2

    def test_hedge_density(self, analyzer):
        """Should calculate hedge density correctly."""
        # 5 hedges in 20 words = 25 per 100 words
        text = "I think maybe it might possibly be somewhat true today."
        # 12 words, 5 hedges
        hedge = analyzer.calculate_hedging(text, 12)

        # Approximately 40 hedges per 100 words
        assert 30 <= hedge.hedge_density <= 50


class TestSourceCitationDetection:
    """Tests for source citation detection."""

    def test_explicit_citation_detection(self, analyzer):
        """Should detect explicit citations."""
        text = "According to NASA, the mission succeeded."
        citation = analyzer.detect_source_citation(text)

        assert citation.has_source
        assert citation.explicit_citations
        assert citation.source_count >= 1

    def test_research_source_detection(self, analyzer):
        """Should detect research sources."""
        text = "The study published in Nature showed significant results."
        citation = analyzer.detect_source_citation(text)

        assert citation.has_source
        assert 'research' in citation.source_types

    def test_institutional_source_detection(self, analyzer):
        """Should detect institutional sources."""
        text = "Harvard University research indicated the findings."
        citation = analyzer.detect_source_citation(text)

        assert citation.has_source
        assert 'institution' in citation.source_types

    def test_person_source_detection(self, analyzer):
        """Should detect person sources."""
        text = "Dr. Johnson confirmed the results."
        citation = analyzer.detect_source_citation(text)

        assert citation.has_source
        assert 'person' in citation.source_types

    def test_no_source_detection(self, analyzer):
        """Should detect when no source is cited."""
        text = "This is a story without any citations."
        citation = analyzer.detect_source_citation(text)

        assert not citation.has_source
        assert citation.source_count == 0


class TestQuestionClassification:
    """Tests for question type classification."""

    def test_yes_no_question(self, analyzer):
        """Should classify yes/no questions."""
        question = Question(
            judge_model="claude",
            target_storyteller_id="A",
            content="Did this happen in 1969?",
            question_number=1
        )
        classification = analyzer.classify_question(question)

        assert classification.question_type == 'yes_no'

    def test_what_question(self, analyzer):
        """Should classify 'what' questions."""
        question = Question(
            judge_model="claude",
            target_storyteller_id="A",
            content="What was the exact date?",
            question_number=1
        )
        classification = analyzer.classify_question(question)

        assert classification.question_type == 'what'

    def test_why_question(self, analyzer):
        """Should classify 'why' questions."""
        question = Question(
            judge_model="claude",
            target_storyteller_id="A",
            content="Why did they choose that location?",
            question_number=1
        )
        classification = analyzer.classify_question(question)

        assert classification.question_type == 'why'

    def test_how_question(self, analyzer):
        """Should classify 'how' questions."""
        question = Question(
            judge_model="claude",
            target_storyteller_id="A",
            content="How did they accomplish this?",
            question_number=1
        )
        classification = analyzer.classify_question(question)

        assert classification.question_type == 'how'

    def test_verification_request(self, analyzer):
        """Should detect verification requests."""
        question = Question(
            judge_model="claude",
            target_storyteller_id="A",
            content="Can you provide a source for that claim?",
            question_number=1
        )
        classification = analyzer.classify_question(question)

        assert classification.is_verification_request

    def test_adversarial_question(self, analyzer):
        """Should detect adversarial questions."""
        question = Question(
            judge_model="claude",
            target_storyteller_id="A",
            content="Are you really sure about that? Can you prove it?",
            question_number=1
        )
        classification = analyzer.classify_question(question)

        assert classification.is_adversarial

    def test_neutral_question(self, analyzer):
        """Should detect neutral questions."""
        question = Question(
            judge_model="claude",
            target_storyteller_id="A",
            content="Where did this take place?",
            question_number=1
        )
        classification = analyzer.classify_question(question)

        assert classification.question_type == 'where'
        assert not classification.is_adversarial


class TestAnswerAnalysis:
    """Tests for answer analysis."""

    def test_answer_specificity(self, analyzer):
        """Should analyze answer specificity."""
        answer = Answer.create(
            storyteller_id="A",
            question_number=1,
            content="It happened on July 20, 1969 at 20:17 UTC at the Sea of Tranquility."
        )
        analysis = analyzer.analyze_answer(answer)

        assert analysis.specificity.score >= 6
        assert analysis.specificity.num_dates >= 1

    def test_answer_hedging(self, analyzer):
        """Should analyze answer hedging."""
        answer = Answer.create(
            storyteller_id="A",
            question_number=1,
            content="I think it was maybe around that time, possibly in the summer."
        )
        analysis = analyzer.analyze_answer(answer)

        assert analysis.hedging.hedge_count >= 3


class TestRoundAnalysis:
    """Tests for complete round analysis."""

    def test_round_linguistic_analysis(self, analyzer, specific_story, vague_story):
        """Should analyze complete round linguistics."""
        stories = [specific_story, vague_story]
        answers = [
            Answer.create("A", 1, "Yes, that's correct."),
            Answer.create("B", 1, "I think so, maybe.")
        ]
        questions = [
            Question("judge", "A", "Is this true?", 1),
            Question("judge", "B", "Can you prove it?", 1)
        ]

        analysis = analyzer.analyze_round_linguistics(stories, answers, questions)

        assert len(analysis['stories']) == 2
        assert len(analysis['answers']) == 2
        assert len(analysis['questions']) == 2

        # Verify story differences
        assert analysis['stories'][0].specificity.score > analysis['stories'][1].specificity.score

        # Verify question classification
        assert analysis['questions'][0].question_type == 'yes_no'
        assert analysis['questions'][1].is_verification_request
