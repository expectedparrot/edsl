from edsl import QuestionFreeText 
from edsl.prompts import Prompt
from edsl import Model
from edsl.data import Cache

from edsl import QuestionFreeText 

m = Model('gemini_pro')
m.hello()

from edsl.data import Cache 

results = QuestionFreeText.example().by(m).run(cache = Cache())

results_with_sidecar = QuestionFreeText.example().by(m).run(cache = Cache(), sidecar_model = Model())


# from edsl.agents.Invigilator import InvigilatorSidecar
# from edsl.questions import QuestionFreeText
# from edsl import QuestionMultipleChoice

# from edsl import Agent
# a = Agent()

# i = InvigilatorSidecar(
#     agent=a,
#     question=QuestionMultipleChoice.example(),
#     scenario={},
#     model= Model(),
#     cache = Cache(),
#     memory_plan=None,
#     current_answers=None,
# )

# result = i.answer_question()

# simple_model = Model()
# advanced_model = Model()

# question = QuestionFreeText.example()
# human_readable_question = question.human_readable()
# raw_simple_response = simple_model.execute_model_call(user_prompt = human_readable_question, 
#         system_prompt = "Pretend you are a human answering questions. Do not break character. You had a bad day")
# simple_response = simple_model.parse_response(raw_simple_response)
# instructions = question.get_instructions()

# main_model_prompt = Prompt(text = """
# A simpler language model was asked this question: 

# To the simpel model:
# {{ human_readable_question }}

# The simple model responded:
# <response>
# {{ simple_response }}
# </response>

# It was suppose to respond according to these instructions:                                                      
# <instructions>
# {{ instructions }}
# </instructions>
                           
# Please format the simple model's response as it should have been formmated, given the instructions.
# Only respond in valid JSON, like so {"answer": "SPAM!"} or {"answer": "SPAM!", "comment": "I am a robot."}
# Do not inlcude the word 'json'
# """)
# d = {'human_readable_question': human_readable_question, 'simple_response': simple_response, 'instructions': instructions}

# final = advanced_model.execute_model_call(
#     user_prompt = main_model_prompt.render(d).text, 
#     system_prompt = "You are a helpful assistant.")







