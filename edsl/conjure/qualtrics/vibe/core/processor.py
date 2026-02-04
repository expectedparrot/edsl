"""
Main vibe processor - clean orchestrator for the vibe system.
"""

from typing import Optional, Dict, List
from edsl import Survey
from ..config import VibeConfig
from ..analysis import QuestionAnalyzer
from ..logging import create_logger
from .change_tracker import ChangeTracker
from .batch_processor import BatchProcessor
from .question_improver import QuestionImprover


class VibeProcessor:
    """
    Clean, focused vibe processor that orchestrates question improvement.

    This is a much slimmer version of the original processor that delegates
    responsibilities to specialized components.
    """

    def __init__(self, config: Optional[VibeConfig] = None):
        """Initialize the vibe processor with dependency injection."""
        self.config = config or VibeConfig()

        # Initialize components
        self._setup_components()

    def _setup_components(self) -> None:
        """Set up all processor components."""
        # Create logger
        self.logger = create_logger(
            enable_logging=self.config.enable_logging,
            verbose=self.config.verbose_logging,
        )

        # Create core components
        self.change_tracker = ChangeTracker()
        self.analyzer = QuestionAnalyzer(self.config)
        self.batch_processor = BatchProcessor(
            max_concurrent=self.config.max_concurrent,
            timeout_seconds=self.config.timeout_seconds,
            logger=self.logger,
        )
        self.question_improver = QuestionImprover(
            config=self.config,
            analyzer=self.analyzer,
            change_tracker=self.change_tracker,
            logger=self.logger,
        )

    async def process_survey(
        self, survey: Survey, response_data: Optional[Dict[str, List[str]]] = None
    ) -> Survey:
        """
        Process all questions in a survey using vibe analysis.

        Args:
            survey: Survey to process
            response_data: Optional response data for extracting options

        Returns:
            Enhanced survey with improved questions
        """
        if not self.config.enabled:
            return survey

        if not survey.questions:
            return survey

        # Store response data for use by question improver
        if response_data:
            self.question_improver.set_response_data(response_data)

        # Process questions in batches
        improved_questions = await self.batch_processor.process_questions_in_batches(
            questions=survey.questions,
            process_function=self.question_improver.improve_question,
        )

        # Create new survey with improved questions
        return Survey(questions=improved_questions)

    def process_survey_sync(
        self, survey: Survey, response_data: Optional[Dict[str, List[str]]] = None
    ) -> Survey:
        """
        Synchronous wrapper for survey processing.

        Args:
            survey: Survey to process
            response_data: Optional response data for extracting options

        Returns:
            Processed survey
        """
        import asyncio

        return asyncio.run(self.process_survey(survey, response_data))

    # Convenience methods for accessing results
    def get_change_log(self) -> list[dict]:
        """Get a list of all changes made during processing."""
        return self.change_tracker.get_change_log()

    def get_change_summary(self) -> dict:
        """Get a summary of changes made during processing."""
        return self.change_tracker.get_change_summary()

    def clear_changes(self) -> None:
        """Clear all recorded changes."""
        self.change_tracker.clear()
