from edsl.language_models.DeepInfra import create_deep_infra_model
from edsl.enums import LanguageModelType

model_name = LanguageModelType.DBRX_INSTRUCT.value
url = "https://api.deepinfra.com/v1/inference/databricks/dbrx-instruct"

DbrxInstruct = create_deep_infra_model(
    model_name=model_name, url=url, model_class_name="DbrxInstruct"
)

if __name__ == "__main__":
    model = DbrxInstruct(use_cache=False)
    from edsl.questions import QuestionMultipleChoice

    q = QuestionMultipleChoice(
        question_text="Are pickled pigs feet a popular breakfast food in the US or Mexico?",
        question_options=["Yes", "No", "Unsure"],
        question_name="bkfast_question",
    )
    results = q.by(model).run()
    results.select("answer.*", "model.model").print()
