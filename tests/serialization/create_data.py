import os
import json
from edsl.questions import *
from edsl import Scenario, Survey, Agent, Model
from edsl import __version__ as edsl_version

# Base directory for the script
base_dir = os.path.dirname(os.path.abspath(__file__))

all_question_types = [
    QuestionBudget,
    QuestionCheckBox,
    QuestionExtract,
    QuestionFreeText,
    QuestionList,
    QuestionMultipleChoice,
    QuestionNumerical,
    QuestionRank,
    QuestionLikertFive,
    QuestionLinearScale,
    QuestionTopK,
    QuestionYesNo
]

questions = [q.example() for q in all_question_types]
survey = Survey(questions=questions)

# Create personas for AI agents
personas = ["You are an athlete", "You are a student", "You are a chef"]
agents = [Agent(traits={"persona": p}) for p in personas]

# Select language models
models = [Model("gpt-3.5-turbo"), Model("gpt-4-1106-preview")]

# Run the survey with agents, and models
results = survey.by(agents).by(models).run()

# Prepare data and path for serialization
data = results.to_dict()
dir_path = os.path.join(base_dir, f"data/{edsl_version}/")

if not os.path.exists(dir_path):
    os.makedirs(dir_path)
file_path = os.path.join(dir_path, "data.json")

# Write data to the file
with open(file_path, "w") as f:
    json.dump(data, f)
