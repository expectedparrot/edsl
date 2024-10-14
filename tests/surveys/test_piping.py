from edsl import QuestionList, QuestionMultipleChoice, Survey, Agent, Cache
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
    results = survey.by(a).by(m).run(cache=Cache())
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


def test_option_expand_piping():
    from edsl import QuestionList, QuestionCheckBox, Survey, Model

    def two_responses_closure():

        num_calls = 0

        def two_responses(user_prompt, system_prompt, files_list):
            nonlocal num_calls
            if num_calls == 0:
                num_calls += 1
                return """["Red", "Blue", "Green", "Yellow", "Orange"]"""
            else:
                return "Red, Blue, Yellow"

        return two_responses

    m = Model("test", func=two_responses_closure())

    q1 = QuestionList(question_name="colors", question_text="Draft a list of colors.")

    q2 = QuestionCheckBox(
        question_name="primary",
        question_text="Which of these colors are primary?",
        question_options="{{ colors.answer }}",
    )

    survey = Survey([q1, q2])

    results = survey.by(m).run()
    # results.select("primary").print(format="rich")
    # breakpoint()
    # Conform it got passed through
    results.select("question_options.primary").to_list()[0] == [
        "Red",
        "Blue",
        "Green",
        "Yellow",
        "Orange",
    ]

    # from edsl.scenarios.Dataset import Dataset
    # assert results.select('question_options.primary') == Dataset([{'question_options.primary_question_options': [['Red', 'Blue', 'Green', 'Yellow', 'Orange']]}])


if __name__ == "__main__":
    pytest.main()
