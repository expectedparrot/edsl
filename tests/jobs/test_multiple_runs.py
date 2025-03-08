from edsl.questions.QuestionFreeText import QuestionFreeText
from edsl.agents import Agent


def test_multiple_runs():

    a = Agent(traits={})

    from edsl.data.Cache import Cache

    a.add_direct_question_answering_method(lambda self, question, scenario: "yes")

    q = QuestionFreeText.example()
    results = q.by(a).run(n=2, cache=Cache())
    assert len(results) == 2
