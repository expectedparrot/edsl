"""
Asynchronous interview runner module for conducting interviews concurrently.

This module provides functionality to run multiple interviews in parallel
with controlled concurrency, supporting both error handling and result collection.
"""

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from typing import List, Generator, Tuple, TYPE_CHECKING, AsyncIterator
from dataclasses import dataclass
import asyncio
from ..data_transfer_models import EDSLResultObjectInput

from ..results import Result
from ..interviews import Interview
from ..config import Config
from .data_structures import RunConfig

config = Config()

if TYPE_CHECKING:
    from ..jobs import Jobs

@dataclass
class InterviewBatch:
    """Container for a batch of interviews being processed."""
    chunks: List[Tuple[int, Interview]]
    results: List[Tuple[Result, Interview, int]]
    failed: List[Tuple[int, Interview, Exception]]

    @classmethod
    def create(cls, chunks: List[Tuple[int, Interview]]) -> 'InterviewBatch':
        return cls(chunks=chunks, results=[], failed=[])

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

    MAX_CONCURRENT = int(config.EDSL_MAX_CONCURRENT_TASKS)

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

    @asynccontextmanager
    async def _manage_tasks(self, tasks: List[asyncio.Task]) -> AsyncIterator[None]:
        """Context manager for handling task lifecycle and cleanup."""
        try:
            yield
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()

    @asynccontextmanager
    async def _interview_batch_processor(self) -> AsyncIterator[AsyncGenerator[tuple[Result, Interview], None]]:
        """Context manager for processing batches of interviews.
        
        Handles initialization, cleanup, and error management for the entire
        interview processing lifecycle.
        """
        self._initialized.set()
        self._current_idx = 0
        interview_generator = self._expand_interviews()
        
        try:
            async def process_batches() -> AsyncGenerator[tuple[Result, Interview], None]:
                while True:
                    chunk = self._get_next_chunk(interview_generator)
                    if not chunk:
                        break
                    
                    async with self._process_chunk(chunk) as results:
                        for result, interview, _ in (r for r in results if r is not None):
                            yield result, interview
            
            yield process_batches()
            
        finally:
            # Cleanup code if needed
            self._current_idx = 0
            self._initialized.clear()

    async def _run_single_interview(
        self, interview: Interview, idx: int
    ) -> Tuple[Result, Interview, int]:
        """Execute a single interview with error handling."""
        try:
            await interview.async_conduct_interview(self.run_config)
            result = Result.from_interview(interview)
            self.run_config.environment.jobs_runner_status.add_completed_interview(
                interview
            )
            return (result, interview, idx)
        except Exception as e:
            if self.run_config.parameters.stop_on_exception:
                raise
            # Could log the error here if needed
            return None

    @asynccontextmanager
    async def _process_chunk(
        self, chunk: List[Tuple[int, Interview]]
    ) -> AsyncIterator[List[Tuple[Result, Interview, int]]]:
        """Process a chunk of interviews concurrently."""
        tasks = [
            asyncio.create_task(self._run_single_interview(interview, idx))
            for idx, interview in chunk
        ]
                
        async with self._manage_tasks(tasks):
            results = await asyncio.gather(
                *tasks,
                return_exceptions=not self.run_config.parameters.stop_on_exception
            )
            yield [r for r in results if r is not None]

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

    def _get_next_chunk(
        self,
        gen: Generator[Interview, None, None]
    ) -> List[Tuple[int, Interview]]:
        """Take interviews from the generator up to MAX_CONCURRENT."""
        chunk = []
        while len(chunk) < self.MAX_CONCURRENT:
            try:
                interview = next(gen)
                chunk.append((self._current_idx, interview))
                self._current_idx += 1
            except StopIteration:
                break
        return chunk

    async def run(self) -> AsyncGenerator[tuple[Result, Interview], None]:
        """
        Run all interviews asynchronously and yield results as they complete.

        This method orchestrates the parallel execution of interviews while
        maintaining controlled concurrency. Results are yielded as soon as
        they become available.

        Yields:
            Tuples of (Result, Interview) as interviews complete
        
        Raises:
            Exception: If stop_on_exception is True and any interview fails
        """
        async with self._interview_batch_processor() as processor:
            async for result in processor:
                yield result

if __name__ == "__main__":
    import doctest

    doctest.testmod()
