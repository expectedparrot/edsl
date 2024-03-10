from __future__ import annotations
import traceback
import asyncio
import logging
import textwrap
from collections import UserList
from typing import Any, Type, List, Generator, Callable, List, Tuple
from collections import defaultdict

# from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type, AsyncRetrying, before_sleep
from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type,
    before_sleep,
)


from edsl import CONFIG
from edsl.agents import Agent
from edsl.exceptions import InterviewErrorPriorTaskCanceled, InterviewTimeoutError
from edsl.language_models import LanguageModel
from edsl.questions import Question
from edsl.scenarios import Scenario
from edsl.surveys import Survey
from edsl.utilities.decorators import sync_wrapper
from edsl.data_transfer_models import AgentResponseDict
from edsl.jobs.Answers import Answers

from edsl.surveys.base import EndOfSurvey

from edsl.jobs.buckets import ModelBuckets
from edsl.jobs.token_tracking import TokenUsage, InterviewTokenUsage

from edsl.jobs.task_management import (
    InterviewStatusDictionary,
    QuestionTaskCreator,
    TasksList,
)


# create logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.propagate = False
# create  file handler
fh = logging.FileHandler(CONFIG.get("EDSL_LOGGING_PATH"))
fh.setLevel(logging.INFO)
# add formatter to the handlers
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(funcName)s - %(message)s"
)
fh.setFormatter(formatter)
# add handler to logger
logger.addHandler(fh)

# start loggin'
logger.info("Interview.py loaded")

TIMEOUT = float(CONFIG.get("EDSL_API_TIMEOUT"))
EDSL_BACKOFF_START_SEC = float(CONFIG.get("EDSL_BACKOFF_START_SEC"))
EDSL_MAX_BACKOFF_SEC = float(CONFIG.get("EDSL_MAX_BACKOFF_SEC"))
EDSL_MAX_ATTEMPTS = int(CONFIG.get("EDSL_MAX_ATTEMPTS"))


def print_retry(retry_state):
    "Prints details on tenacity retries"
    attempt_number = retry_state.attempt_number
    exception = retry_state.outcome.exception()
    wait_time = retry_state.next_action.sleep
    print(
        f"Attempt {attempt_number} failed with exception: {exception}; "
        f"now waiting {wait_time:.2f} seconds before retrying."
    )


retry_strategy = retry(
    wait=wait_exponential(
        multiplier=EDSL_BACKOFF_START_SEC, max=EDSL_MAX_BACKOFF_SEC
    ),  # Exponential back-off starting at 1s, doubling, maxing out at 60s
    stop=stop_after_attempt(EDSL_MAX_ATTEMPTS),  # Stop after 5 attempts
    # retry=retry_if_exception_type(Exception),  # Customize this as per your specific retry-able exception
    before_sleep=print_retry,  # Use custom print function for retries
)

class Interview:
    """
    An 'interview' is one agent answering one survey, with one language model, for a given scenario.
    """

    def __init__(
        self,
        agent: Agent,
        survey: Survey,
        scenario: Scenario,
        model: Type[LanguageModel],
        verbose: bool = False,
        debug: bool = False,
        iteration:int = 0
    ):
        self.agent = agent
        self.survey = survey
        self.scenario = scenario
        self.model = model
        self.debug = debug
        self.verbose = verbose
        self.iteration = iteration

        self.answers: dict[str, str] = Answers()  # will get filled in

        logger.info(f"Interview instantiated")
        # task creators is a dictionary that maps question names to their task creators.
        # this is used to track the status of each task for real-time reporting on status of a job
        # being executed.
        # 1 task = 1 question.
        self.task_creators = {}

    @property
    def dag(self):
        """Returns the directed acyclic graph for the survey.
    
        The DAG, or directed acyclic graph, is a dictionary that maps question names to their dependencies.
        It is used to determine the order in which questions should be answered.
        This reflects both agent 'memory' considerations and 'skip' logic.
        The 'textify' parameter is set to True, so that the question names are returned as strings rather than integer indices.
        """
        return self.survey.dag(textify=True)

    @property
    def to_index(self) -> dict:
        "Returns a dictionary mapping question names to their index in the survey."
        return { question_name: index for index, question_name in enumerate(self.survey.question_names)}
    
    @property
    def token_usage(self) -> InterviewTokenUsage:
        "Determins how many tokens were used for the interview."
        cached_tokens = TokenUsage(from_cache=True)
        new_tokens = TokenUsage(from_cache=False)
        for task_creator in self.task_creators.values():
            token_usage = task_creator.token_usage()
            cached_tokens += token_usage["cached_tokens"]
            new_tokens += token_usage["new_tokens"]
        return InterviewTokenUsage(
            new_token_usage=new_tokens, 
            cached_token_usage=cached_tokens
        )

    @property
    def interview_status(self) -> InterviewStatusDictionary:
        """Returns a dictionary mapping task status codes to counts"""
        status_dict = InterviewStatusDictionary()
        for task_creator in self.task_creators.values():
            status_dict[task_creator.task_status] += 1
            status_dict["number_from_cache"] += task_creator.from_cache
        return status_dict

    async def async_conduct_interview(
        self,
        *,
        model_buckets: ModelBuckets = None,
        debug: bool = False,
        replace_missing: bool = True,
    ) -> tuple["Answers", List[dict[str, Any]]]:
        """
        Conducts an interview asynchronously.
        params
        - `model_buckets`: a dictionary of token buckets for the model
        - `debug`: prints debug messages
        - `replace_missing`: if True, replaces missing answers with None
        """
        # if no model bucket is passed, create an 'infinity' bucket with no rate limits
        model_buckets = model_buckets or ModelBuckets.infinity_bucket()

        # we create both tasks and invigilators lists.
        # this is because it's easier to extract info
        # we need from the invigilators list when a task fails.
        # it's challenging to get info from failed asyncio tasks.

        self.tasks, self.invigilators = self._build_question_tasks(
            debug=debug, 
            model_buckets=model_buckets, 
        )

        await asyncio.gather(*self.tasks, return_exceptions=not debug)

        if replace_missing:
            self.answers.replace_missing_answers_with_none(self.survey)

        valid_results = list(self._extract_valid_results())

        return self.answers, valid_results

    def _extract_valid_results(
        self, print_traceback=False
    ) -> Generator["Answers", None, None]:
        """Extracts the valid results from the list of results."""

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
            logger.info(f"Iterating through task: {task}")
            if task.done():
                try:
                    # it worked!
                    result = task.result()
                except asyncio.CancelledError:
                    # task was cancelled
                    logger.info(f"Task `{task.edsl_name}` was cancelled.")
                    result = invigilator.get_failed_task_result()
                except Exception as exception:
                    # any other kind of exception in the task
                    if not warning_printed:
                        warning_printed = True
                        print(warning_header)

                    error_message = f"Task `{task.edsl_name}` failed with `{exception.__class__.__name__}`:`{exception}`."
                    logger.error(error_message)
                    print(error_message)
                    if print_traceback:
                        traceback.print_exc()
                    result = invigilator.get_failed_task_result()
                else:
                    # No exception means the task completed successfully
                    pass

                yield result
            else:
                raise ValueError(f"Task {task.edsl_name} is not done.")
                

    def _build_question_tasks(
        self, 
        debug: bool, 
        model_buckets: ModelBuckets, 
    ) -> Tuple[List[asyncio.Task], List["Invigilators"]]:
        """Creates a task for each question, with dependencies on the questions that must be answered before this one can be answered."""
        logger.info("Creating tasks for each question")
        tasks = []
        invigilators = []
        for question in self.survey.questions:
            # finds dependency tasks for that question
            tasks_that_must_be_completed_before = (
                self._get_tasks_that_must_be_completed_before(tasks, question)
            )
            # creates the task for that question
            question_task = self._create_question_task(
                question=question,
                tasks_that_must_be_completed_before=tasks_that_must_be_completed_before,
                model_buckets=model_buckets,
                debug=debug,
                iteration=self.iteration
            )
            # adds the task to the list of tasks
            tasks.append(question_task)
            invigilators.append(self.get_invigilator(question=question, debug=debug))
        return TasksList(tasks), invigilators

    def _get_tasks_that_must_be_completed_before(
        self, tasks, question
    ) -> List[asyncio.Task]:
        """Returns the tasks that must be completed before the given question can be answered.
        If a question has no dependencies, this will be an empty list, [].
        """
        parents_of_focal_question: List[str] = self.dag.get(question.question_name, [])
        return [
            tasks[self.to_index[parent_question_name]]
            for parent_question_name in parents_of_focal_question
        ]

    def _create_question_task(
        self,
        question: Question,
        tasks_that_must_be_completed_before: List[asyncio.Task],
        model_buckets: ModelBuckets,
        debug: bool,
        iteration:int = 0
    ):
        """Creates a task that depends on the passed-in dependencies that are awaited before the task is run."""
        task_creator = QuestionTaskCreator(
            question=question,
            answer_question_func=self._answer_question_and_record_task,
            token_estimator=self._get_estimated_request_tokens,
            model_buckets=model_buckets,
            iteration = iteration
        )
        [task_creator.add_dependency(x) for x in tasks_that_must_be_completed_before]
        self.task_creators[question.question_name] = task_creator
        return task_creator.generate_task(debug)

    def async_timeout_handler(timeout):
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
        invigilator = self.agent.create_invigilator(
            question=question,
            scenario=self.scenario,
            model=self.model,
            debug=debug,
            memory_plan=self.survey.memory_plan,
            current_answers=self.answers,
            iteration = self.iteration
        )
        return invigilator

    def _get_estimated_request_tokens(self, question) -> float:
        """Estimates the number of tokens that will be required to run the focal task."""
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

    @async_timeout_handler(TIMEOUT)
    async def _answer_question_and_record_task(
        self,
        question: Question,
        debug: bool,
    ) -> AgentResponseDict:
        """Answers a question and records the task.
        This in turn calls the the passed-in agent's async_answer_question method, which returns a response dictionary.
        Note that is updates answers with the response.
        """
        invigilator = self.get_invigilator(question, debug=debug)

        @retry_strategy
        async def attempt_to_answer_question():
            return await invigilator.async_answer_question()

        response: AgentResponseDict = await attempt_to_answer_question()

        # TODO: Move this back into actual agent response dict and enforce it.
        response["question_name"] = question.question_name

        self.answers.add_answer(response, question)

        self._cancel_skipped_questions(question)

        # TODO: This should be forced to be a data-exchange model to cement attributes.
        return AgentResponseDict(**response)

    def _cancel_skipped_questions(self, current_question) -> None:
        """Cancels the tasks for questions that are skipped."""
        logger.info(f"Current question is {current_question.question_name}")
        current_question_index = self.to_index[current_question.question_name]
        next_question = self.survey.rule_collection.next_question(
            q_now=current_question_index, answers=self.answers
        )
        next_question_index = next_question.next_q

        def cancel_between(start, end):
            for i in range(start, end):
                logger.info(
                    f"Cancelling task for question {i}; {self.tasks[i].edsl_name}"
                )
                self.tasks[i].cancel()
                skipped_question_name = self.survey.question_names[i]
                logger.info(f"{skipped_question_name} skipped.")

        if next_question_index == EndOfSurvey:
            cancel_between(current_question_index + 1, len(self.survey.questions))
            return

        if next_question_index > (current_question_index + 1):
            cancel_between(current_question_index + 1, next_question_index)

        self.tasks.status()

    #######################
    # Dunder methods
    #######################
    def __repr__(self) -> str:
        """Returns a string representation of the Interview instance."""
        return f"Interview(agent = {self.agent}, survey = {self.survey}, scenario = {self.scenario}, model = {self.model})"


if __name__ == "__main__":
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
        raise Exception("Fuck you!")
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
