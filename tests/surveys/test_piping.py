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


def test_alt_piping():
    # this one uses a test model to return the answers
    from edsl import QuestionList, QuestionMultipleChoice, Model, Survey

    def two_responses_closure():

        num_calls = 0

        def two_responses(user_prompt, system_prompt, files_list):
            nonlocal num_calls
            if num_calls == 0:
                num_calls += 1
                return """["Reading", "Sailing"]"""
            else:
                return "Sailing"

        return two_responses

    m = Model("test", func=two_responses_closure())
    q1 = QuestionList(question_text="What are your hobbies?", question_name="hobbies")
    q2 = QuestionMultipleChoice(
        question_text="Which is our favorite?",
        question_options=["{{hobbies.answer[0]}}", "{{hobbies.answer[1]}}"],
        question_name="favorite_hobby",
    )
    s = Survey([q1, q2])
    results = s.by(m).run(progress_bar=False, cache=False)
    # assert results.select("answer.*").to_list() == [(["Reading", "Sailing"], "Sailing")]


if __name__ == "__main__":
    pytest.main()
