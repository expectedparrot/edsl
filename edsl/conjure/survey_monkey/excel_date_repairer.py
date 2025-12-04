"""Excel Date Format Repairer for Survey Monkey imports.

This module uses LLM calls to detect and repair Excel-mangled date formatting
in survey answer options. Excel commonly converts numeric ranges like "1-2",
"3-5", "6-10" into date formats like "2-Jan", "5-Mar", "10-Jun".
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
class OptionRepairDetail(BaseModel):
    """Details of a single option repair."""
    original: str = Field(description="The original Excel-mangled option text")
    repaired: str = Field(description="The corrected option text")
    confidence: float = Field(
        description="Confidence in this repair (0.0 to 1.0)",
        ge=0.0,
        le=1.0
    )
    repair_type: str = Field(
        description="Type of repair applied (e.g., 'date_to_range', 'no_change', 'uncertain')"
    )
    explanation: str = Field(
        description="Brief explanation of why this repair was made"
    )


class QuestionOptionsRepair(BaseModel):
    """Repair results for a single question's options."""
    question_identifier: str = Field(
        description="Identifier for the question (question text or column header)"
    )
    original_options: List[str] = Field(
        description="Original list of answer options as received"
    )
    repaired_options: List[str] = Field(
        description="List of repaired answer options"
    )
    repairs_made: List[OptionRepairDetail] = Field(
        description="Details of each repair that was performed"
    )
    any_repairs_applied: bool = Field(
        description="True if any repairs were applied to this question's options"
    )


class SurveyOptionsRepairResult(BaseModel):
    """Complete repair results for all questions in a survey."""
    questions: List[QuestionOptionsRepair] = Field(
        description="Repair results for each question"
    )
    total_repairs_count: int = Field(
        description="Total number of option repairs made across all questions"
    )
    high_confidence_repairs: int = Field(
        description="Number of repairs with confidence >= 0.8"
    )
    summary: str = Field(
        description="Brief summary of the repairs that were performed"
    )


@dataclass
class ExcelDateRepairer:
    """LLM-based Excel date format repairer.

    Uses OpenAI LLMs to detect and repair Excel-mangled date formatting
    in survey answer options. Designed to integrate with SurveyMonkey
    import pipeline.
    """

    model: str = "gpt-4o"
    temperature: float = 0.2  # Low temperature for deterministic repairs
    verbose: bool = False

    def __post_init__(self):
        """Initialize the OpenAI client."""
        try:
            self.client = create_openai_client()
        except Exception as e:
            logger.error(f"Failed to create OpenAI client: {e}")
            raise

    def repair_question_options(
        self,
        question_identifier: str,
        options: List[str]
    ) -> QuestionOptionsRepair:
        """Repair Excel-mangled dates in a single question's answer options.

        Parameters
        ----------
        question_identifier : str
            Identifier for the question (used for logging/tracking)
        options : List[str]
            List of answer options that may contain Excel-mangled dates

        Returns
        -------
        QuestionOptionsRepair
            Structured repair results with original/repaired options and details
        """
        if not options or all(not opt.strip() for opt in options):
            # Return empty result for questions with no valid options
            return QuestionOptionsRepair(
                question_identifier=question_identifier,
                original_options=options,
                repaired_options=options,
                repairs_made=[],
                any_repairs_applied=False
            )

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(question_identifier, options)

        try:
            if self.verbose:
                logger.info(f"Calling LLM to repair options for question: {question_identifier}")
                logger.debug(f"Original options: {options}")

            resp = self.client.responses.parse(
                model=self.model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_prompt, indent=2)},
                ],
                text_format=QuestionOptionsRepair,
                temperature=self.temperature,
            )

            result = resp.output_parsed

            if self.verbose and result.any_repairs_applied:
                logger.info(f"Applied {len(result.repairs_made)} repairs to question: {question_identifier}")
                for repair in result.repairs_made:
                    logger.debug(f"  {repair.original} → {repair.repaired} (confidence: {repair.confidence:.2f})")

            return result

        except Exception as e:
            logger.error(f"LLM call failed for question {question_identifier}: {e}")
            # Fallback: return original options unchanged
            return QuestionOptionsRepair(
                question_identifier=question_identifier,
                original_options=options,
                repaired_options=options,
                repairs_made=[],
                any_repairs_applied=False
            )

    def repair_multiple_questions(
        self,
        questions_data: Dict[str, List[str]]
    ) -> SurveyOptionsRepairResult:
        """Repair Excel-mangled dates across multiple questions.

        Parameters
        ----------
        questions_data : Dict[str, List[str]]
            Dictionary mapping question identifiers to their answer options

        Returns
        -------
        SurveyOptionsRepairResult
            Complete repair results for all questions
        """
        all_repairs = []
        total_repairs = 0
        high_confidence_repairs = 0

        for question_id, options in questions_data.items():
            question_repair = self.repair_question_options(question_id, options)
            all_repairs.append(question_repair)

            if question_repair.any_repairs_applied:
                total_repairs += len(question_repair.repairs_made)
                high_confidence_repairs += len([
                    r for r in question_repair.repairs_made
                    if r.confidence >= 0.8
                ])

        # Generate summary
        if total_repairs == 0:
            summary = "No Excel date formatting issues detected in survey options."
        else:
            summary = (
                f"Repaired {total_repairs} Excel-mangled date formats across "
                f"{len([r for r in all_repairs if r.any_repairs_applied])} questions. "
                f"{high_confidence_repairs} repairs had high confidence (≥0.8)."
            )

        return SurveyOptionsRepairResult(
            questions=all_repairs,
            total_repairs_count=total_repairs,
            high_confidence_repairs=high_confidence_repairs,
            summary=summary
        )

    def _build_system_prompt(self) -> str:
        """Build the system prompt for the LLM repair task."""
        return """You are an expert at detecting and repairing Excel-mangled date formatting in survey answer options.

COMMON EXCEL DATE MANGLING PATTERNS:
When users open CSV files in Excel, Excel auto-converts certain text patterns into dates:
- "1-2" becomes "2-Jan" or "Jan-2"
- "3-5" becomes "5-Mar" or "Mar-5"
- "6-10" becomes "10-Jun" or "Jun-10"
- "11-15" becomes "15-Nov" or "Nov-15"
- "1-Jan" stays "1-Jan" (already a date)
- "Dec-25" stays "Dec-25" (already a date)

YOUR TASK:
1. Examine each answer option to determine if it appears to be an Excel-mangled date
2. If it's mangled, repair it to the original intended format (likely a numeric range)
3. If it's a legitimate date or other text, leave it unchanged
4. Provide confidence scores and explanations for your decisions

REPAIR GUIDELINES:
- "5-Mar" likely meant "3-5" (March=3rd month, day 5 → range 3-5)
- "10-Jun" likely meant "6-10" (June=6th month, day 10 → range 6-10)
- "15-Jan" likely meant "1-15" (January=1st month, day 15 → range 1-15)
- Look for context clues in other options to confirm patterns
- Be conservative: only repair if confident it's Excel mangling
- Consider the survey context (age ranges, quantity ranges, etc.)

CONFIDENCE SCORING:
- 1.0: Extremely confident this is Excel mangling (clear pattern with other options)
- 0.8: Very confident (fits common patterns, context supports it)
- 0.6: Moderately confident (likely mangling but some uncertainty)
- 0.4: Low confidence (could be mangling or legitimate date)
- 0.2: Very low confidence (probably leave unchanged)
- 0.0: No confidence (definitely leave unchanged)"""

    def _build_user_prompt(self, question_identifier: str, options: List[str]) -> Dict[str, Any]:
        """Build the user prompt with specific question data."""
        return {
            "task": "Detect and repair Excel-mangled date formatting in survey answer options",
            "question_identifier": question_identifier,
            "answer_options": options,
            "instructions": [
                "Analyze each option for potential Excel date mangling",
                "Look for patterns like 'DD-MMM' that should be numeric ranges",
                "Consider the context of all options together",
                "Only repair options where you're confident they were mangled by Excel",
                "Provide detailed explanations for your decisions"
            ],
            "examples": {
                "mangled_dates": [
                    {"original": "5-Mar", "should_be": "3-5", "reason": "March=3, day 5 suggests range 3-5"},
                    {"original": "10-Jun", "should_be": "6-10", "reason": "June=6, day 10 suggests range 6-10"}
                ],
                "legitimate_dates": [
                    {"original": "Jan-2025", "keep_as": "Jan-2025", "reason": "Legitimate date format"},
                    {"original": "Q1", "keep_as": "Q1", "reason": "Not a date, likely quarter reference"}
                ]
            }
        }