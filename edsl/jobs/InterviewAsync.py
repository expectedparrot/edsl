from __future__ import annotations
import asyncio

# from tenacity import retry, wait_exponential, stop_after_attempt
from typing import Any, Type, Union, List
from edsl.agents import Agent
from edsl.language_models import LanguageModel
from edsl.questions import Question
from edsl.scenarios import Scenario
from edsl.surveys import Survey
from edsl.utilities.decorators import sync_wrapper

from edsl.jobs.Answers import Answers

from edsl.config import Config

TIMEOUT = int(Config().API_CALL_TIMEOUT_SEC)


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

    async def async_conduct_interview(
        self, debug: bool = False, replace_missing: bool = True, threaded: bool = False
    ) -> tuple["Answers", List[dict[str, Any]]]:
        "Conducts an 'interview' asynchronously."

        # creates awaitable asyncio tasks for each question, with
        # dependencies on the questions that must be answered before
        # this one can be answered.
        tasks = self._build_question_tasks(self.questions, self.dag, debug)
        await asyncio.gather(*tasks)

        if replace_missing:
            self.answers.replace_missing_answers_with_none(self.survey)

        results = [task.result() for task in tasks]
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
        tasks = []
        for question in questions:
            dependencies = self._get_question_dependencies(tasks, question, dag)
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
            await asyncio.gather(*questions_that_must_be_answered_before)
            return await self.answer_question_and_record_task(question, debug)

        return asyncio.create_task(run_task())

    def _update_answers(self, response, question):
        """Updates the answers dictionary with the response to a question."""
        self.answers.add_answer(response, question)

    @async_timeout_handler(TIMEOUT)
    async def answer_question_and_record_task(self, question, debug):
        """Answers a question and records the task.
        This in turn calls the the passed-in agent's async_answer_question method, which returns a response dictionary.
        """
        # response = await self.async_agent_answers_single_question(question)

        response = await self.agent.async_answer_question(
            question=question,
            scenario=self.scenario,
            model=self.model,
            debug=debug,
            memory_plan=self.survey.memory_plan,
            current_answers=self.answers,
        )
        self._update_answers(response, question)
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

    # conduct five interviews
    for _ in range(5):
        I.conduct_interview(debug=True)

    # replace missing answers
    I
    repr(I)
    eval(repr(I))
