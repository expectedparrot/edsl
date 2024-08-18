import pytest
from edsl import QuestionList, QuestionMultipleChoice, Survey, Agent
from edsl.language_models import LanguageModel


def test_survey_flow():
    a = Agent()
    m = LanguageModel.example("test")

    def f(self, question, scenario):
        if question.question_name == "q1":
            return ["red", "green", "blue"]
        if question.question_name == "q3":
            return "red"

    a.add_direct_question_answering_method(f)

    q1 = QuestionList(
        question_name="q1",
        question_text="What are your 3 favorite colors?",
        max_list_items=3,
    )

    q3 = QuestionMultipleChoice(
        question_name="q3",
        question_text="Which color is your #1 favorite?",
        question_options=["{{ q1.answer[0] }}", "{{ q1.answer[1] }}"],
    )

    survey = Survey([q1, q3])
    results = survey.by(a).by(m).run()
    assert results.select("q1", "q3").to_list() == [(["red", "green", "blue"], "red")]


if __name__ == "__main__":
    pytest.main()
