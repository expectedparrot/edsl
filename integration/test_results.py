#from edsl.language_models import LanguageModelOpenAIFour
from edsl.questions import QuestionMultipleChoice, QuestionList
from edsl.surveys import Survey
from edsl import Model

#m = LanguageModelOpenAIFour()
m = Model()

q1 = QuestionList(
    question_text="Please return a list of 10 fast food restaurants",
    question_name="fast_food",
    max_list_items=10,
)
q2 = QuestionMultipleChoice(
    question_text="Do you each chicken?",
    question_options=["yes", "no"],
    question_name="chicken",
)
s = Survey(questions=[q1, q2])
foods = s.by(m).run()

foods.select("answer.*").print()
foods.select("prompt.*").print()

# q = QuestionMultipleChoice(question="What is the capital of France?", answer="Paris")
# m = LanguageModelOpenAIFour()
