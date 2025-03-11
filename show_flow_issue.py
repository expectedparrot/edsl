from edsl import Scenario, Survey
from edsl import QuestionFreeText



q1 = QuestionFreeText(
    question_name="q1",
    question_text = "What is your age, {{ scenario.name }}?"
    )
survey = Survey([q1])
#survey.show_flow()

scenario = Scenario({'name':"Steve"})


survey.by(scenario).show_flow()

