from __future__ import annotations
import asyncio

# from tenacity import retry, wait_exponential, stop_after_attempt
from typing import Any, Type, Union
from edsl.agents import Agent
from edsl.language_models import LanguageModel
from edsl.questions import Question
from edsl.scenarios import Scenario
from edsl.surveys import Survey
from edsl.utilities.decorators import sync_wrapper

from edsl.jobs.Answers import Answers

from edsl.config import Config

TIMEOUT = int(Config().API_CALL_TIMEOUT_SEC)


def task_wrapper(name, delay, dependencies=[]):
    async def run_task():
        for dependency in dependencies:
            await dependency
        return await task(name, delay)

    # Using create_task instead of ensure_future
    return asyncio.create_task(run_task())


# async def task_with_timeout(task_number, duration, timeout):
#     try:
#         await asyncio.wait_for(asyncio.sleep(duration), timeout)
#         print(f"Task {task_number} completed.")
#     except asyncio.TimeoutError:
#         print(f"Task {task_number} timed out after {timeout} seconds.")


class ChaosMonkeyException(Exception):
    pass


def chaos_monkey(p):
    import random

    if random.random() < p:
        raise ChaosMonkeyException("Chaos monkey!")


class Interview:
    """
    A class that has an Agent answer Survey Questions with a particular Scenario and using a LanguageModel.
    - `Agent.answer_question(question, scenario, model)` is called for each question in the Survey to get an answer to a question.
    - `Survey.gen_path_through_survey()` is called to get a generator that traverses through the Survey.
    - `conduct_interview()` is called to conduct the interview, and returns the answers and comments to the questions in the Survey.
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
    ) -> "Answers":
        """ """
        to_index = {
            name: index for index, name in enumerate(self.survey.question_names)
        }

        async def task(question):
            try:
                chaos_monkey(0.0)
                response = await asyncio.wait_for(
                    self.async_get_response(question, debug=debug), TIMEOUT
                )
                self.answers.add_answer(response, question)
            except asyncio.TimeoutError:
                print(
                    f"Task {question.question_name} timed out after {TIMEOUT} seconds."
                )
                response = None
            except ChaosMonkeyException as e:
                print(f"Task {question.question_name} failed with {e}")
                response = None
            # response = await self.async_get_response(question, debug=debug)

            return response

        def task_wrapper(question, dependencies=[]):
            async def run_task():
                for dependency in dependencies:
                    await dependency  # awaits all the tasks (questions) this question depends on
                return await task(
                    question
                )  # awaits the task (question) itself once dependencies are done

            return asyncio.create_task(run_task())

        dag = self.survey.dag(textify=True)  # gets the combined memory & skip logic DAG

        # tasks = {}
        # async with asyncio.TaskGroup() as tg:
        #     for question in self.survey.questions:
        #         dependencies = [
        #             tasks[question_name]
        #             for question_name in dag.get(question.question_name, [])
        #         ]
        #         tasks[question.question_name] = tg.create_task(
        #             task_wrapper(question, dependencies)
        #         )

        tasks = []
        for question in self.survey.questions:
            dependencies = [
                tasks[to_index[question_name]]
                for question_name in dag.get(question.question_name, [])
            ]  # Note: if a question has no dependencies, this will be an empty list, []
            tasks.append(task_wrapper(question, dependencies=dependencies))

        await asyncio.gather(*tasks)

        if replace_missing:
            self.answers.replace_missing_answers_with_none(self.survey)

        return self.answers

    conduct_interview = sync_wrapper(async_conduct_interview)

    async def async_get_response(
        self, question: Question, debug: bool = False
    ) -> dict[str, Any]:
        """Gets the agent's response to a question with exponential backoff.

        This calls the agent's `answer_question` method, which returns a response dictionary.
        """
        response = await self.agent.async_answer_question(
            question=question,
            scenario=self.scenario,
            model=self.model,
            debug=debug,
            memory_plan=self.survey.memory_plan,
            current_answers=self.answers,
        )
        return response

    get_response = sync_wrapper(async_get_response)

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
