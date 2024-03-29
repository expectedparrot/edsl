from edsl.questions import QuestionFreeText
from edsl import Agent

def test_multiple_runs():
    
    a = Agent(traits = {})

    a.add_direct_question_answering_method(lambda self, question, scenario: "yes")

    q = QuestionFreeText.example()
    results = q.by(a).run(n = 2)
    assert len(results) == 2