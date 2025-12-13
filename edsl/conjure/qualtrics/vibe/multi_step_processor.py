"""
Multi-step vibe processor that runs specialized processors in sequence.
"""

import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from edsl.questions import Question
from edsl import Survey

from .processors.base_processor import BaseProcessor, ProcessingResult
from .processors.type_corrector import TypeCorrectionProcessor
from .processors.option_organizer import OptionOrganizationProcessor
from .processors.text_cleaner import TextCleanupProcessor


@dataclass
class MultiStepResult:
    """Result of multi-step processing."""
    question: Question
    total_changes: int
    step_results: List[ProcessingResult]
    processing_time: float


class MultiStepProcessor:
    """
    Coordinates multiple processing steps in sequence.

    This replaces the single large AI prompt with focused, specialized processors
    that handle specific aspects of question improvement.
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

        # Initialize processors in order
        self.processors: List[BaseProcessor] = [
            TypeCorrectionProcessor(verbose=verbose),
            OptionOrganizationProcessor(verbose=verbose),
            TextCleanupProcessor(verbose=verbose),
        ]

    async def process_question(self, question: Question, context: Optional[Dict[str, Any]] = None) -> MultiStepResult:
        """
        Process a question through all steps.

        Args:
            question: Question to process
            context: Optional context data (response data, etc.)

        Returns:
            MultiStepResult with final question and processing details
        """
        import time
        start_time = time.time()

        current_question = question
        step_results = []
        total_changes = 0

        if self.verbose:
            print(f"🔧 Processing {question.question_name} through {len(self.processors)} steps...")

        # Run each processor in sequence
        for i, processor in enumerate(self.processors, 1):
            if self.verbose:
                print(f"  Step {i}/{len(self.processors)}: {processor.__class__.__name__}")

            try:
                result = await processor.process(current_question, context)
                step_results.append(result)

                if result.changed:
                    current_question = result.question
                    total_changes += len(result.changes)

                    if self.verbose:
                        print(f"    ✨ Changes made: {len(result.changes)}")
                        for change in result.changes:
                            print(f"      - {change.get('type', 'unknown')}")
                else:
                    if self.verbose:
                        print(f"    ✅ No changes needed")

            except Exception as e:
                if self.verbose:
                    print(f"    ❌ Error in {processor.__class__.__name__}: {e}")

                # Create error result and continue with original question
                error_result = ProcessingResult(
                    question=current_question,
                    changed=False,
                    changes=[],
                    confidence=0.0,
                    reasoning=f"Error: {str(e)}"
                )
                step_results.append(error_result)

        processing_time = time.time() - start_time

        if self.verbose and total_changes > 0:
            print(f"  🎯 Total improvements: {total_changes} changes in {processing_time:.2f}s")

        return MultiStepResult(
            question=current_question,
            total_changes=total_changes,
            step_results=step_results,
            processing_time=processing_time
        )

    async def process_survey(self, survey: Survey, response_data: Optional[Dict[str, List[str]]] = None) -> Survey:
        """
        Process all questions in a survey.

        Args:
            survey: Survey to process
            response_data: Optional response data for context

        Returns:
            Improved survey
        """
        if not survey.questions:
            return survey

        if self.verbose:
            print(f"🔍 Processing {len(survey.questions)} questions with multi-step approach...")

        improved_questions = []
        total_changes = 0

        for question in survey.questions:
            result = await self.process_question(question, response_data)
            improved_questions.append(result.question)
            total_changes += result.total_changes

        if self.verbose:
            print(f"✨ Survey processing complete: {total_changes} total improvements")

        # Create new survey with improved questions
        improved_survey = Survey(questions=improved_questions)

        # Copy any other survey attributes
        for attr in ['name', 'description', 'metadata']:
            if hasattr(survey, attr):
                setattr(improved_survey, attr, getattr(survey, attr))

        return improved_survey

    def get_processor_info(self) -> List[Dict[str, str]]:
        """Get information about available processors."""
        return [
            {
                'name': processor.__class__.__name__,
                'description': processor.__class__.__doc__ or 'No description available'
            }
            for processor in self.processors
        ]