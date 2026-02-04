"""
Batch processing system for handling question processing in concurrent batches.
"""

import asyncio
from typing import List, Callable, Any, Awaitable, Optional
from edsl.questions import Question
from ..logging import VibeLogger


class BatchProcessor:
    """Handles batch processing of questions with concurrency control."""

    def __init__(
        self,
        max_concurrent: int = 5,
        timeout_seconds: int = 30,
        logger: Optional[VibeLogger] = None,
    ):
        self.max_concurrent = max_concurrent
        self.timeout_seconds = timeout_seconds
        self.logger = logger

    async def process_questions_in_batches(
        self,
        questions: List[Question],
        process_function: Callable[[Question], Awaitable[Question]],
    ) -> List[Question]:
        """
        Process questions in batches with concurrency control.

        Args:
            questions: List of questions to process
            process_function: Async function to process each question

        Returns:
            List of processed questions
        """
        if not questions:
            return []

        # Split questions into batches
        question_batches = self._create_batches(questions)
        processed_questions = []
        total_questions = len(questions)
        processed_count = 0

        if self.logger:
            self.logger.log_processing_start(total_questions, self.max_concurrent)

        for batch_idx, batch in enumerate(question_batches, 1):
            batch_start = processed_count + 1
            batch_end = min(processed_count + len(batch), total_questions)

            if self.logger:
                self.logger.log_batch_start(
                    batch_idx, batch_start, batch_end, len(question_batches)
                )

            # Process batch concurrently
            batch_results = await self._process_batch(batch, process_function)

            # Handle results and add to processed list
            for original_question, result in zip(batch, batch_results):
                processed_count += 1

                if isinstance(result, Exception):
                    # Log error and keep original question
                    if self.logger:
                        error_msg = str(result)[:50] + (
                            "..." if len(str(result)) > 50 else ""
                        )
                        print(
                            f"❌ {original_question.question_name}: Analysis failed - {error_msg}"
                        )
                    processed_questions.append(original_question)
                else:
                    processed_questions.append(result)

        if self.logger:
            self.logger.log_processing_complete(processed_count, total_questions)

        return processed_questions

    async def _process_batch(
        self,
        batch: List[Question],
        process_function: Callable[[Question], Awaitable[Question]],
    ) -> List[Any]:
        """
        Process a single batch of questions concurrently.

        Returns:
            List of results (questions or exceptions)
        """
        try:
            # Use asyncio.wait_for to enforce timeout
            tasks = [
                asyncio.wait_for(
                    process_function(question), timeout=self.timeout_seconds
                )
                for question in batch
            ]

            # Gather with return_exceptions=True to handle individual failures
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return results

        except asyncio.TimeoutError:
            # If the entire batch times out, return timeout exceptions for all questions
            return [asyncio.TimeoutError("Batch processing timeout") for _ in batch]

    def _create_batches(self, questions: List[Question]) -> List[List[Question]]:
        """Split questions into batches based on max_concurrent setting."""
        batch_size = self.max_concurrent
        return [
            questions[i : i + batch_size] for i in range(0, len(questions), batch_size)
        ]
