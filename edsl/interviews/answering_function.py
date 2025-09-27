import asyncio
import copy
import weakref
from typing import TYPE_CHECKING, Any, Callable, Union

if TYPE_CHECKING:
    from ..invigilators.invigilator_base import InvigilatorBase
    from ..key_management import KeyLookup
    from ..questions import QuestionBase
    from .interview import Interview

from ..data_transfer_models import EDSLResultObjectInput
from ..jobs.fetch_invigilator import FetchInvigilator
from ..language_models.exceptions import (
    LanguageModelNoResponseError,
    LanguageModelInsufficientCreditsError,
)
from ..questions.exceptions import QuestionAnswerValidationError
from ..surveys.base import EndOfSurvey
from ..tasks import TaskStatus
from ..logger import get_logger
from .exception_tracking import InterviewExceptionEntry


class RetryConfig:
    from ..config import CONFIG

    EDSL_BACKOFF_START_SEC = float(CONFIG.get("EDSL_BACKOFF_START_SEC"))
    EDSL_BACKOFF_MAX_SEC = float(CONFIG.get("EDSL_BACKOFF_MAX_SEC"))
    EDSL_MAX_ATTEMPTS = int(CONFIG.get("EDSL_MAX_ATTEMPTS"))


class SkipHandler:
    def __init__(self, interview: "Interview"):
        # Store a weak reference to the interview
        self._interview_ref = weakref.ref(interview)

        # Cache only the skip function which doesn't maintain a reference to the interview
        try:
            self.skip_function: Callable = (
                interview.survey.rule_collection.skip_question_before_running
            )
        except (AttributeError, KeyError):
            # Fallback for test environments
            self.skip_function = lambda *args: False

    @property
    def interview(self):
        """Access the interview via weak reference if it still exists."""
        interview = self._interview_ref()
        if interview is None:
            raise RuntimeError("Interview has been garbage collected")
        return interview

    @property
    def _to_index(self):
        return self.interview.to_index

    @property
    def _survey(self):
        return self.interview.survey

    @property
    def _answers(self):
        return self.interview.answers

    @property
    def _scenario(self):
        return self.interview.scenario

    @property
    def _agent_traits(self):
        try:
            return self.interview.agent["traits"]
        except (AttributeError, KeyError):
            return {}

    @property
    def _skip_flags(self):
        return self.interview.skip_flags

    def should_skip(self, current_question: "QuestionBase") -> bool:
        """Determine if the current question should be skipped."""
        current_question_index = self._to_index[current_question.question_name]

        # Handle ScenarioList case - convert to dict first
        scenario_dict = {}
        if hasattr(self._scenario, "items"):
            # Handle standard dict scenario
            scenario_dict = self._scenario
        else:
            # Handle ScenarioList or other scenario object
            # Access as a dict if possible, otherwise try to convert
            scenario_dict = (
                dict(self._scenario) if hasattr(self._scenario, "__iter__") else {}
            )

        combined_answers = dict(self._answers)
        combined_answers.update(scenario_dict)
        combined_answers.update(self._agent_traits)

        return self.skip_function(current_question_index, combined_answers)

    def _current_info_env(self) -> dict[str, Any]:
        """
        - The current answers are "generated_tokens" and "comment"
        - The scenario should have "scenario." added to the keys
        - The agent traits should have "agent." added to the keys
        """
        # Check if we have cached static components
        if not hasattr(self, "_scenario_cache"):
            self._scenario_cache = {
                f"scenario.{k}": v for k, v in self._scenario.items()
            }

        if not hasattr(self, "_agent_cache"):
            self._agent_cache = {f"agent.{k}": v for k, v in self._agent_traits.items()}

        # Simple check - if answers haven't changed, return cached result
        if (
            hasattr(self, "_last_answers_id")
            and id(self._answers) == self._last_answers_id
        ):
            return self._env_cache_result

        # Process answers dictionary
        processed_answers = {}
        for key, value in self._answers.items():
            if key.endswith("_generated_tokens"):
                base_name = key.replace("_generated_tokens", "")
                processed_answers[f"{base_name}.generated_tokens"] = value
            elif key.endswith("_comment"):
                base_name = key.replace("_comment", "")
                processed_answers[f"{base_name}.comment"] = value
            else:
                # Regular answer
                processed_answers[f"{key}.answer"] = value

        result = processed_answers | self._scenario_cache | self._agent_cache

        # Cache the result with object id
        self._last_answers_id = id(self._answers)
        self._env_cache_result = result

        return result

    def cancel_skipped_questions(self, current_question: "QuestionBase") -> None:
        """Cancel the tasks for questions that should be skipped."""
        current_question_index: int = self._to_index[current_question.question_name]
        answers = self._current_info_env()

        # Get the index of the next question, which could also be the end of the survey
        next_question: Union[
            int, EndOfSurvey
        ] = self._survey.rule_collection.next_question(
            q_now=current_question_index,
            answers=answers,
        )

        def cancel_between(start, end):
            """Cancel the tasks for questions between the start and end indices."""
            for i in range(start, end):
                # print(f"Cancelling task {i}")
                # self.interview.tasks[i].cancel()
                # self.interview.tasks[i].set_result("skipped")
                interview = self._interview_ref()
                if interview is not None:
                    interview.skip_flags[self._survey.questions[i].question_name] = True
                else:
                    # If interview is gone, there's nothing to skip anymore
                    return

        if (next_question_index := next_question.next_q) == EndOfSurvey:
            cancel_between(current_question_index + 1, len(self._survey.questions))
            return

        if next_question_index > (current_question_index + 1):
            cancel_between(current_question_index + 1, next_question_index)


class AnswerQuestionFunctionConstructor:
    """Constructs a function that answers a question and records the answer."""

    def __init__(
        self, interview: "Interview", key_lookup: "KeyLookup", run_config=None
    ):
        # Store a weak reference to the interview
        self._interview_ref = weakref.ref(interview)
        self.key_lookup = key_lookup
        self.run_config = run_config
        self._logger = get_logger(__name__)

        # Store configuration settings that won't change during lifecycle
        self._raise_validation_errors = getattr(
            interview, "raise_validation_errors", False
        )
        self._stop_on_exception = getattr(interview, "stop_on_exception", False)

        self.had_language_model_no_response_error: bool = False

        # Initialize fetch invigilator with the interview - this should use weakref internally
        self.invigilator_fetcher = FetchInvigilator(
            interview, key_lookup=self.key_lookup
        )

        # In our test environment, we might not be able to create the SkipHandler
        # because example Interview might not have all required attributes
        # So we'll initialize it conditionally
        if hasattr(interview, "skip_flags"):
            self.skip_handler = SkipHandler(interview)
        else:
            self.skip_handler = None

    @property
    def interview(self):
        """Access the interview via weak reference if it still exists."""
        interview = self._interview_ref()
        if interview is None:
            raise RuntimeError("Interview has been garbage collected")
        return interview

    @property
    def _answers(self):
        return self.interview.answers

    @property
    def _exceptions(self):
        return self.interview.exceptions

    @property
    def _to_index(self):
        return self.interview.to_index

    @property
    def _skip_flags(self):
        if hasattr(self.interview, "skip_flags"):
            return self.interview.skip_flags
        return {}

    def _handle_exception(
        self, e: Exception, invigilator: "InvigilatorBase", task=None
    ):
        """Handle an exception that occurred while answering a question."""
        interview = self._interview_ref()
        if interview is None:
            # If interview is gone, we can't really handle the exception properly
            # Just raise it to the caller
            raise e

        # Copy to freeze the answers here for logging
        answers = copy.copy(self._answers)

        exception_entry = InterviewExceptionEntry(
            exception=e,
            invigilator=invigilator,
            answers=answers,
        )

        if task:
            task.task_status = TaskStatus.FAILED

        # Add to exceptions - need to use the interview reference here
        interview.exceptions.add(invigilator.question.question_name, exception_entry)

        # Check if we should raise validation errors
        if self._raise_validation_errors and isinstance(
            e, QuestionAnswerValidationError
        ):
            raise e

        # Check if we should stop on exception
        if self._stop_on_exception:
            raise e

    def __call__(self):
        return self.answer_question_and_record_task

    async def answer_question_and_record_task(
        self,
        *,
        question: "QuestionBase",
        task=None,
    ) -> "EDSLResultObjectInput":
        from tenacity import (
            RetryError,
            retry,
            retry_if_exception_type,
            stop_after_attempt,
            wait_exponential,
        )

        def log_retry_attempt(retry_state):
            """Log when a retry is about to happen."""
            attempt_number = retry_state.attempt_number

            if attempt_number >= 1:  # Only log on actual retries, not the first attempt
                exception = (
                    retry_state.outcome.exception() if retry_state.outcome else None
                )
                print(f"\n{'='*60}", flush=True)
                print(
                    f"RETRY TRIGGERED for question '{question.question_name}'",
                    flush=True,
                )
                print(
                    f"Attempt: {attempt_number}/{RetryConfig.EDSL_MAX_ATTEMPTS}",
                    flush=True,
                )
                print(
                    f"Exception: {exception.__class__.__name__ if exception else 'Unknown'}: {str(exception) if exception else 'No exception details'}",
                    flush=True,
                )
                print("Waiting before retry...", flush=True)
                print(f"{'='*60}\n", flush=True)
                self._logger.warning(
                    f"Retrying question '{question.question_name}' (attempt {attempt_number}/{RetryConfig.EDSL_MAX_ATTEMPTS}) "
                    f"after {exception.__class__.__name__ if exception else 'error'}: {str(exception) if exception else 'unknown error'}"
                )

        def should_retry_exception(retry_state):
            """Only retry network/service errors, never balance errors"""
            # Extract the actual exception from the retry state
            if hasattr(retry_state, "outcome") and retry_state.outcome:
                exception = retry_state.outcome.exception()
            else:
                return False

            # Never retry balance errors - they won't be resolved by retrying
            if isinstance(exception, LanguageModelInsufficientCreditsError):
                return False

            # Only retry actual network/service errors
            if isinstance(exception, LanguageModelNoResponseError):
                return True

            # When stop_on_exception is False, also retry InferenceServiceIntendedError
            if not self._stop_on_exception:
                from ..inference_services.exceptions import (
                    InferenceServiceIntendedError,
                )

                if isinstance(exception, InferenceServiceIntendedError):
                    return True

            return False

        @retry(
            stop=stop_after_attempt(RetryConfig.EDSL_MAX_ATTEMPTS),
            wait=wait_exponential(
                multiplier=RetryConfig.EDSL_BACKOFF_START_SEC,
                max=RetryConfig.EDSL_BACKOFF_MAX_SEC,
            ),
            retry=should_retry_exception,
            reraise=True,
            # before_sleep=log_retry_attempt, --- IGNORE --- Used for debugging retries
        )
        async def attempt_answer():
            # Get a reference to the interview (may be None if it's been garbage collected)
            interview = self._interview_ref()

            # Get the invigilator for this question
            invigilator = self.invigilator_fetcher(question)

            # Check if interview still exists
            if interview is None:
                # If interview is gone, we can't really process this question
                # Return a failure result
                return invigilator.get_failed_task_result(
                    failure_reason="Interview has been garbage collected."
                )

            # Check if question should be skipped - use cached skip_flags if available
            skip_flags = getattr(self, "_skip_flags", None) or interview.skip_flags
            if skip_flags.get(question.question_name, False):
                return invigilator.get_failed_task_result(
                    failure_reason="Question skipped."
                )

            if self.skip_handler and self.skip_handler.should_skip(question):
                return invigilator.get_failed_task_result(
                    failure_reason="Question skipped."
                )

            had_language_model_no_response_error = False
            try:
                import time

                answer_start = time.time()
                self._logger.info(
                    f"Starting question '{question.question_name}' with {type(invigilator).__name__}"
                )

                response: EDSLResultObjectInput = (
                    await invigilator.async_answer_question()
                )

                answer_time = time.time() - answer_start
                self._logger.info(
                    f"Question '{question.question_name}' completed in {answer_time:.3f}s"
                )

                if response.validated:
                    # Re-check if interview exists before updating it
                    interview = self._interview_ref()
                    if interview is not None:
                        interview.answers.add_answer(
                            response=response, question=question
                        )
                        if self.skip_handler:
                            self.skip_handler.cancel_skipped_questions(question)

                        # Track question completion for real-time progress
                        try:
                            if (
                                self.run_config
                                and hasattr(self.run_config, "environment")
                                and hasattr(
                                    self.run_config.environment, "jobs_runner_status"
                                )
                                and self.run_config.environment.jobs_runner_status
                                is not None
                            ):
                                self.run_config.environment.jobs_runner_status.add_completed_question(
                                    model_name=interview.model.model,
                                    question_name=question.question_name,
                                )
                        except Exception as e:
                            # Don't let progress tracking break question answering
                            self._logger.warning(f"Progress tracking failed: {e}")
                else:
                    if (
                        hasattr(response, "exception_occurred")
                        and response.exception_occurred
                    ):
                        raise response.exception_occurred

            except QuestionAnswerValidationError as e:
                self._handle_exception(e, invigilator, task)
                return invigilator.get_failed_task_result(
                    failure_reason="Question answer validation failed."
                )

            except asyncio.TimeoutError:
                # Don't record exception yet - will retry
                # Only record exception if retry limit is reached (handled in except RetryError below)
                had_language_model_no_response_error = True
                raise LanguageModelNoResponseError(
                    f"Language model timed out for question '{question.question_name}.'"
                )

            except Exception as e:
                # For generic exceptions, record them immediately as they won't be retried
                self._handle_exception(e, invigilator, task)
                # Re-raise the exception so it can be checked by the retry mechanism
                raise

            if "response" not in locals():
                had_language_model_no_response_error = True
                raise LanguageModelNoResponseError(
                    f"Language model did not return a response for question '{question.question_name}.'"
                )

            # Re-check if interview exists before accessing exceptions
            interview = self._interview_ref()
            if (
                interview is not None
                and question.question_name in interview.exceptions
                and had_language_model_no_response_error
            ):
                interview.exceptions.record_fixed_question(question.question_name)

            return response

        try:
            out = await attempt_answer()
            return out
        except RetryError as retry_error:
            # print(f"\n{'='*60}", flush=True)
            # print(f"RETRY LIMIT REACHED for question '{question.question_name}'", flush=True)
            # print(f"All {RetryConfig.EDSL_MAX_ATTEMPTS} attempts exhausted", flush=True)
            # print(f"Final error: {retry_error.last_attempt.exception()}", flush=True)
            # print(f"{'='*60}\n", flush=True)

            # Now record the exception since retries are exhausted
            original_error = retry_error.last_attempt.exception()
            self._handle_exception(
                original_error, self.invigilator_fetcher(question), task
            )

            # Track permanently failed question for progress tracking
            interview = self._interview_ref()
            if (
                interview is not None
                and self.run_config
                and hasattr(self.run_config, "environment")
                and hasattr(self.run_config.environment, "jobs_runner_status")
                and self.run_config.environment.jobs_runner_status is not None
            ):
                self.run_config.environment.jobs_runner_status.add_failed_question(
                    model_name=interview.model.model,
                    question_name=question.question_name,
                )

            raise original_error
