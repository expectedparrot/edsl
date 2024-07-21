import random
from edsl.surveys import Survey
from edsl.data import Cache
from edsl.questions import QuestionMultipleChoice
from edsl.scenarios.ScenarioList import ScenarioList
from edsl import Model

c_memory = Cache()
c_no_memory = Cache()

m = Model()
verbose = False
random.seed("agents are cool")
NUM_FLIPS = 10


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
        If you do not have a memory of the previous question, choose 'I don't know.'""",
        question_name="q2",
        question_options=["heads", "tails", "I don't know"],
    )
    s = Survey(questions=[q1, q2])
    if memory:
        s = s.add_targeted_memory(focal_question="q2", prior_question="q1")
    return s


def test_without_memory():
    s = get_survey(memory=False)
    flip_scenarios = flips(NUM_FLIPS)
    results = s.by(flip_scenarios).by(m).run(cache=c_no_memory)
    if verbose:
        results.select("coin_flip_observed", "q2").print()
    assert all([result == "I don't know" for result in results.select("q2").to_list()])
    c_no_memory.write_jsonl("coin_flip_cache_no_memory.jsonl")


def test_with_memory():
    s = get_survey(memory=True)
    flip_scenarios = flips(NUM_FLIPS)
    results = s.by(flip_scenarios).by(m).run(cache=c_memory).mutate("match = q1 == q2")
    # breakpoint()
    if verbose:
        results.select("q1", "q2", "match").print()
    matches = [result == True for result in results.select("match").to_list()]
    num_matches = sum(matches)
    assert len(matches) == num_matches

    c_memory.write_jsonl("coin_flip_cache_with_memory.jsonl")
