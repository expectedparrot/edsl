"""
Asynchronous interview runner module for conducting interviews concurrently.

This module provides functionality to run multiple interviews in parallel
with controlled concurrency, supporting both error handling and result collection.
"""

from collections.abc import AsyncGenerator
from typing import List, Generator, Tuple, TYPE_CHECKING
from dataclasses import dataclass
import asyncio
from edsl.data_transfer_models import EDSLResultObjectInput

from ..results import Result
from ..interviews import Interview

if TYPE_CHECKING:
    from ..jobs import Jobs

from .data_structures import RunConfig
from .concurrency_control import ConcurrencyManager

@dataclass
class InterviewResult:
    """Container for the result of an interview along with metadata.
    
    Attributes:
        result: The Result object containing the interview answers
        interview: The Interview object used to conduct the interview
        order: The original position of this interview in the processing queue
    """
    result: Result
    interview: Interview
    order: int


class AsyncInterviewRunner:
    """
    Runs interviews asynchronously with controlled concurrency.
    
    This class manages the parallel execution of multiple interviews while
    respecting concurrency limits and handling errors appropriately.
    
    Examples:
        >>> from unittest.mock import MagicMock, AsyncMock
        >>> mock_jobs = MagicMock()
        >>> mock_run_config = MagicMock()
        >>> mock_run_config.parameters.n = 1
        >>> mock_run_config.environment.cache = None
        >>> runner = AsyncInterviewRunner(mock_jobs, mock_run_config)
        >>> isinstance(runner._initialized, asyncio.Event)
        True
    """

    def __init__(self, jobs: "Jobs", run_config: RunConfig):
        """
        Initialize the AsyncInterviewRunner.
        
        Args:
            jobs: The Jobs object that generates interviews
            run_config: Configuration for running the interviews
        """
        self.jobs = jobs
        self.run_config = run_config
        self._initialized = asyncio.Event()
        # Get the concurrency limit adaptively
        self.max_concurrent = ConcurrencyManager.get_max_concurrent()

    def _expand_interviews(self) -> Generator["Interview", None, None]:
        """
        Create multiple copies of each interview based on the run configuration.
        
        This method expands interviews for repeated runs and ensures each has
        the proper cache configuration.
        
        Yields:
            Interview objects ready to be conducted
            
        Examples:
            >>> from unittest.mock import MagicMock
            >>> mock_jobs = MagicMock()
            >>> mock_interview = MagicMock()
            >>> mock_jobs.generate_interviews.return_value = [mock_interview]
            >>> mock_run_config = MagicMock()
            >>> mock_run_config.parameters.n = 2
            >>> mock_run_config.environment.cache = "mock_cache"
            >>> runner = AsyncInterviewRunner(mock_jobs, mock_run_config)
            >>> interviews = list(runner._expand_interviews())
            >>> len(interviews)
            2
        """
        for interview in self.jobs.generate_interviews():
            for iteration in range(self.run_config.parameters.n):
                if iteration > 0:
                    yield interview.duplicate(
                        iteration=iteration, cache=self.run_config.environment.cache
                    )
                else:
                    interview.cache = self.run_config.environment.cache
                    yield interview

    async def _conduct_interview(
        self, interview: "Interview"
    ) -> Tuple["Result", "Interview"]:
        """
        Asynchronously conduct a single interview.
        
        This method performs the interview and creates a Result object with
        the extracted answers and model responses.
        
        Args:
            interview: The interview to conduct
            
        Returns:
            Tuple containing the Result object and the Interview object
            
        Notes:
            'extracted_answers' contains the processed and validated answers
            from the interview, which may differ from the raw model output.
        """
        extracted_answers: dict[str, str]
        model_response_objects: List[EDSLResultObjectInput]

        extracted_answers, model_response_objects = (
            await interview.async_conduct_interview(self.run_config)
        )
        result = Result.from_interview(
            interview=interview,
            extracted_answers=extracted_answers,
            model_response_objects=model_response_objects,
        )
        return result, interview

    async def run(
        self,
    ) -> AsyncGenerator[tuple[Result, Interview], None]:
        """
        Run all interviews asynchronously and yield results as they complete.
        
        This method processes interviews in chunks using adaptive concurrency control,
        maintaining controlled parallelism while yielding results as soon as
        they become available.
        
        Yields:
            Tuples of (Result, Interview) as interviews complete
            
        Notes:
            - Uses structured concurrency patterns for proper resource management
            - Handles exceptions according to the run configuration
            - Ensures task cleanup even in case of failures
            - Adapts concurrency based on system resources
        """
        interviews = list(self._expand_interviews())
        self._initialized.set()

        async def _process_single_interview(
            interview: Interview, idx: int
        ) -> InterviewResult:
            try:
                result, interview = await self._conduct_interview(interview)
                self.run_config.environment.jobs_runner_status.add_completed_interview(
                    result
                )
                result.order = idx
                return InterviewResult(result, interview, idx)
            except Exception as e:
                if self.run_config.parameters.stop_on_exception:
                    raise
                return None

        # Check if we should reduce concurrency based on system load
        if ConcurrencyManager.should_reduce_concurrency():
            self.max_concurrent = max(2, self.max_concurrent // 2)

        # Process interviews in chunks with adaptive concurrency
        for i in range(0, len(interviews), self.max_concurrent):
            chunk = interviews[i : i + self.max_concurrent]
            tasks = [
                asyncio.create_task(_process_single_interview(interview, idx))
                for idx, interview in enumerate(chunk, start=i)
            ]

            try:
                # Wait for all tasks in the chunk to complete
                results = await asyncio.gather(
                    *tasks,
                    return_exceptions=not self.run_config.parameters.stop_on_exception
                )

                # Process successful results
                for result in (r for r in results if r is not None):
                    yield result.result, result.interview

            except Exception as e:
                if self.run_config.parameters.stop_on_exception:
                    raise
                continue

            finally:
                # Clean up any remaining tasks
                for task in tasks:
                    if not task.done():
                        task.cancel()
                        
                # Check if we should adjust concurrency for next chunk
                if i + self.max_concurrent < len(interviews):
                    if ConcurrencyManager.should_reduce_concurrency():
                        self.max_concurrent = max(2, self.max_concurrent - 1)


if __name__ == "__main__":
    import doctest 
    doctest.testmod()