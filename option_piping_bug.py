from edsl import Agent, AgentList
from edsl.language_models import LanguageModel

# Create agents with names to identify them in the scripted responses
a1 = Agent(name="botanist", traits={"persona": "botanist who picks really weird colors"})
a2 = Agent(name="economist", traits={"persona": "economist"})
agents = AgentList([a1, a2])

# Create scripted responses for the two agents
scripted_responses = {
    'botanist': {
        'q1': ['moss green', 'rust red', 'deep purple', 'ocean teal'],
        'q2': 'moss green'
    },
    'economist': {
        'q1': ["market green", "bull gold", "bear red", "neutral blue"],
        'q2': 'bear red'
    }
}

# Create the scripted response model
model = LanguageModel.from_scripted_responses(scripted_responses)

from edsl import QuestionList, QuestionMultipleChoice, Survey

q1 = QuestionList(
    question_name="q1",
    question_text="What colors do you like?",
    min_list_items=3,
    max_list_items=5,
)

# We can pipe an answer into a follow-on question in the same survey:
q2 = QuestionMultipleChoice(
    question_name="q2",
    question_text="Which color is your favorite?",
    question_options="{{ q1.answer }}",
)

survey = Survey(questions=[q1, q2])

results = survey.by(agents).by(model).run(n = 1, disable_remote_inference = True, 
                                          refresh = True, 
                                          fresh = True, 
                                          cache = False, 
                                          stop_on_exceptions = True)

print(results.select("persona", "q1", "q2_question_options", 'q2').table())



