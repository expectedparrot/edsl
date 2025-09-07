from edsl import Scenario, ScenarioList, QuestionFreeText

s = ScenarioList([Scenario({"activity":"taking a nap"})])

q = QuestionFreeText(
    question_name = "favorite_place_{{ scenario.activity }}", # optional use of scenario key
    question_text = "In a brief sentence, describe your favorite place for {{ scenario.activity }}."
)

questions = q.loop(s)