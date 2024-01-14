import random
from edsl.surveys import Survey
from edsl.questions import QuestionMultipleChoice
from edsl.scenarios.ScenarioList import ScenarioList
from edsl.language_models.LanguageModelOpenAIThreeFiveTurbo import (
    LanguageModelOpenAIThreeFiveTurbo,
)

NUM_FLIPS = 5
m = LanguageModelOpenAIThreeFiveTurbo(use_cache=False)

verbose = False

random.seed("agents are cool")


def flips(n):
    flip_results = [
        {"coin_flip_observed": random.choice(["heads", "tails"])} for _ in range(n)
    ]
    flip_scenarios = ScenarioList.gen(flip_results)
    return flip_scenarios


def get_survey(memory):
    q1 = QuestionMultipleChoice(
        question_text="""You just observed a coin flip that had a value {{coin_flip_observed}}. 
        What is the result of the coin flip?""",
        question_options=["heads", "tails"],
        question_name="q1",
    )

    q2 = QuestionMultipleChoice(
        question_text="""In the previous question, what was the result of the coin flip? 
        If you do have a memory of the previous question, choose 'I don't know.'""",
        question_name="q2",
        question_options=["heads", "tails", "I don't know"],
    )
    s = Survey(questions=[q1, q2])
    if memory:
        s.add_targeted_memory(focal_question="q2", prior_question="q1")
    return s


def test_without_memory():
    s = get_survey(memory=False)
    flip_scenarios = flips(NUM_FLIPS)
    results = s.by(flip_scenarios).by(m).run()
    if verbose:
        results.select("coin_flip_observed", "q2").print()
    assert all([result == "I don't know" for result in results.select("q2").to_list()])


def test_with_memory():
    s = get_survey(memory=True)
    flip_scenarios = flips(NUM_FLIPS)
    results = s.by(flip_scenarios).by(m).run().mutate("match = q1 == q2")
    if verbose:
        results.select("q1", "q2", "match").print()
    assert all([result == True for result in results.select("match").to_list()])
