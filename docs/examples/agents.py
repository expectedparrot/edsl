from edsl import Agent, AgentList, QuestionMultipleChoice, Scenario, ScenarioList

agents = AgentList([
    Agent(traits={"experience": experience, "role": role},
          instruction="Answer using only the supplied profile and message.")
    for experience in ["new user", "experienced user"]
    for role in ["individual contributor", "team lead"]
])
messages = ScenarioList([
    Scenario({"condition": "short", "message": "Export your report."}),
    Scenario({"condition": "explicit", "message": "Download your report as a CSV file."}),
])
question = QuestionMultipleChoice(
    question_name="clarity",
    question_text="How clear is this instruction: {{ scenario.message }}?",
    question_options=["Clear", "Unclear", "Unsure"],
)
job = question.by(agents).by(messages)
# Four profiles crossed with two messages gives eight interviews per model.
