from edsl.questions import QuestionYesNo, QuestionFreeText
from edsl import Agent, Survey

agent = Agent(traits={"persona": "audiophile"})

from edsl import Model

m = Model(temperature=1)

q1 = QuestionYesNo(question_name="age", question_text="Are you over 30?")
q2 = QuestionFreeText(
    question_name="analog", question_text="What's the last tape cassette you bought?"
)

survey = Survey([q1, q2]).add_skip_rule(q2, "age == 'No'")

results = survey.by(agent).by(m).run(n=10)

results.select("age", "analog").print(format="rich")
