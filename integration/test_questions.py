import pytest
from edsl.questions.question_registry import get_question_class, QuestionBase


class TestAllQuestions:
    pass


to_exclude = []


def create_test_function(question_type):
    @staticmethod
    def test_func():
        print(f"Now running: {question_type}")
        cls = get_question_class(question_type)
        try:
            if cls.question_type in to_exclude:
                pass
            else:
                results = cls.example().run()
                assert results is not None  # or any other assertion as needed
        except Exception as e:
            pytest.fail(f"Error running {question_type}: {e}")

    return test_func


# Dynamically adding test methods for each question type
for question_type in QuestionBase.available():
    test_method_name = f"test_{question_type}"
    test_method = create_test_function(question_type)
    setattr(TestAllQuestions, test_method_name, test_method)
