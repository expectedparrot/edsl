from edsl import QuestionMultipleChoice, Scenario, ScenarioList, Survey

question = QuestionMultipleChoice(
    question_name="sentiment",
    question_text="Classify the sentiment of this feedback: {{ scenario.feedback }}",
    question_options=["Positive", "Neutral", "Negative"],
)
feedback = ScenarioList([
    Scenario({"record_id": "f1", "feedback": "The setup was easy."}),
    Scenario({"record_id": "f2", "feedback": "I couldn't find the export button."}),
    Scenario({"record_id": "f3", "feedback": "It worked as expected."}),
])
job = question.by(feedback)
# by(): one interview per input, with the same answer.sentiment column.
# loop(): three distinct questions in one survey, with the text substituted now.
variants = question.loop(feedback)
variant_survey = Survey(variants)
