from edsl import QuestionMultipleChoice, QuestionFreeText, Scenario, ScenarioList, Survey

# Sample inputs: no existing labels are needed to run the survey.
records = ScenarioList([
    Scenario({"record_id": "t1", "text": "I was charged twice."}),
    Scenario({"record_id": "t2", "text": "I cannot reset my password."}),
    Scenario({"record_id": "t3", "text": "Please add a dark theme."}),
    Scenario({"record_id": "t4", "text": "The invoice page won't open."}),
])

# Translate the codebook into allowed answers and instructions for using them.
codebook = {
    "Billing": "A charge or payment issue.",
    "Access": "Inability to enter or use a page, including a billing page.",
    "Feature request": "A request for new functionality.",
    "Other": "A request that does not fit any of the categories above.",
}
definitions = "\n".join(f"{label}: {meaning}" for label, meaning in codebook.items())
category = QuestionMultipleChoice(
    question_name="category",
    question_text="What kind of request is this: {{ scenario.text }}?\n" + definitions,
    question_options=list(codebook),
)
evidence = QuestionFreeText(
    question_name="evidence", question_text="Quote the words supporting your code: {{ scenario.text }}",
)
survey = Survey([category, evidence]).add_targeted_memory(evidence, category)
job = survey.by(records)
