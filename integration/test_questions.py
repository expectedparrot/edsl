from edsl.questions.question_registry import get_question_class, Question


class TestAllQuestions:
    pass


to_exclude = ["extract"]


def create_test_function(question_type):
    @staticmethod
    def question_test_func():
        cls = get_question_class(question_type)
        if cls.question_type in to_exclude:
            pass
        else:
            results = cls.example().run()
            assert results is not None

    return question_test_func


# Dynamically adding test methods for each question type

for question_type in Question.available():
    question_test_method_name = f"test_question_{question_type}"
    question_test_method = create_test_function(question_type)
    setattr(TestAllQuestions, question_test_method_name, question_test_method)
