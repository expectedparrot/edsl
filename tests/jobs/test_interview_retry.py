import pytest
import asyncio

from edsl.agents import Agent
from edsl.jobs.Jobs import Jobs
from edsl.questions.QuestionFreeText import QuestionFreeText
from edsl.surveys.Survey import Survey
from edsl.scenarios import Scenario
from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice
from edsl.jobs.interviews.Interview import Interview


def test_retry():
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

    def service_that_fails_set_times(num_fails):
        "Closure that generates a function that fails num_fails times before succeeding."
        counter = 0

        def service_that_fails(self, question, scenario):
            if counter < num_fails:
                raise Exception("Failed!")
            else:
                return "yes"

        return service_that_fails

    direct_question_answering_method = service_that_fails_set_times(2)

    a.add_direct_question_answering_method(direct_question_answering_method)
    scenario = Scenario()
    from edsl.language_models.model import Model

    m = Model()
    I = Interview(agent=a, survey=s, scenario=scenario, model=m)

    result = asyncio.run(I.async_conduct_interview())
