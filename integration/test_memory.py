import random
from edsl.surveys import Survey
from edsl.questions import QuestionMultipleChoice
from edsl.scenarios.ScenarioList import ScenarioList
from edsl.language_models.LanguageModelOpenAIThreeFiveTurbo import (
    LanguageModelOpenAIThreeFiveTurbo,
)

random.seed("agents are cool")

flip_results = [
    {"coin_flip_observed": random.choice(["heads", "tails"])} for _ in range(10)
]
flip_scenarios = ScenarioList.gen(flip_results)

m = LanguageModelOpenAIThreeFiveTurbo(use_cache=False)

q1 = QuestionMultipleChoice(
    question_text="""You just observed a coin flip that had a value {{coin_flip_observed}}. 
    What is the result of the coin flip?""",
    question_options=["heads", "tails"],
    question_name="q1",
)

q2 = QuestionMultipleChoice(
    question_text="In the previous question, what was the result of the coin flip?",
    question_name="q2",
    question_options=["heads", "tails"],
)
s = Survey(questions=[q1, q2])
s.add_targeted_memory(focal_question="q2", prior_question="q1")

results = s.by(flip_scenarios).by(m).run()
results.select("q1", "q2", "scenario.*").print()
