from __future__ import annotations
import asyncio
import logging
from typing import Any, Type, List
from edsl.agents import Agent
from edsl.language_models import LanguageModel
from edsl.questions import Question
from edsl.scenarios import Scenario
from edsl.surveys import Survey
from edsl.utilities.decorators import sync_wrapper
from edsl.config import Config
from edsl.data_transfer_models import AgentResponseDict
from edsl.jobs.Answers import Answers


TIMEOUT = int(Config().API_CALL_TIMEOUT_SEC)

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


def async_timeout_handler(timeout):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                # Call the original function, which is now responsible only for getting the response
                return await asyncio.wait_for(func(*args, **kwargs), timeout)
            except asyncio.TimeoutError:
                question = args[0]  # Assuming the first argument is the question
                print(
                    f"Task {question.question_name} timed out after {timeout} seconds."
                )
                logger.error(f"Task {question.question_name }timed out")
                return None

        return wrapper

    return decorator


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

        logger.info(f"Interview instantiated")

    async def async_conduct_interview(
        self, debug: bool = False, replace_missing: bool = True, threaded: bool = False
    ) -> tuple["Answers", List[dict[str, Any]]]:
        "Conducts an 'interview' asynchronously."

        # creates awaitable asyncio tasks for each question, with
        # dependencies on the questions that must be answered before
        # this one can be answered.
        tasks = self._build_question_tasks(self.questions, self.dag, debug)
        await asyncio.gather(*tasks, return_exceptions=True)

        if replace_missing:
            self.answers.replace_missing_answers_with_none(self.survey)

        results = [task.result() for task in tasks]

        for i, result in enumerate(results):
            if "exception" in result.keys():
                exception = result["exception"]
                print(
                    f"Task {i} out of {len(results)} failed with exception {repr(exception)}"
                )

        return self.answers, results

    conduct_interview = sync_wrapper(async_conduct_interview)

    @property
    def questions(self):
        "Returns the questions in the survey."
        return self.survey.questions

    @property
    def to_index(self):
        "Returns a dictionary mapping question names to their indices in the survey."
        return {name: index for index, name in enumerate(self.survey.question_names)}

    @property
    def dag(self, texify=True):
        """Returns the DAG of the survey, which reflects both skip-logic and memory.
        texify: if True, returns the DAG with the question names, otherwise, indices.
        """
        return self.survey.dag(textify=texify)

    def _build_question_tasks(self, questions, dag, debug) -> List[asyncio.Task]:
        """Creates a task for each question, with dependencies on the questions that must be answered before this one can be answered."""
        logger.info("Creating tasks for each question")
        tasks = []
        for question in questions:
            logger.info(f"Now working on: {question.question_name}")
            dependencies = self._get_question_dependencies(tasks, question, dag)
            logger.info(f"Dependencies for {question.question_name}: {dependencies}")
            question_task = self._create_question_task(question, dependencies, debug)
            tasks.append(question_task)
        return tasks

    def _get_question_dependencies(self, tasks, question, dag) -> List[asyncio.Task]:
        """Returns the tasks that must be completed before the given question can be answered.
        If a question has no dependencies, this will be an empty list, [].
        """
        return [
            tasks[self.to_index[question_name]]
            for question_name in dag.get(question.question_name, [])
        ]

    def _get_question_dependent_children(
        self, tasks, question, dag
    ) -> List[asyncio.Task]:
        """Returns the tasks that must be completed before the given question can be answered.
        If a question has no dependencies, this will be an empty list, [].
        """
        pass

    def _create_question_task(
        self,
        question: Question,
        questions_that_must_be_answered_before: List[asyncio.Task],
        debug,
    ):
        """Creates a task that depends on the passed-in dependencies that are awaited before the task is run.
        The key awaitable is the `run_task` function, which is a wrapper around the `answer_question_and_record_task` method.
        """

        async def run_task() -> asyncio.Task:
            logger.info(f"Running task for {question.question_name}")
            await asyncio.gather(*questions_that_must_be_answered_before)
            logger.info(f"Tasks for {question.question_name} completed")
            return await self.answer_question_and_record_task(question, debug)

        return asyncio.create_task(run_task())

    def _update_answers(self, response, question) -> None:
        """Updates the answers dictionary with the response to a question."""
        self.answers.add_answer(response, question)

    @async_timeout_handler(TIMEOUT)
    async def answer_question_and_record_task(
        self, question, debug
    ) -> AgentResponseDict:
        """Answers a question and records the task.
        This in turn calls the the passed-in agent's async_answer_question method, which returns a response dictionary.
        """
        try:
            response: AgentResponseDict = await self.agent.async_answer_question(
                question=question,
                scenario=self.scenario,
                model=self.model,
                debug=debug,
                memory_plan=self.survey.memory_plan,
                current_answers=self.answers,
            )
            self._update_answers(response, question)
        except Exception as e:
            # logger.error(f"Error in answer_question_and_record_task: {e}")
            ## We do *not* raise the exception here, because we want to continue with the interview
            ## even if one question fails.But we should cancel all tasks that depend on this one.
            logger.exception("Error in answer_question_and_record_task")

            from collections import UserDict

            class FailedTask(UserDict):
                def __init__(self):
                    data = {
                        "answer": "Failure",
                        "comment": "Failure",
                        "prompts": {"user_prompt": "", "sytem_prompt": ""},
                        "exception": e,
                    }
                    super().__init__(data)

            response = FailedTask()

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
