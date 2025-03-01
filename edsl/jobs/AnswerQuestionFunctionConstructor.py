import copy
import asyncio

from typing import Union, Type, Callable, TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from edsl.questions.QuestionBase import QuestionBase
    from edsl.jobs.interviews.Interview import Interview
    from edsl.language_models.key_management.KeyLookup import KeyLookup
    from edsl.agents.InvigilatorBase import InvigilatorBase

from edsl.surveys.base import EndOfSurvey
from edsl.jobs.tasks.task_status_enum import TaskStatus

from edsl.jobs.FetchInvigilator import FetchInvigilator
from edsl.exceptions.language_models import LanguageModelNoResponseError
from edsl.exceptions.questions import QuestionAnswerValidationError
from edsl.data_transfer_models import AgentResponseDict, EDSLResultObjectInput

from edsl.jobs.Answers import Answers


class RetryConfig:
    from edsl.config import CONFIG

    EDSL_BACKOFF_START_SEC = float(CONFIG.get("EDSL_BACKOFF_START_SEC"))
    EDSL_BACKOFF_MAX_SEC = float(CONFIG.get("EDSL_BACKOFF_MAX_SEC"))
    EDSL_MAX_ATTEMPTS = int(CONFIG.get("EDSL_MAX_ATTEMPTS"))


class SkipHandler:
    """Handles skipping questions.
    
    Skipping occurs when a question is skipped by the skip rule. 

    >>> from edsl.jobs.interviews.Interview import Interview
    >>> from edsl.jobs.AnswerQuestionFunctionConstructor import SkipHandler
    >>> i = Interview.example()
    >>> i.answers = {'q0': 'yes'}
    >>> sh = SkipHandler(i)
    >>> sh.should_skip(i.survey.questions[0])
    False
    >>> sh.should_skip(i.survey.questions[1])
    True
    """

    def __init__(self, interview: "Interview"):
        self.interview = interview
        self.question_index = self.interview.to_index

        self.skip_function: Callable = (
            self.interview.survey.rule_collection.skip_question_before_running
        )

    def _current_interview_state(self) -> dict:
        return {
            "answers": self.interview.answers,
            "scenario": self.interview.scenario,
            "agent_traits": self.interview.agent["traits"],
        }

    def should_skip(self, current_question: "QuestionBase") -> bool:
        """Determine if the current question should be skipped.
        
        I *think* this is to handle skip-logic where you get a to a question and then learn if you 
        should skip it. It is not for normal flow control.
        """
        current_question_index = self.question_index[current_question.question_name]
        current_state = self._current_interview_state()
        return self.skip_function(current_question_index, current_state)
    
    def _cancel_between(self, start: int, end: int) -> None:
        """Cancel the tasks for questions between the start and end indices."""
        for i in range(start, end):
            self.interview.skip_flags[self.interview.survey.questions[i].question_name] = True

    def _get_current_and_next_question_indices(self, current_question: "QuestionBase") -> Tuple[int, int]:
        """Get the indices of the current and next question."""
        current_question_index: int = self.interview.to_index[
            current_question.question_name
        ]
        next_question = self.interview.survey.rule_collection.next_question(
            q_now=current_question_index,
            answers=self._current_interview_state(),
        )
        next_question_index: int = next_question.next_q
        return current_question_index, next_question_index


    def cancel_skipped_questions(self, current_question: "QuestionBase") -> None:
        """Cancel the tasks for questions that should be skipped."""
        # current_question_index: int = self.interview.to_index[
        #     current_question.question_name
        # ]
        
        # current_state = self._current_interview_state()

        # # Get the index of the next question, which could also be the end of the survey
        # next_question: Union[int, EndOfSurvey] = (
        #     self.interview.survey.rule_collection.next_question(
        #         q_now=current_question_index,
        #         answers=current_state,
        #     )
        # )
        current_question_index, next_question_index = self._get_current_and_next_question_indices(current_question)

        if next_question_index == EndOfSurvey:
            # If the next question is the end of the survey, cancel all tasks after the current question
            self._cancel_between(
                start=current_question_index + 1, 
                end=len(self.interview.survey.questions)
            )
            return

        if next_question_index > (current_question_index + 1):
            # If the next question is after the current question, cancel all tasks between the current question and the next question
            self._cancel_between(start=current_question_index + 1, 
                                 end=next_question_index)

        


class AnswerQuestionFunctionConstructor:
    """Constructs a function that answers a question and records the answer."""

    def __init__(self, interview: "Interview", key_lookup: "KeyLookup"):
        self.interview = interview
        self.key_lookup = key_lookup

        self.had_language_model_no_response_error: bool = False
        self.question_index = self.interview.to_index

        self.skip_function: Callable = (
            self.interview.survey.rule_collection.skip_question_before_running
        )

        self.invigilator_fetcher = FetchInvigilator(
            self.interview, key_lookup=self.key_lookup
        )
        self.skip_handler = SkipHandler(self.interview)

    def _handle_exception(
        self, e: Exception, invigilator: "InvigilatorBase", task=None
    ):
        """Handle an exception that occurred while answering a question."""

        from edsl.jobs.interviews.InterviewExceptionEntry import InterviewExceptionEntry

        answers = copy.copy(
            self.interview.answers
        )  # copy to freeze the answers here for logging
        exception_entry = InterviewExceptionEntry(
            exception=e,
            invigilator=invigilator,
            answers=answers,
        )
        if task:
            task.task_status = TaskStatus.FAILED

        self.interview.exceptions.add(
            invigilator.question.question_name, exception_entry
        )

        if self.interview.raise_validation_errors and isinstance(
            e, QuestionAnswerValidationError
        ):
            raise e

        stop_on_exception = getattr(self.interview, "stop_on_exception", False)
        if stop_on_exception:
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
            retry,
            stop_after_attempt,
            wait_exponential,
            retry_if_exception_type,
            RetryError,
        )

        @retry(
            stop=stop_after_attempt(RetryConfig.EDSL_MAX_ATTEMPTS),
            wait=wait_exponential(
                multiplier=RetryConfig.EDSL_BACKOFF_START_SEC,
                max=RetryConfig.EDSL_BACKOFF_MAX_SEC,
            ),
            retry=retry_if_exception_type(LanguageModelNoResponseError),
            reraise=True,
        )
        async def attempt_answer():
            invigilator = self.invigilator_fetcher(question)

            if self.interview.skip_flags.get(question.question_name, False):
                return invigilator.get_failed_task_result(
                    failure_reason="Question skipped."
                )

            if self.skip_handler.should_skip(question):
                return invigilator.get_failed_task_result(
                    failure_reason="Question skipped."
                )

            try:
                response: EDSLResultObjectInput = (
                    await invigilator.async_answer_question()
                )
                if response.validated:
                    self.interview.answers.add_answer(
                        response=response, question=question
                    )

                    self.skip_handler.cancel_skipped_questions(question)
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

            except asyncio.TimeoutError as e:
                self._handle_exception(e, invigilator, task)
                had_language_model_no_response_error = True
                raise LanguageModelNoResponseError(
                    f"Language model timed out for question '{question.question_name}.'"
                )

            except Exception as e:
                self._handle_exception(e, invigilator, task)

            if "response" not in locals():
                had_language_model_no_response_error = True
                raise LanguageModelNoResponseError(
                    f"Language model did not return a response for question '{question.question_name}.'"
                )

            if (
                question.question_name in self.interview.exceptions
                and had_language_model_no_response_error
            ):
                self.interview.exceptions.record_fixed_question(question.question_name)

            return response

        try:
            return await attempt_answer()
        except RetryError as retry_error:
            original_error = retry_error.last_attempt.exception()
            self._handle_exception(
                original_error, self.invigilator_fetcher(question), task
            )
            raise original_error


if __name__ == "__main__":
    import doctest
    doctest.testmod()