from edsl.enums import LanguageModelType
from edsl.language_models.DeepInfra import create_deep_infra_model

model_name = LanguageModelType.MIXTRAL_8x7B_INSTRUCT.value
url = "https://api.deepinfra.com/v1/inference/mistralai/Mixtral-8x7B-Instruct-v0.1"

Mixtral8x7B = create_deep_infra_model(
    model_name=model_name, url=url, model_class_name="Mixtral8x7B"
)

if __name__ == "__main__":
    from edsl.questions import QuestionMultipleChoice

    m = Mixtral8x7B()
    q = QuestionMultipleChoice(
        question_text="Are pickled pigs feet a popular breakfast food in the US?",
        question_options=["Yes", "No", "Unsure"],
        question_name="bkfast_question",
    )
    results = q.by(m).run()
    from rich import print

    print(q)
    results.select("answer.*", "model.model").print()
