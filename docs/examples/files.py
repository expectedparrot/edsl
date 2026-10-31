import csv
from pathlib import Path
from edsl import FileStore, Scenario, ScenarioList, QuestionMultipleChoice

path = Path("feedback.csv")
with path.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=["record_id", "feedback"])
    writer.writeheader()
    writer.writerows([
        {"record_id": "f1", "feedback": "The setup was easy."},
        {"record_id": "f2", "feedback": "The export button is missing."},
    ])
file = FileStore(str(path))
# A CSV row becomes one scenario, retaining its record_id.
rows = ScenarioList.from_source("csv", str(path))
question = QuestionMultipleChoice(
    question_name="sentiment",
    question_text="Classify this feedback: {{ scenario.feedback }}",
    question_options=["Positive", "Neutral", "Negative"],
)
job = question.by(rows)
# A whole file can instead be attached under a scenario key for a compatible model.
attachment = Scenario({"document": file})
