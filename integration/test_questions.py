import pytest
from edsl.questions.question_registry import get_question_class, QuestionBase


class TestAllQuestions:
    pass


def create_test_function(question_type):
    def test_func(self):
        print(f"Now running: {question_type}")
        cls = get_question_class(question_type)
        try:
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
