from edsl import (
    QuestionFreeText,
    QuestionMultipleChoice,
    Survey,
    QuestionList,
)


def Quick(question_text):
    q_type = QuestionMultipleChoice(
        question_text=f"A researcher is asking a language model this: {question_text}. What is the most appropriate type of question to ask?",
        question_name="potential_question_type",
        question_options=["multiple_choice", "list", "free_text"],
    )

    q_name = QuestionFreeText(
        question_text=f"A researcher is asking a language model this: {question_text}. What is a good name for this question that's a valid python identifier? Just return the proposed identifer",
        question_name="potential_question_name",
    )

    q_options = QuestionList(
        question_text=f"A research is asking this question: { question_text }. What are the possible options for this question?",
        question_name="potential_question_options",
    )

    survey = Survey([q_type, q_name, q_options]).add_skip_rule(
        q_options, "{{ potential_question_type }} != 'multiple_choice'"
    )
    return survey
    # results = survey.run()
    # question_type = results.select("potential_question_type").first()
    # question_options = results.select("potential_question_options").first()
    # question_name = results.select("potential_question_name").first()
    # print("Question Type: ", question_type)
    # print("Question Name: ", question_name)
    # print("Question Options: ", question_options)
    # if question_options == None:
    #     return Question(question_type, question_name = question_name)
    # else:
    #     return Question(question_type, question_name = question_name, question_options = question_options)
