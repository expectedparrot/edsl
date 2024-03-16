"""This module contains the Interview class, which is responsible for conducting an interview asynchronously."""
from __future__ import annotations
import traceback
import asyncio
import time
import textwrap
from typing import Any, Type, List, Generator, Tuple
from collections import defaultdict 

from edsl import CONFIG
from edsl.agents import Agent
from edsl.exceptions import InterviewTimeoutError
from edsl.language_models import LanguageModel
from edsl.questions import Question
from edsl.scenarios import Scenario
from edsl.surveys import Survey
from edsl.utilities.decorators import sync_wrapper
from edsl.data_transfer_models import AgentResponseDict
from edsl.jobs.Answers import Answers
from edsl.surveys.base import EndOfSurvey
from edsl.jobs.buckets import ModelBuckets
from edsl.jobs.token_tracking import InterviewTokenUsage

from edsl.jobs.task_management import (
    InterviewStatusDictionary,
    TasksList,
#    retry_strategy,
)
from edsl.jobs.retry_management import retry_strategy

from edsl.jobs.question_task_creator import QuestionTaskCreator, TaskCreators

TIMEOUT = float(CONFIG.get("EDSL_API_TIMEOUT"))

class Interview:
    """
    An 'interview' is one agent answering one survey, with one language model, for a given scenario.

    The main method is `async_conduct_interview`, which conducts the interview asynchronously.
    """

    def __init__(
        self,
        agent: Agent,
        survey: Survey,
        scenario: Scenario,
        model: Type[LanguageModel],
        verbose: bool = False,
        debug: bool = False,
        iteration: int = 0,
    ):
        """Initialize the Interview instance."""
        self.agent = agent
        self.survey = survey
        self.scenario = scenario
        self.model = model
        self.debug = debug
        self.verbose = verbose
        self.iteration = iteration

        self.answers: dict[
            str, str
        ] = Answers()  # will get filled in as interview progresses
        self.task_creators = TaskCreators()  # tracks the task creators

        self.exceptions = defaultdict(list)
        self.has_exceptions = False
        
    @property
    def dag(self):
        """Return the directed acyclic graph for the survey.

        The DAG, or directed acyclic graph, is a dictionary that maps question names to their dependencies.
        It is used to determine the order in which questions should be answered.
        This reflects both agent 'memory' considerations and 'skip' logic.
        The 'textify' parameter is set to True, so that the question names are returned as strings rather than integer indices.
        """
        return self.survey.dag(textify=True)

    @property
    def token_usage(self) -> InterviewTokenUsage:
        """Determine how many tokens were used for the interview."""
        return self.task_creators.token_usage

    @property
    def interview_status(self) -> InterviewStatusDictionary:
        """Return a dictionary mapping task status codes to counts."""
        return self.task_creators.interview_status

    @property
    def to_index(self) -> dict:
        """Return a dictionary mapping question names to their index in the survey."""
        return {
            question_name: index
            for index, question_name in enumerate(self.survey.question_names)
        }

    async def async_conduct_interview(
        self,
        *,
        model_buckets: ModelBuckets = None,
        debug: bool = False,
        replace_missing: bool = True,
    ) -> tuple["Answers", List[dict[str, Any]]]:
        """
        Conduct an interview asynchronously.

        params
        - `model_buckets`: a dictionary of token buckets for the model
        - `debug`: prints debug messages
        - `replace_missing`: if True, replaces missing answers with None
        """
        # if no model bucket is passed, create an 'infinity' bucket with no rate limits
        self.tasks = self._build_question_tasks(
            debug=debug, model_buckets=model_buckets or ModelBuckets.infinity_bucket()
        )

        self.invigilators = list(self._build_invigilators(debug=debug))

        await asyncio.gather(*self.tasks, return_exceptions=not debug)

        if replace_missing:
            self.answers.replace_missing_answers_with_none(self.survey)

        valid_results = list(self._extract_valid_results())

        return self.answers, valid_results

    def _extract_valid_results(
        self, print_traceback=False
    ) -> Generator["Answers", None, None]:
        """Extract the valid results from the list of results."""
        # we only need to print the warning once if a task failed.
        warning_printed = False
        warning_header = textwrap.dedent(
            """\
            WARNING: At least one question in the survey was not answered.
            """
        )
        # there should be one one invigilator for each task
        assert len(self.tasks) == len(self.invigilators)

        for task, invigilator in zip(self.tasks, self.invigilators):
            if task.done():
                try:  # task worked
                    result = task.result()
                except asyncio.CancelledError:  # task was cancelled
                    result = invigilator.get_failed_task_result()
                except (
                    Exception
                ) as exception:  # any other kind of exception in the task
                    if not warning_printed:
                        warning_printed = True
                        print(warning_header)

                    error_message = f"Task `{task.edsl_name}` failed with `{exception.__class__.__name__}`:`{exception}`."
                    print(error_message)
                    if print_traceback:
                        traceback.print_exc()
                    result = invigilator.get_failed_task_result()

                yield result
            else:
                raise ValueError(f"Task {task.edsl_name} is not done.")

    def _build_invigilators(self, debug: bool) -> Generator["Invigilator", None, None]:
        """Create an invigilator for each question."""
        for question in self.survey.questions:
            yield self.get_invigilator(question=question, debug=debug)

    def _build_question_tasks(
        self,
        debug: bool,
        model_buckets: ModelBuckets,
    ) -> List[asyncio.Task]:
        """Create a task for each question, with dependencies on the questions that must be answered before this one can be answered."""
        tasks = []
        for question in self.survey.questions:
            tasks_that_must_be_completed_before = list(
                self._get_tasks_that_must_be_completed_before(
                    tasks=tasks, question=question
                )
            )
            question_task = self._create_question_task(
                question=question,
                tasks_that_must_be_completed_before=tasks_that_must_be_completed_before,
                model_buckets=model_buckets,
                debug=debug,
                iteration=self.iteration,
            )
            tasks.append(question_task)
        return TasksList(tasks)  # , invigilators

    def _get_tasks_that_must_be_completed_before(
        self, *, tasks: List[asyncio.Task], question: Question
    ) -> Generator[asyncio.Task, None, None]:
        """Return the tasks that must be completed before the given question can be answered.

        If a question has no dependencies, this will be an empty list, [].
        """
        parents_of_focal_question = self.dag.get(question.question_name, [])
        for parent_question_name in parents_of_focal_question:
            parent_index = self.to_index[parent_question_name]
            parent_task = tasks[parent_index]
            yield parent_task

    def _create_question_task(
        self,
        *,
        question: Question,
        tasks_that_must_be_completed_before: List[asyncio.Task],
        model_buckets: ModelBuckets,
        debug: bool,
        iteration: int = 0,
    ) -> asyncio.Task:
        """Create a task that depends on the passed-in dependencies that are awaited before the task is run.

        The task is created by a QuestionTaskCreator, which is responsible for creating the task and managing its dependencies.
        It is passed a reference to the function that will be called to answer the question.
        It is passed a list "tasks_that_must_be_completed_before" that are awaited before the task is run.
        These are added as a dependency to the focal task.
        """
        task_creator = QuestionTaskCreator(
            question=question,
            answer_question_func=self._answer_question_and_record_task,
            token_estimator=self._get_estimated_request_tokens,
            model_buckets=model_buckets,
            iteration=iteration,
        )
        for task in tasks_that_must_be_completed_before:
            task_creator.add_dependency(task)

        self.task_creators.update(
            {question.question_name: task_creator}
        )  # track this task creator
        return task_creator.generate_task(debug)
    

    def async_timeout_handler(timeout):
        """Handle timeouts for async functions."""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                try:
                    return await asyncio.wait_for(func(*args, **kwargs), timeout)
                except asyncio.TimeoutError:
                    raise InterviewTimeoutError(
                        f"Task timed out after {timeout} seconds."
                    )

            return wrapper

        return decorator

    def get_invigilator(self, question: Question, debug: bool) -> "Invigilator":
        """Return an invigilator for the given question."""
        invigilator = self.agent.create_invigilator(
            question=question,
            scenario=self.scenario,
            model=self.model,
            debug=debug,
            memory_plan=self.survey.memory_plan,
            current_answers=self.answers,
            iteration=self.iteration,
        )
        """Return an invigilator for the given question."""
        return invigilator

    def _get_estimated_request_tokens(self, question) -> float:
        """Estimate the number of tokens that will be required to run the focal task."""
        invigilator = self.get_invigilator(question, debug=False)
        # TODO: There should be a way to get a more accurate estimate.
        combined_text = ""
        for prompt in invigilator.get_prompts().values():
            if hasattr(prompt, "text"):
                combined_text += prompt.text
            elif isinstance(prompt, str):
                combined_text += prompt
            else:
                raise ValueError(f"Prompt is of type {type(prompt)}")
        return len(combined_text) / 4.0

    @retry_strategy
    async def _answer_question_and_record_task(
        self,
        question: Question,
        debug: bool,
    ) -> AgentResponseDict:
        """Answer a question and records the task.
        
        This in turn calls the the passed-in agent's async_answer_question method, which returns a response dictionary.
        Note that is updates answers with the response.
        """
        invigilator = self.get_invigilator(question, debug=debug)

        async def attempt_to_answer_question(invigilator):
             try:
                 return await asyncio.wait_for(invigilator.async_answer_question(), timeout=TIMEOUT)
             except asyncio.TimeoutError as e:
                self.has_exceptions = True
                self.exceptions[question.question_name].append(
                    {
                        'exception': repr(e), 
                        'traceback': traceback.format_exc(),
                        'time': time.time()})
                raise InterviewTimeoutError(
                        f"Task timed out after {TIMEOUT} seconds."
                )
             except Exception as e:
                self.has_exceptions = True
                self.exceptions[question.question_name].append(
                    {
                        'exception': repr(e), 
                        'traceback': traceback.format_exc(),
                        'time': time.time()})
                raise e
                #raise  # Reraise to be caught by retry mechanism

        response: AgentResponseDict = await attempt_to_answer_question(invigilator)

        self.answers.add_answer(response=response, question=question)
        self._cancel_skipped_questions(question)

        return AgentResponseDict(**response)

    def _cancel_skipped_questions(self, current_question: Question) -> None:
        """Cancel the tasks for questions that are skipped.

        It first determines the next question, given the current question and the current answers.
        If the next question is the end of the survey, it cancels all remaining tasks.
        If the next question is after the current question, it cancels all tasks between the current question and the next question.
        """
        current_question_index = self.to_index[current_question.question_name]
        next_question = self.survey.rule_collection.next_question(
            q_now=current_question_index, answers=self.answers
        )
        next_question_index = next_question.next_q

        def cancel_between(start, end):
            """Cancel the tasks between the start and end indices."""
            for i in range(start, end):
                self.tasks[i].cancel()

        if next_question_index == EndOfSurvey:
            cancel_between(current_question_index + 1, len(self.survey.questions))
            return

        if next_question_index > (current_question_index + 1):
            cancel_between(current_question_index + 1, next_question_index)

    #######################
    # Dunder methods
    #######################
    def __repr__(self) -> str:
        """Return a string representation of the Interview instance."""
        return f"Interview(agent = {self.agent}, survey = {self.survey}, scenario = {self.scenario}, model = {self.model})"


if __name__ == "__main__":
    """Test the Interview class."""
    from edsl.language_models import LanguageModelOpenAIThreeFiveTurbo
    from edsl.agents import Agent
    from edsl.surveys import Survey
    from edsl.scenarios import Scenario
    from edsl.questions import QuestionMultipleChoice

    # from edsl.jobs.Interview import Interview

    #  a survey with skip logic
    q0 = QuestionMultipleChoice(
        question_text="Do you like school?",
        question_options=["yes", "no"],
        question_name="q0",
    )
    q1 = QuestionMultipleChoice(
        question_text="Why not?",
        question_options=["killer bees in cafeteria", "other"],
        question_name="q1",
    )
    q2 = QuestionMultipleChoice(
        question_text="Why?",
        question_options=["**lack*** of killer bees in cafeteria", "other"],
        question_name="q2",
    )
    s = Survey(questions=[q0, q1, q2])
    s = s.add_rule(q0, "q0 == 'yes'", q2)

    # create an interview
    a = Agent(traits=None)

    def direct_question_answering_method(self, question, scenario):
        """Answer a question directly."""
        raise Exception("Error!")
        # return "yes"

    a.add_direct_question_answering_method(direct_question_answering_method)
    scenario = Scenario()
    m = LanguageModelOpenAIThreeFiveTurbo(use_cache=False)
    I = Interview(agent=a, survey=s, scenario=scenario, model=m)

    result = asyncio.run(I.async_conduct_interview())
    # # conduct five interviews
    # for _ in range(5):
    #     I.conduct_interview(debug=True)

    # # replace missing answers
    # I
    # repr(I)
    # eval(repr(I))
