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


class Interview:
    """
    A class that has an Agent answer Survey Questions with a particular Scenario and using a LanguageModel.
    - `Agent.answer_question(question, scenario, model)` is called for each question in the Survey to get an answer to a question.
    - `Survey.gen_path_through_survey()` is called to get a generator that     async def async_conduct_interview(
        self, debug: bool = False, replace_missing: bool = True, threaded: bool = False
    ) -> "Answers":
        """ """
        to_index = {
            name: index for index, name in enumerate(self.survey.question_names)
        }

        async def task(question):
            try:
                response = await asyncio.wait_for(
                    self.async_get_response(question, debug=debug), TIMEOUT
                )
                self.answers.add_answer(response, question)
            except asyncio.TimeoutError:
                print(
                    f"Task {question.question_name} timed out after {TIMEOUT} seconds."
                )
                response = None

            return response

        def task_wrapper(question, dependencies=[]):
            async def run_task():
                for dependency in dependencies:
                    await dependency  # awaits all the tasks (questions) this question depends on
                return await task(question)  
            return asyncio.create_task(run_task())

        dag = self.survey.dag(textify=True)  # gets the combined memory & skip logic DAG

        tasks = []
        for question in self.survey.questions:
            dependencies = [
                tasks[to_index[question_name]]
                for question_name in dag.get(question.question_name, [])
            ]  # Note: if a question has no dependencies, this will be an empty list, []
            tasks.append(task_wrapper(question, dependencies=dependencies))
traverses through the Survey.
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
        "Conducts an interview asynchronously."

        @self.async_timeout_handler(TIMEOUT)
        async def task(question):
            response = await self.async_agent_answers_single_question(question)
            self._update_answers(response, question)
            return response

        to_index = {
            name: index for index, name in enumerate(self.survey.question_names)
        }

        def create_question_task(
            question: Question,
            questions_that_must_be_answered_before: List[asyncio.Task],
        ):
            """This creates a task that depends on the passed-in dependencies.

            The dependencies are awaited before the task is run.
            """

            async def run_task() -> asyncio.Task:
                await asyncio.gather(*questions_that_must_be_answered_before)
                return await task(question)

            return asyncio.create_task(run_task())

        def get_question_dependencies(question, dag) -> List[asyncio.Task]:
            return [
                tasks[to_index[question_name]]
                for question_name in dag.get(question.question_name, [])
            ]

        dag = self.survey.dag(textify=True)  # gets the combined memory & skip logic DAG

        tasks = []
        for question in self.survey.questions:
            focal_question_dependencies = get_question_dependencies(question, dag)
            question_task = create_question_task(question, focal_question_dependencies)
            tasks.append(question_task)

        await asyncio.gather(*tasks)

        if replace_missing:
            self.answers.replace_missing_answers_with_none(self.survey)

        results = [task.result() for task in tasks]
        return self.answers, results

    conduct_interview = sync_wrapper(async_conduct_interview)

    @staticmethod
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

    def _update_answers(self, response, question):
        """Updates the answers dictionary with the response to a question."""
        self.answers.add_answer(response, question)

    async def async_agent_answers_single_question(
        self, question: Question, debug: bool = False
    ) -> dict[str, Any]:
        """Gets the agent's response to a question with exponential backoff.

        This calls the agent's `answer_question` method, which returns a response dictionary.
        """
        response = await self.agent.async_answer_question(
            question=question,
            scenario=self.scenario,
            model=self.model,
            debug=False,
            memory_plan=self.survey.memory_plan,
            current_answers=self.answers,
        )
        return response

    get_response = sync_wrapper(async_agent_answers_single_question)

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
