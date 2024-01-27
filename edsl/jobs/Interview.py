from __future__ import annotations
import asyncio
import logging
import textwrap
from collections import UserDict
from collections import defaultdict

from typing import Any, Type, List, Generator, Callable
from edsl.agents import Agent
from edsl.language_models import LanguageModel
from edsl.questions import Question
from edsl.scenarios import Scenario
from edsl.surveys import Survey
from edsl.utilities.decorators import sync_wrapper
from edsl.data_transfer_models import AgentResponseDict
from edsl.jobs.Answers import Answers
from collections import UserList

from typing import Dict, List


class InterviewError(Exception):
    """Base class for exceptions in this module."""

    pass


class InterviewErrorPriorTaskCanceled(InterviewError):
    """Raised when a prior task was canceled."""

    pass


class InterviewTimeoutError(InterviewError):
    pass


# create logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.propagate = False
# create  file handler
fh = logging.FileHandler("interview.log")
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

from edsl.config import Config

TIMEOUT = int(Config().API_CALL_TIMEOUT_SEC)


class FailedTask(UserDict):
    def __init__(self, e: Exception = None):
        data = {
            "answer": "Failure",
            "comment": "Failure",
            "prompts": {"user_prompt": "", "sytem_prompt": ""},
            "exception": e,
        }
        super().__init__(data)


class QuestionTaskCreator(UserList):
    """Class to create and manage question tasks with dependencies."""

    def __init__(self, func: Callable):
        self.func = func  # the function to be called to actually run the task
        super().__init__([])

    async def _run_task_async(self, question, debug) -> asyncio.Task:
        """Runs the task asynchronously, awaiting the tasks that must be completed before this one can be run."""
        logger.info(f"Running task for {question.question_name}")
        try:
            await asyncio.gather(*self)
        except Exception as e:
            logger.error(f"Required tasks for {question.question_name} failed: {e}")
            # turns the parent exception into a custom exception
            raise InterviewErrorPriorTaskCanceled(
                f"Required tasks failed for {question.question_name}"
            ) from e
        else:
            logger.info(f"Tasks for {question.question_name} completed")
            results = await self.func(question, debug)
            return results

    def __call__(self, question, debug):
        """Creates a task that depends on the passed-in dependencies."""
        task = asyncio.create_task(self._run_task_async(question, debug))
        task.edsl_name = question.question_name
        return task


class Interview:
    """
    A class that has an Agent answer Survey Questions with a particular Scenario and using a LanguageModel.
    """

    def __init__(
        self,
        agent: Agent,
        survey: Survey,
        scenario: Scenario,
        model: Type[LanguageModel],
        verbose: bool = False,
        debug: bool = False,
    ):
        self.agent = agent
        self.survey = survey
        self.scenario = scenario
        self.model = model
        self.debug = debug
        self.verbose = verbose
        self.answers: dict[str, str] = Answers()

        self.dag = self.survey.dag(textify=True)
        self.to_index = {
            name: index for index, name in enumerate(self.survey.question_names)
        }

        logger.info(f"Interview instantiated")

    async def async_conduct_interview(
        self, debug: bool = False, replace_missing: bool = True
    ) -> tuple["Answers", List[dict[str, Any]]]:
        """
        Conducts an 'interview' asynchronously.

        Args:
            debug (bool): Enable debugging mode.
            replace_missing (bool): Replace missing answers with None.
            threaded (bool): Flag to use threading if required.

        Returns:
            Tuple[Answers, List[Dict[str, Any]]]: The answers and a list of valid results.
        """

        tasks = self._build_question_tasks(debug)
        await asyncio.gather(*tasks, return_exceptions=True)

        if replace_missing:
            self.answers.replace_missing_answers_with_none(self.survey)

        valid_results = list(self._extract_valid_results(tasks))

        logger.info(f"Total of tasks requested:\t {len(tasks)}")
        logger.info(f"Number of valid results:\t {len(valid_results)}")
        return self.answers, valid_results

    conduct_interview = sync_wrapper(async_conduct_interview)

    def _extract_valid_results(self, tasks) -> Generator["Answers", None, None]:
        """Extracts the valid results from the list of results."""

        warning_header = textwrap.dedent(
            """\
            WARNING: At least one question in the survey was not answered.
            """
        )
        warning_printed = False
        for task in tasks:
            try:
                result = task.result()
            except Exception as e:
                if not warning_printed:
                    warning_printed = True
                    print(warning_header)
                print(
                    f"""Task `{task.edsl_name}` failed with `{e.__class__.__name__}`:`{e}`."""
                )
            else:
                yield result

    def _build_question_tasks(self, debug) -> Generator[asyncio.Task, None, None]:
        """Creates a task for each question, with dependencies on the questions that must be answered before this one can be answered."""
        logger.info("Creating tasks for each question")
        tasks = []
        for question in self.survey.questions:
            tasks_that_must_be_completed_before = (
                self._get_tasks_that_must_be_completed_before(tasks, question)
            )
            question_task = self._create_question_task(
                question, tasks_that_must_be_completed_before, debug
            )
            tasks.append(question_task)
        return tasks

    def _get_tasks_that_must_be_completed_before(
        self, tasks, question
    ) -> List[asyncio.Task]:
        """Returns the tasks that must be completed before the given question can be answered.
        If a question has no dependencies, this will be an empty list, [].
        """
        parents_of_focal_question = self.dag.get(question.question_name, [])
        return [
            tasks[self.to_index[parent_question_name]]
            for parent_question_name in parents_of_focal_question
        ]

    def _create_question_task(
        self,
        question: Question,
        tasks_that_must_be_completed_before: List[asyncio.Task],
        debug,
    ):
        """Creates a task that depends on the passed-in dependencies that are awaited before the task is run.
        The key awaitable is the `run_task` function, which is a wrapper around the `answer_question_and_record_task` method.
        """
        create_task = QuestionTaskCreator(func=self._answer_question_and_record_task)
        for dependency in tasks_that_must_be_completed_before:
            create_task.append(dependency)
        return create_task(question, debug)

    def async_timeout_handler(timeout):
        def decorator(func):
            async def wrapper(*args, **kwargs):
                try:
                    return await asyncio.wait_for(func(*args, **kwargs), timeout)
                except asyncio.TimeoutError:
                    raise InterviewTimeoutError(
                        f"Task timed out after {timeout} seconds."
                    )
                    # question = args[1]  # Assuming the first argument is the question
                    # task_name = getattr(question, "question_name", "unknown")
                    # print(f"Task {task_name} timed out after {timeout} seconds.")
                    # logger.error(f"Task {task_name} timed out")
                    # return None

            return wrapper

        return decorator

    @async_timeout_handler(TIMEOUT)
    async def _answer_question_and_record_task(
        self, question, debug
    ) -> AgentResponseDict:
        """Answers a question and records the task.
        This in turn calls the the passed-in agent's async_answer_question method, which returns a response dictionary.
        """
        response: AgentResponseDict = await self.agent.async_answer_question(
            question=question,
            scenario=self.scenario,
            model=self.model,
            debug=debug,
            memory_plan=self.survey.memory_plan,
            current_answers=self.answers,
        )
        self.answers.add_answer(response, question)
        return response

    #######################
    # Dunder methods
    #######################
    def __repr__(self) -> str:
        """Returns a string representation of the Interview instance."""
        return f"Interview(agent = {self.agent}, survey = {self.survey}, scenario = {self.scenario}, model = {self.model})"


def main():
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
    scenario = Scenario()
    m = LanguageModelOpenAIThreeFiveTurbo(use_cache=True)
    I = Interview(agent=a, survey=s, scenario=scenario, model=m)

    # # conduct five interviews
    # for _ in range(5):
    #     I.conduct_interview(debug=True)

    # # replace missing answers
    # I
    # repr(I)
    # eval(repr(I))


if __name__ == "__main__":
    main()
