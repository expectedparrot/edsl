import random
import time
from edsl.questions import QuestionMultipleChoice
from edsl.scenarios.ScenarioList import ScenarioList
from edsl import Model
from edsl.caching import Cache

serial_time = 1000
async_time = 1000
verbose = False


def get_job():
    NUM_FLIPS = 5
    random.seed("agents are cool")

    m = Model()

    flip_results = [
        {"coin_flip_observed": random.choice(["heads", "tails"])}
        for _ in range(NUM_FLIPS)
    ]
    flip_scenarios = ScenarioList.gen(flip_results)

    q1 = QuestionMultipleChoice(
        question_text="""You just observed a coin flip that had a value {{coin_flip_observed}}. 
        What is the result of the coin flip?""",
        question_options=["heads", "tails"],
        question_name="q1",
    )
    return q1.by(flip_scenarios).by(m)


def test_async():
    global async_time
    job = get_job()
    c = Cache()
    start = time.time()
    results = job.run(cache=c)
    end = time.time()
    async_time = end - start
    if verbose:
        print(f"Async time: {async_time}")
