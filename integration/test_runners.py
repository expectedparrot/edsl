import random
import time

from edsl.surveys import Survey
from edsl.questions import QuestionMultipleChoice
from edsl.scenarios.ScenarioList import ScenarioList
from edsl.language_models import LanguageModelOpenAIThreeFiveTurbo

random.seed("agents are cool")

m = LanguageModelOpenAIThreeFiveTurbo(use_cache=False)

flip_results = [
    {"coin_flip_observed": random.choice(["heads", "tails"])} for _ in range(20)
]
flip_scenarios = ScenarioList.gen(flip_results)

q1 = QuestionMultipleChoice(
    question_text="""You just observed a coin flip that had a value {{coin_flip_observed}}. 
    What is the result of the coin flip?""",
    question_options=["heads", "tails"],
    question_name="q1",
)

start = time.time()
results = q1.by(flip_scenarios).by(m).run(method="serial")
end = time.time()
serial_time = end - start

start = time.time()
results = q1.by(flip_scenarios).by(m).run(method="asyncio")
end = time.time()
async_time = end - start

print(f"Serial time: {serial_time}")
print(f"Async time: {async_time}")
