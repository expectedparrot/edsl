import random
import time

from edsl.surveys import Survey
from edsl.questions import QuestionMultipleChoice
from edsl.scenarios.ScenarioList import ScenarioList
from edsl.language_models import LanguageModelOpenAIThreeFiveTurbo

serial_time = 1000
async_time = 1000

verbose = False


def get_job():
    NUM_FLIPS = 5
    random.seed("agents are cool")

    m = LanguageModelOpenAIThreeFiveTurbo(use_cache=False)

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


def test_serial():
    global serial_time
    job = get_job()
    start = time.time()
    results = job.run(method="serial")
    end = time.time()
    serial_time = end - start
    if verbose:
        print(f"Serial time: {serial_time}")


def test_async():
    global async_time
    job = get_job()
    start = time.time()
    results = job.run(method="asyncio")
    end = time.time()
    async_time = end - start
    if verbose:
        print(f"Async time: {async_time}")


def test_compare():
    global serial_time, async_time
    print(f"Serial time: {serial_time}")
    print(f"Async time: {async_time}")
    assert async_time < serial_time
