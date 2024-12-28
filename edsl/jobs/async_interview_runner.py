from collections.abc import AsyncGenerator
from typing import List, TypeVar, Generator, Tuple
from dataclasses import dataclass
import asyncio
from contextlib import asynccontextmanager
from edsl.data_transfer_models import EDSLResultObjectInput

from edsl.results.Result import Result
from edsl.jobs.interviews.Interview import Interview


@dataclass
class InterviewResult:
    result: Result
    interview: Interview
    order: int


class AsyncInterviewRunner:
    MAX_CONCURRENT = 5

    def __init__(
        self,
        jobs: "Jobs",
        n: int,
        cache: "Cache",
        stop_on_exception: bool,
        bucket_collection: "BucketCollection",
        raise_validation_errors: bool,
        key_lookup: "KeyLookup",
        jobs_runner_status: "JobsRunnerStatus",
    ):
        self.jobs = jobs
        self.n = n
        self.cache = cache
        self.stop_on_exception = stop_on_exception
        self._initialized = asyncio.Event()
        self.bucket_collection = bucket_collection
        self.raise_validation_errors = raise_validation_errors
        self.key_lookup = key_lookup
        self.jobs_runner_status = jobs_runner_status

    def _expand_interviews(self) -> Generator["Interview", None, None]:
        """Populates self.total_interviews with n copies of each interview.

        It also has to set the cache for each interview.

        :param n: how many times to run each interview.
        """
        for interview in self.jobs.generate_interviews():
            for iteration in range(self.n):
                if iteration > 0:
                    yield interview.duplicate(iteration=iteration, cache=self.cache)
                else:
                    interview.cache = self.cache
                    yield interview

    async def _conduct_interview(
        self, interview: "Interview"
    ) -> Tuple["Result", "Interview"]:
        """Conducts an interview and returns the result object, along with the associated interview.

        We return the interview because it is not populated with exceptions, if any.

        :param interview: the interview to conduct
        :return: the result of the interview

        'extracted_answers' is a dictionary of the answers to the questions in the interview.
        This is not the same as the generated_tokens---it can include substantial cleaning and processing / validation.
        """
        # the model buckets are used to track usage rates
        model_buckets = self.bucket_collection[interview.model]

        # get the results of the interview e.g., {'how_are_you':"Good" 'how_are_you_generated_tokens': "Good"}
        extracted_answers: dict[str, str]
        model_response_objects: List[EDSLResultObjectInput]

        extracted_answers, model_response_objects = (
            await interview.async_conduct_interview(
                model_buckets=model_buckets,
                stop_on_exception=self.stop_on_exception,
                raise_validation_errors=self.raise_validation_errors,
                key_lookup=self.key_lookup,
            )
        )
        result = Result.from_interview(
            interview=interview,
            extracted_answers=extracted_answers,
            model_response_objects=model_response_objects,
        )
        return result, interview

    async def run_async_generator(
        self,
    ) -> AsyncGenerator[tuple[Result, Interview], None]:
        """Creates and processes tasks asynchronously, yielding results as they complete.

        Uses TaskGroup for structured concurrency and automated cleanup.
        Results are yielded as they become available while maintaining controlled concurrency.
        """
        interviews = list(self._expand_interviews())
        self._initialized.set()

        async def _process_single_interview(
            interview: Interview, idx: int
        ) -> InterviewResult:
            try:
                result, interview = await self._conduct_interview(interview)
                self.jobs_runner_status.add_completed_interview(result)
                result.order = idx
                return InterviewResult(result, interview, idx)
            except Exception as e:
                if self.stop_on_exception:
                    raise
                # logger.error(f"Task failed with error: {e}")
                return None

        # Process interviews in chunks
        for i in range(0, len(interviews), self.MAX_CONCURRENT):
            chunk = interviews[i : i + self.MAX_CONCURRENT]
            tasks = [
                asyncio.create_task(_process_single_interview(interview, idx))
                for idx, interview in enumerate(chunk, start=i)
            ]

            try:
                # Wait for all tasks in the chunk to complete
                results = await asyncio.gather(
                    *tasks, return_exceptions=not self.stop_on_exception
                )

                # Process successful results
                for result in (r for r in results if r is not None):
                    yield result.result, result.interview

            except Exception as e:
                if self.stop_on_exception:
                    raise
                # logger.error(f"Chunk processing failed with error: {e}")
                continue

            finally:
                # Clean up any remaining tasks
                for task in tasks:
                    if not task.done():
                        task.cancel()
