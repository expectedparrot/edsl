import asyncio
import copy

from typing import Union, Type, Callable
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
)

from edsl import CONFIG
from edsl.questions.QuestionBase import QuestionBase
from edsl.surveys.base import EndOfSurvey
from edsl.jobs.interviews.InterviewExceptionEntry import InterviewExceptionEntry
from edsl.jobs.tasks.task_status_enum import TaskStatus


EDSL_BACKOFF_START_SEC = float(CONFIG.get("EDSL_BACKOFF_START_SEC"))
EDSL_BACKOFF_MAX_SEC = float(CONFIG.get("EDSL_BACKOFF_MAX_SEC"))
EDSL_MAX_ATTEMPTS = int(CONFIG.get("EDSL_MAX_ATTEMPTS"))

from edsl.jobs.FetchInvigilator import FetchInvigilator
from edsl.exceptions.language_models import LanguageModelNoResponseError

from edsl.exceptions import QuestionAnswerValidationError
from edsl.exceptions import QuestionAnswerValidationError
from edsl.data_transfer_models import AgentResponseDict, EDSLResultObjectInput

from edsl.jobs.Answers import Answers


class AnswerQuestionFunctionConstructor:
    def __init__(self, interview):
        self.interview = interview
        self.had_language_model_no_response_error = False
        self.question_index = self.interview.to_index

        self.skip_function: Callable = (
            self.interview.survey.rule_collection.skip_question_before_running
        )

    def _combined_answers(self) -> Answers:
        return self.answers | self.interview.scenario | self.interview.agent["traits"]

    @property
    def answers(self) -> Answers:
        return self.interview.answers

    def _skip_this_question(self, current_question: "QuestionBase") -> bool:
        current_question_index = self.question_index[current_question.question_name]
        combined_answers = self._combined_answers()
        return self.skip_function(current_question_index, combined_answers)

    def _handle_exception(
        self, e: Exception, invigilator: "InvigilatorBase", task=None
    ):
        answers = copy.copy(self.answers)  # copy to freeze the answers here for logging
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

    def _cancel_skipped_questions(self, current_question: QuestionBase) -> None:
        current_question_index: int = self.interview.to_index[
            current_question.question_name
        ]
        answers = (
            self.answers | self.interview.scenario | self.interview.agent["traits"]
        )

        # Get the index of the next question, which could also be the end of the survey
        next_question: Union[int, EndOfSurvey] = (
            self.interview.survey.rule_collection.next_question(
                q_now=current_question_index,
                answers=answers,
            )
        )

        def cancel_between(start, end):
            for i in range(start, end):
                self.interview.tasks[i].cancel()

        if (next_question_index := next_question.next_q) == EndOfSurvey:
            cancel_between(
                current_question_index + 1, len(self.interview.survey.questions)
            )
            return

        if next_question_index > (current_question_index + 1):
            cancel_between(current_question_index + 1, next_question_index)

    def __call__(self):
        async def answer_question_and_record_task(
            *,
            question: "QuestionBase",
            task=None,
        ) -> "AgentResponseDict":
            @retry(
                stop=stop_after_attempt(EDSL_MAX_ATTEMPTS),
                wait=wait_exponential(
                    multiplier=EDSL_BACKOFF_START_SEC, max=EDSL_BACKOFF_MAX_SEC
                ),
                retry=retry_if_exception_type(LanguageModelNoResponseError),
                reraise=True,
            )
            async def attempt_answer():

                invigilator = FetchInvigilator(self.interview)(question)

                if self._skip_this_question(question):
                    return invigilator.get_failed_task_result(
                        failure_reason="Question skipped."
                    )

                try:
                    response: EDSLResultObjectInput = (
                        await invigilator.async_answer_question()
                    )
                    if response.validated:
                        self.answers.add_answer(response=response, question=question)
                        self._cancel_skipped_questions(question)
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
                    self.interview.exceptions.record_fixed_question(
                        question.question_name
                    )

                return response

            try:
                return await attempt_answer()
            except RetryError as retry_error:
                original_error = retry_error.last_attempt.exception()
                self._handle_exception(
                    original_error, FetchInvigilator(self.interview)(question), task
                )
                raise original_error

        return answer_question_and_record_task
