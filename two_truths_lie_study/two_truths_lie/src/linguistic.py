"""Linguistic analysis for Two Truths and a Lie stories and answers.

This module provides tools to analyze linguistic features of stories and answers
to identify patterns that might correlate with deception or truth-telling.
"""

import re
from dataclasses import dataclass
from typing import List, Dict, Literal
from collections import Counter

from .models import Story, Answer, Question


# Linguistic feature patterns
HEDGING_WORDS = {
    # Epistemic hedges (uncertainty about knowledge)
    'maybe', 'perhaps', 'possibly', 'probably', 'apparently', 'seemingly',
    'supposedly', 'allegedly', 'presumably', 'conceivably',

    # Approximators
    'about', 'around', 'roughly', 'approximately', 'nearly', 'almost',
    'sort of', 'kind of', 'more or less', 'essentially', 'basically',

    # Modal hedges
    'might', 'could', 'would', 'should', 'may', 'can',

    # Qualifiers
    'somewhat', 'rather', 'quite', 'fairly', 'relatively',
    'partially', 'slightly', 'moderately',

    # Indirect speech
    'i think', 'i believe', 'i guess', 'i suppose', 'it seems',
    'it appears', 'it looks like', 'in my opinion'
}

# Concrete detail patterns
DATE_PATTERN = re.compile(r'\b\d{4}\b|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b')  # Years or dates
NUMBER_PATTERN = re.compile(r'\b\d+(?:,\d{3})*(?:\.\d+)?(?!%)\b')  # Numbers (excluding percentages)
PERCENTAGE_PATTERN = re.compile(r'\b\d+(?:\.\d+)?\s*%')  # Percentages (with optional space before %)
MEASUREMENT_PATTERN = re.compile(r'\b\d+(?:\.\d+)?\s*(?:km|m|cm|mm|kg|g|lb|ft|in|miles?|meters?|pounds?|feet)\b', re.IGNORECASE)

# Source citation patterns
SOURCE_PATTERNS = [
    re.compile(r'\b(?:according to|as reported by|cited in|published in|from)\b', re.IGNORECASE),
    re.compile(r'\b(?:study|research|paper|article|book|journal|report)\b', re.IGNORECASE),
    re.compile(r'\b(?:university|institute|laboratory|museum|archive)\b', re.IGNORECASE),
    re.compile(r'\b(?:professor|dr\.?|scientist|researcher|historian)\b', re.IGNORECASE),
]

# Question type patterns
QUESTION_TYPES = {
    'yes_no': re.compile(r'^(?:is|are|was|were|do|does|did|can|could|will|would|has|have|had)\b', re.IGNORECASE),
    'what': re.compile(r'^\s*what\b', re.IGNORECASE),
    'why': re.compile(r'^\s*(?:why|how come)\b', re.IGNORECASE),
    'how': re.compile(r'^\s*how\b', re.IGNORECASE),
    'when': re.compile(r'^\s*when\b', re.IGNORECASE),
    'where': re.compile(r'^\s*where\b', re.IGNORECASE),
    'who': re.compile(r'^\s*who\b', re.IGNORECASE),
}

# Verification request patterns (asking for sources/evidence)
VERIFICATION_PATTERNS = [
    re.compile(r'\b(?:source|citation|reference|evidence|proof|prove)\b', re.IGNORECASE),
    re.compile(r'\bwhere did you (?:hear|read|learn|find)\b', re.IGNORECASE),
    re.compile(r'\bhow do you know\b', re.IGNORECASE),
    re.compile(r'\bcan you (?:cite|provide|show|prove)\b', re.IGNORECASE),
]


@dataclass
class SpecificityScore:
    """Detailed breakdown of specificity indicators.

    Attributes:
        score: Overall specificity score (1-10)
        num_dates: Count of dates/years mentioned
        num_numbers: Count of numbers mentioned
        num_percentages: Count of percentages
        num_measurements: Count of measurements with units
        num_proper_nouns: Count of capitalized names/places
        concrete_detail_density: Details per 100 words
    """
    score: int
    num_dates: int
    num_numbers: int
    num_percentages: int
    num_measurements: int
    num_proper_nouns: int
    concrete_detail_density: float


@dataclass
class HedgingAnalysis:
    """Analysis of hedging language.

    Attributes:
        hedging_score: Overall hedging score (1-10, higher = more hedging)
        hedge_count: Total number of hedging words/phrases
        hedge_density: Hedges per 100 words
        hedge_types: Breakdown by hedge type
        hedging_words_found: List of specific hedging words used
    """
    hedging_score: int
    hedge_count: int
    hedge_density: float
    hedge_types: Dict[str, int]
    hedging_words_found: List[str]


@dataclass
class SourceCitationAnalysis:
    """Analysis of source citation patterns.

    Attributes:
        has_source: Whether any source is cited
        source_count: Number of source mentions
        source_types: Types of sources mentioned (study, book, person, etc.)
        explicit_citations: Whether explicit citations are present
    """
    has_source: bool
    source_count: int
    source_types: List[str]
    explicit_citations: bool


@dataclass
class QuestionTypeAnalysis:
    """Classification of question types.

    Attributes:
        question_type: Primary type (yes_no, what, why, how, when, where, who, other)
        is_verification_request: Whether question asks for sources/evidence
        is_adversarial: Whether question seems adversarial/challenging
    """
    question_type: Literal['yes_no', 'what', 'why', 'how', 'when', 'where', 'who', 'other']
    is_verification_request: bool
    is_adversarial: bool


@dataclass
class StoryAnalysis:
    """Complete linguistic analysis of a story.

    Attributes:
        story_id: Storyteller ID
        word_count: Number of words
        specificity: Specificity analysis
        hedging: Hedging analysis
        source_citation: Source citation analysis
    """
    story_id: str
    word_count: int
    specificity: SpecificityScore
    hedging: HedgingAnalysis
    source_citation: SourceCitationAnalysis


@dataclass
class AnswerAnalysis:
    """Complete linguistic analysis of an answer.

    Attributes:
        storyteller_id: Storyteller ID
        question_number: Which question this answers
        word_count: Number of words
        specificity: Specificity analysis
        hedging: Hedging analysis
    """
    storyteller_id: str
    question_number: int
    word_count: int
    specificity: SpecificityScore
    hedging: HedgingAnalysis


class LinguisticAnalyzer:
    """Analyzer for linguistic features in stories and answers."""

    def analyze_story(self, story: Story) -> StoryAnalysis:
        """Analyze a complete story.

        Args:
            story: Story to analyze

        Returns:
            Complete linguistic analysis
        """
        return StoryAnalysis(
            story_id=story.storyteller_id,
            word_count=story.word_count,
            specificity=self.calculate_specificity(story.content, story.word_count),
            hedging=self.calculate_hedging(story.content, story.word_count),
            source_citation=self.detect_source_citation(story.content)
        )

    def analyze_answer(self, answer: Answer) -> AnswerAnalysis:
        """Analyze an answer.

        Args:
            answer: Answer to analyze

        Returns:
            Complete linguistic analysis
        """
        return AnswerAnalysis(
            storyteller_id=answer.storyteller_id,
            question_number=answer.question_number,
            word_count=answer.word_count,
            specificity=self.calculate_specificity(answer.content, answer.word_count),
            hedging=self.calculate_hedging(answer.content, answer.word_count)
        )

    def classify_question(self, question: Question) -> QuestionTypeAnalysis:
        """Classify a question by type.

        Args:
            question: Question to classify

        Returns:
            Question type analysis
        """
        content = question.content.strip()

        # Determine primary question type
        question_type = 'other'
        for qtype, pattern in QUESTION_TYPES.items():
            if pattern.search(content):
                question_type = qtype
                break

        # Check if verification request
        is_verification = any(
            pattern.search(content)
            for pattern in VERIFICATION_PATTERNS
        )

        # Simple adversarial detection (questions with challenging words)
        adversarial_words = ['really', 'actually', 'sure', 'certain', 'prove', 'evidence']
        is_adversarial = any(word in content.lower() for word in adversarial_words)

        return QuestionTypeAnalysis(
            question_type=question_type,
            is_verification_request=is_verification,
            is_adversarial=is_adversarial
        )

    def calculate_specificity(self, text: str, word_count: int) -> SpecificityScore:
        """Calculate specificity score based on concrete details.

        Args:
            text: Text to analyze
            word_count: Number of words in text

        Returns:
            Specificity score breakdown
        """
        # Count concrete details
        num_dates = len(DATE_PATTERN.findall(text))
        num_numbers = len(NUMBER_PATTERN.findall(text))
        num_percentages = len(PERCENTAGE_PATTERN.findall(text))
        num_measurements = len(MEASUREMENT_PATTERN.findall(text))

        # Count proper nouns (capitalized words that aren't sentence-initial)
        words = text.split()
        num_proper_nouns = 0
        for i, word in enumerate(words):
            # Skip first word of sentences
            if i > 0 and word and word[0].isupper() and word.isalpha():
                # Not after sentence-ending punctuation
                prev_word = words[i-1]
                if not prev_word.endswith(('.', '!', '?')):
                    num_proper_nouns += 1

        # Calculate total concrete details
        total_details = (
            num_dates +
            num_numbers +
            num_percentages +
            num_measurements +
            num_proper_nouns
        )

        # Calculate density (details per 100 words)
        concrete_detail_density = (total_details / max(word_count, 1)) * 100

        # Score from 1-10 based on density
        # 0-1 details per 100 words = 1-2
        # 1-2 details per 100 words = 3-4
        # 2-4 details per 100 words = 5-6
        # 4-6 details per 100 words = 7-8
        # 6+ details per 100 words = 9-10
        if concrete_detail_density < 1:
            score = max(1, min(2, int(concrete_detail_density * 2) + 1))
        elif concrete_detail_density < 2:
            score = 3 + int((concrete_detail_density - 1) * 2)
        elif concrete_detail_density < 4:
            score = 5 + int((concrete_detail_density - 2) / 2)
        elif concrete_detail_density < 6:
            score = 7 + int((concrete_detail_density - 4) / 2)
        else:
            score = min(10, 9 + int((concrete_detail_density - 6) / 3))

        return SpecificityScore(
            score=score,
            num_dates=num_dates,
            num_numbers=num_numbers,
            num_percentages=num_percentages,
            num_measurements=num_measurements,
            num_proper_nouns=num_proper_nouns,
            concrete_detail_density=round(concrete_detail_density, 2)
        )

    def calculate_hedging(self, text: str, word_count: int) -> HedgingAnalysis:
        """Calculate hedging score based on hedging language.

        Args:
            text: Text to analyze
            word_count: Number of words in text

        Returns:
            Hedging analysis breakdown
        """
        text_lower = text.lower()

        # Find all hedging words/phrases
        hedging_words_found = []
        for hedge in HEDGING_WORDS:
            if hedge in text_lower:
                # Count occurrences
                count = text_lower.count(hedge)
                hedging_words_found.extend([hedge] * count)

        hedge_count = len(hedging_words_found)

        # Calculate density (hedges per 100 words)
        hedge_density = (hedge_count / max(word_count, 1)) * 100

        # Categorize hedge types
        hedge_types = {
            'epistemic': 0,  # uncertainty
            'approximator': 0,  # about, roughly
            'modal': 0,  # might, could
            'qualifier': 0,  # somewhat, rather
            'indirect': 0  # i think, it seems
        }

        epistemic = {'maybe', 'perhaps', 'possibly', 'probably', 'apparently', 'seemingly',
                     'supposedly', 'allegedly', 'presumably', 'conceivably'}
        approximators = {'about', 'around', 'roughly', 'approximately', 'nearly', 'almost',
                        'sort of', 'kind of', 'more or less', 'essentially', 'basically'}
        modals = {'might', 'could', 'would', 'should', 'may', 'can'}
        qualifiers = {'somewhat', 'rather', 'quite', 'fairly', 'relatively',
                     'partially', 'slightly', 'moderately'}
        indirect = {'i think', 'i believe', 'i guess', 'i suppose', 'it seems',
                   'it appears', 'it looks like', 'in my opinion'}

        for hedge in hedging_words_found:
            if hedge in epistemic:
                hedge_types['epistemic'] += 1
            elif hedge in approximators:
                hedge_types['approximator'] += 1
            elif hedge in modals:
                hedge_types['modal'] += 1
            elif hedge in qualifiers:
                hedge_types['qualifier'] += 1
            elif hedge in indirect:
                hedge_types['indirect'] += 1

        # Score from 1-10 based on density
        # 0-1 hedges per 100 words = 1-2
        # 1-2 hedges per 100 words = 3-4
        # 2-4 hedges per 100 words = 5-6
        # 4-6 hedges per 100 words = 7-8
        # 6+ hedges per 100 words = 9-10
        if hedge_density < 1:
            score = max(1, min(2, int(hedge_density * 2) + 1))
        elif hedge_density < 2:
            score = 3 + int((hedge_density - 1) * 2)
        elif hedge_density < 4:
            score = 5 + int((hedge_density - 2) / 2)
        elif hedge_density < 6:
            score = 7 + int((hedge_density - 4) / 2)
        else:
            score = min(10, 9 + int((hedge_density - 6) / 3))

        return HedgingAnalysis(
            hedging_score=score,
            hedge_count=hedge_count,
            hedge_density=round(hedge_density, 2),
            hedge_types=hedge_types,
            hedging_words_found=list(set(hedging_words_found))  # Unique words
        )

    def detect_source_citation(self, text: str) -> SourceCitationAnalysis:
        """Detect source citations in text.

        Args:
            text: Text to analyze

        Returns:
            Source citation analysis
        """
        source_types = []
        source_count = 0

        # Check for source patterns
        for i, pattern in enumerate(SOURCE_PATTERNS):
            matches = pattern.findall(text)
            if matches:
                source_count += len(matches)
                # Add category based on pattern index
                if i == 0:  # according to/reported by/etc
                    source_types.append('attribution')
                elif i == 1:  # study/research/paper
                    source_types.append('research')
                elif i == 2:  # university/institute
                    source_types.append('institution')
                elif i == 3:  # professor/dr./scientist
                    source_types.append('person')

        has_source = source_count > 0
        explicit_citations = 'according to' in text.lower() or 'cited in' in text.lower()

        return SourceCitationAnalysis(
            has_source=has_source,
            source_count=source_count,
            source_types=list(set(source_types)),
            explicit_citations=explicit_citations
        )

    def analyze_round_linguistics(
        self,
        stories: List[Story],
        answers: List[Answer],
        questions: List[Question]
    ) -> Dict:
        """Analyze all linguistic features for a complete round.

        Args:
            stories: All stories from the round
            answers: All answers from the round
            questions: All questions from the round

        Returns:
            Dictionary with complete linguistic analysis
        """
        return {
            'stories': [self.analyze_story(story) for story in stories],
            'answers': [self.analyze_answer(answer) for answer in answers],
            'questions': [self.classify_question(q) for q in questions]
        }
