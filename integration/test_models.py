import pytest
from edsl.questions.question_registry import get_question_class, QuestionBase
from edsl import Model
from edsl.questions import QuestionMultipleChoice

from edsl.questions import QuestionMultipleChoice

q = QuestionMultipleChoice(
    question_text="Are pickled pigs feet a popular breakfast food in the US?",
    question_options=["Yes", "No", "Unsure"],
    question_name="bkfast_question",
)


class TestAllModels:
    pass


def create_test_function(model):
    @staticmethod
    def test_func():
        print(f"Now running: {model}")
        m = Model(model, use_cache=False)
        try:
            results = q.by(m).run()
            results.select("answer.*", "model.model").print()
        except Exception as e:
            pytest.fail(f"Error running {model}: {e}")

    return test_func


to_exclude = ["Llama-2-13b-chat-hf"]

# Dynamically adding test methods for each question type
for model in (model for model in Model.available() if model not in to_exclude):
    test_method_name = f"test_{model}"
    test_method = create_test_function(model)
    setattr(TestAllModels, test_method_name, test_method)

# for model in Model.available():
#     m = Model(model)
#     results = q.by(m).run()
