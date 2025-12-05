"""Semantic Option Orderer for Survey Monkey imports.

This module uses LLM calls to analyze multiple choice question options and
reorder them in semantically correct order (e.g., company size from smallest
to largest, experience levels from beginner to expert, age ranges in order).
"""

import json
import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

# Import the OpenAI utils from the vibes system
from ...base.openai_utils import create_openai_client

logger = logging.getLogger(__name__)


# Pydantic schemas for structured LLM output
class OptionOrderingDetail(BaseModel):
    """Details of how options were reordered."""

    original_order: List[str] = Field(
        description="The original order of options as received"
    )
    semantic_order: List[str] = Field(
        description="The semantically correct order of options"
    )
    ordering_type: str = Field(
        description="Type of ordering applied (e.g., 'size_ascending', 'experience_level', 'chronological', 'no_change')"
    )
    confidence: float = Field(
        description="Confidence in this ordering decision (0.0 to 1.0)", ge=0.0, le=1.0
    )
    explanation: str = Field(description="Explanation of why this ordering was chosen")
    reordering_applied: bool = Field(
        description="True if the order was actually changed"
    )


class QuestionOptionsOrdering(BaseModel):
    """Semantic ordering results for a single question's options."""

    question_text: str = Field(description="The text of the question being analyzed")
    question_identifier: str = Field(
        description="Identifier for the question (question name or column)"
    )
    ordering_details: OptionOrderingDetail = Field(
        description="Details of the semantic ordering analysis and results"
    )
    question_category: str = Field(
        description="Inferred category of question (e.g., 'demographic', 'rating', 'frequency', 'size', 'other')"
    )


class SurveyOptionsOrderingResult(BaseModel):
    """Complete semantic ordering results for all multiple choice questions."""

    questions: List[QuestionOptionsOrdering] = Field(
        description="Ordering results for each multiple choice question"
    )
    total_reorderings: int = Field(
        description="Total number of questions that had their options reordered"
    )
    high_confidence_reorderings: int = Field(
        description="Number of reorderings with confidence >= 0.8"
    )
    summary: str = Field(
        description="Brief summary of the semantic ordering that was performed"
    )


@dataclass
class OptionSemanticOrderer:
    """LLM-based semantic option orderer.

    Uses OpenAI LLMs to analyze multiple choice questions and reorder their
    options in semantically correct order (e.g., sizes from small to large,
    experience levels from beginner to expert, etc.).
    """

    model: str = "gpt-4o"
    temperature: float = 0.2  # Low temperature for consistent ordering decisions
    verbose: bool = False

    def __post_init__(self):
        """Initialize the OpenAI client."""
        try:
            self.client = create_openai_client()
        except Exception as e:
            logger.error(f"Failed to create OpenAI client: {e}")
            raise

    def order_question_options(
        self, question_text: str, question_identifier: str, options: List[str]
    ) -> QuestionOptionsOrdering:
        """Order options for a single multiple choice question semantically.

        Parameters
        ----------
        question_text : str
            The text of the survey question
        question_identifier : str
            Identifier for the question (used for logging/tracking)
        options : List[str]
            List of answer options that may need semantic ordering

        Returns
        -------
        QuestionOptionsOrdering
            Structured results with original/reordered options and reasoning
        """
        if not options or len(options) < 2:
            # Return no-change result for questions with 0-1 options
            return QuestionOptionsOrdering(
                question_text=question_text,
                question_identifier=question_identifier,
                ordering_details=OptionOrderingDetail(
                    original_order=options,
                    semantic_order=options,
                    ordering_type="no_change",
                    confidence=1.0,
                    explanation="Question has fewer than 2 options, no ordering needed",
                    reordering_applied=False,
                ),
                question_category="other",
            )

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            question_text, question_identifier, options
        )

        try:
            if self.verbose:
                logger.info(
                    f"Calling LLM to order options for question: {question_identifier}"
                )
                logger.debug(f"Question: {question_text}")
                logger.debug(f"Original options: {options}")

            resp = self.client.responses.parse(
                model=self.model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_prompt, indent=2)},
                ],
                text_format=QuestionOptionsOrdering,
                temperature=self.temperature,
            )

            result = resp.output_parsed

            if self.verbose and result.ordering_details.reordering_applied:
                logger.info(f"Reordered options for question: {question_identifier}")
                logger.debug(f"  Before: {result.ordering_details.original_order}")
                logger.debug(f"  After:  {result.ordering_details.semantic_order}")
                logger.debug(f"  Type: {result.ordering_details.ordering_type}")
                logger.debug(f"  Confidence: {result.ordering_details.confidence:.2f}")

            return result

        except Exception as e:
            logger.error(f"LLM call failed for question {question_identifier}: {e}")
            # Fallback: return original options unchanged
            return QuestionOptionsOrdering(
                question_text=question_text,
                question_identifier=question_identifier,
                ordering_details=OptionOrderingDetail(
                    original_order=options,
                    semantic_order=options,
                    ordering_type="error",
                    confidence=0.0,
                    explanation=f"LLM call failed: {e}",
                    reordering_applied=False,
                ),
                question_category="other",
            )

    def order_multiple_questions(
        self, questions_data: List[Dict[str, Any]]
    ) -> SurveyOptionsOrderingResult:
        """Order options semantically across multiple questions.

        Parameters
        ----------
        questions_data : List[Dict[str, Any]]
            List of question dicts with keys: 'question_text', 'question_identifier', 'options'

        Returns
        -------
        SurveyOptionsOrderingResult
            Complete ordering results for all questions
        """
        all_orderings = []
        total_reorderings = 0
        high_confidence_reorderings = 0

        for question_data in questions_data:
            question_ordering = self.order_question_options(
                question_data["question_text"],
                question_data["question_identifier"],
                question_data["options"],
            )
            all_orderings.append(question_ordering)

            if question_ordering.ordering_details.reordering_applied:
                total_reorderings += 1
                if question_ordering.ordering_details.confidence >= 0.8:
                    high_confidence_reorderings += 1

        # Generate summary
        if total_reorderings == 0:
            summary = (
                "No semantic reordering was needed for any multiple choice questions."
            )
        else:
            summary = (
                f"Reordered options for {total_reorderings} multiple choice questions. "
                f"{high_confidence_reorderings} reorderings had high confidence (≥0.8). "
                f"Common orderings: sizes, experience levels, frequencies, and age ranges."
            )

        return SurveyOptionsOrderingResult(
            questions=all_orderings,
            total_reorderings=total_reorderings,
            high_confidence_reorderings=high_confidence_reorderings,
            summary=summary,
        )

    def _build_system_prompt(self) -> str:
        """Build the system prompt for the LLM ordering task."""
        return """You are an expert at analyzing survey questions and ordering multiple choice options in semantically correct order.

COMMON SEMANTIC ORDERING PATTERNS:
- Company/Organization Size: Small → Medium → Large (or specific ranges in ascending order)
- Experience Levels: Beginner → Intermediate → Advanced → Expert
- Age Ranges: Youngest first, in ascending chronological order (18-25, 26-35, etc.)
- Education Levels: High School → Bachelor's → Master's → PhD
- Frequency: Never → Rarely → Sometimes → Often → Always
- Income Ranges: Lowest to highest dollar amounts
- Time Periods: Past to present, or logical chronological order
- Ratings/Satisfaction: Lowest to highest (Poor → Fair → Good → Excellent)
- Quantities/Amounts: Smallest to largest numerical values

YOUR TASK:
1. Analyze the question text to understand what type of ordering would be most logical
2. Determine if the current option order makes semantic sense
3. If not, reorder the options in the most logical sequence
4. Provide clear reasoning for your ordering decision
5. Assign confidence based on how clear-cut the correct ordering is

ORDERING GUIDELINES:
- Preserve the exact text of each option (don't modify, just reorder)
- Use ascending order by default (smallest to largest, earliest to latest)
- For experience/skill levels: beginner → expert progression
- For satisfaction/rating scales: negative to positive
- For frequencies: least frequent to most frequent
- Consider the survey context and question intent
- If multiple valid orderings exist, choose the most conventional one
- Leave options unchanged if no clear semantic ordering applies

CONFIDENCE SCORING:
- 1.0: Crystal clear ordering (age ranges, company sizes with clear progression)
- 0.8: Very clear ordering (experience levels, education, satisfaction ratings)
- 0.6: Moderately clear ordering (some ambiguity but one order clearly better)
- 0.4: Unclear ordering (multiple reasonable orders possible)
- 0.2: Very unclear (ordering might not improve readability)
- 0.0: No semantic ordering possible (random/categorical options)"""

    def _build_user_prompt(
        self, question_text: str, question_identifier: str, options: List[str]
    ) -> Dict[str, Any]:
        """Build the user prompt with specific question data."""
        return {
            "task": "Analyze and semantically order multiple choice question options",
            "question_text": question_text,
            "question_identifier": question_identifier,
            "current_options": options,
            "instructions": [
                "Analyze the question text to understand the intent and context",
                "Determine what type of semantic ordering would be most logical",
                "Check if the current order already follows good semantic ordering",
                "If not, reorder options in the most logical sequence",
                "Provide clear reasoning for your ordering decision",
                "Be conservative: only reorder when there's a clear improvement",
            ],
            "examples": {
                "company_size": {
                    "question": "What is the size of your company?",
                    "original": ["Large (500+)", "Medium (50-499)", "Small (1-49)"],
                    "reordered": ["Small (1-49)", "Medium (50-499)", "Large (500+)"],
                    "reason": "Company sizes should be ordered from smallest to largest",
                },
                "experience": {
                    "question": "What is your experience level with this software?",
                    "original": ["Expert", "Beginner", "Advanced", "Intermediate"],
                    "reordered": ["Beginner", "Intermediate", "Advanced", "Expert"],
                    "reason": "Experience levels follow natural progression from novice to expert",
                },
                "frequency": {
                    "question": "How often do you use this feature?",
                    "original": ["Sometimes", "Never", "Always", "Rarely"],
                    "reordered": ["Never", "Rarely", "Sometimes", "Always"],
                    "reason": "Frequency options ordered from least to most frequent",
                },
                "no_change_needed": {
                    "question": "Which department do you work in?",
                    "original": ["Marketing", "Sales", "Engineering", "HR"],
                    "reordered": ["Marketing", "Sales", "Engineering", "HR"],
                    "reason": "Department names are categorical with no natural ordering",
                },
            },
        }
