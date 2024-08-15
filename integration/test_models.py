from edsl import Model
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
    def model_test_func():
        m = Model(model)
        results = q.by(m).run(cache=False)
        results.select("answer.*", "model.model").print()

    return model_test_func


# from edsl.enums import LanguageModelType
# to_exclude = [LanguageModelType.LLAMA_2_13B_CHAT_HF.value]

# Dynamically adding test methods for each question type

models = ["gpt-4-turbo"]
for model in models:
    model_test_method_name = f"test_model_{model}"
    model_test_method = create_test_function(model)
    setattr(TestAllModels, model_test_method_name, model_test_method)
