from edsl import QuestionMultipleChoice, QuestionFreeText, Scenario, ScenarioList, Survey

variants = ScenarioList([
    Scenario({"variant": "vague", "item": "Do you use this service regularly?"}),
    Scenario({"variant": "bounded", "item": "On how many of the past 7 days did you use this service?"}),
])
issue = QuestionMultipleChoice(
    question_name="issue",
    question_text="Review this survey item: {{ scenario.item }}. What is its main issue?",
    question_options=["Ambiguous timeframe", "Double-barreled", "Leading", "None identified"],
)
revision = QuestionFreeText(
    question_name="revision",
    question_text="Suggest a revision and explain what it measures: {{ scenario.item }}",
)
survey = Survey([issue, revision]).add_targeted_memory(revision, issue)
job = survey.by(variants)
