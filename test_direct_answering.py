from edsl.agents import Agent

a = Agent()
a.add_canned_response("q1", "foo")
# def f(self, question, scenario):
#         if question.question_name == "q1":
#             return "foo"
#         else:
#             return "bar"
#a.add_direct_question_answering_method(f)
from edsl import QuestionFreeText 
q = QuestionFreeText(question_text="What is your name?", question_name="q1")
results = q.by(a).run(disable_remote_inference=True)
print(results.select("answer.*"))
