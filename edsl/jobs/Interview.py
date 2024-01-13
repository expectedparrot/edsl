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

from collections import UserDict


class Answers(UserDict):
    "Helper class to hold the answers to a survey"

    def add_answer(self, response, question) -> None:
        "Adds a response to the answers dictionary"
        answer = response.get("answer")
        comment = response.pop("comment", None)
        # record the answer
        self[question.question_name] = answer
        if comment:
            self[question.question_name + "_comment"] = comment

    def replace_missing_answers_with_none(self, survey) -> None:
        "Replaces missing answers with None. Answers can be missing if the agent skips a question."
        for question_name in survey.question_names:
            if question_name not in self:
                self[question_name] = None


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
        """
        Conducts the interview using a generator from the Survey object to traverse through the survey. Sends answers to the Survey, which then sends back the next Question.

        Arguments:
        - `debug`: if True, the agent simulates answers without API calls
        - `replace_missing`: if True, missing answers are imputed with None.

        Returns:
        - `answers`: a dictionary of answers to the survey questions, with keys as question names and values as answers. If the agent also produced a comment, the comment is stored in a key with the question name plus "_comment" appended to it.
        """
        path_through_survey = self.survey.gen_path_through_survey()
        question = next(path_through_survey)

        def get_next_question(answers) -> Union["Question", None]:
            """Gets the next question from the survey by sending the current answers.
            If the survey is finished, the generator returns at StopIteration, in which case
            this returns None, which will end the while-loop."""
            try:
                return path_through_survey.send(answers)
            except StopIteration:
                return None

        while question:
            response = await self.async_get_response(question, debug=debug)
            self.answers.add_answer(response, question)
            question = get_next_question(self.answers)

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
    from edsl.jobs.Interview import Interview

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
