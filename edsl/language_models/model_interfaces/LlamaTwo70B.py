from edsl.language_models.DeepInfra import create_deep_infra_model

model_name = "Llama-2-70b-chat-hf"
url = "https://api.deepinfra.com/v1/inference/meta-llama/Llama-2-70b-chat-hf"

LlamaTwo70B = create_deep_infra_model(model_name=model_name, url=url)

if __name__ == "__main__":
    model = LlamaTwo70B(use_cache=False)
    from edsl.questions import QuestionMultipleChoice

    q = QuestionMultipleChoice(
        question_text="Are pickled pigs feet a popular breakfast food in the US?",
        question_options=["Yes", "No", "Unsure"],
        question_name="bkfast_question",
    )
    results = q.by(model).run()
    results.select("answer.*", "model.model").print()
