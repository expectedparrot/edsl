from edsl import Agent, AgentList, QuestionMultipleChoice, Scenario, ScenarioList

agents = AgentList([
    Agent(traits={"instruction_id": "literal"}, instruction="Classify only explicit statements."),
    Agent(traits={"instruction_id": "inference"}, instruction="Classify the likely intent of the writer."),
])
records = ScenarioList([
    Scenario({"record_id": "r1", "text": "Great, another unexpected charge."}),
    Scenario({"record_id": "r2", "text": "The receipt arrived today."}),
])
question = QuestionMultipleChoice(
    question_name="sentiment", question_text="Classify: {{ scenario.text }}",
    question_options=["Positive", "Neutral", "Negative"],
)
job = question.by(agents).by(records)
