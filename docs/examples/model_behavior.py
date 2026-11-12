from edsl import QuestionMultipleChoice, Scenario, ScenarioList

cases = ScenarioList([
    Scenario({"case_id": "a", "context": "An individual has one export left.",
              "message": "Exporting now uses the last export."}),
    Scenario({"case_id": "b", "context": "A team has one export left.",
              "message": "Exporting now uses the last export."}),
])
question = QuestionMultipleChoice(
    question_name="choice",
    question_text="{{ scenario.context }} {{ scenario.message }} What would you choose?",
    question_options=["Export now", "Wait", "Need more information"],
)
job = question.by(cases)
