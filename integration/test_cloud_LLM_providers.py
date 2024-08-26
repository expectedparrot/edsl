from edsl import Model, QuestionFreeText


def test_cloud_azure():
    azure_models = Model.available("azure")
    azure_models
    for model_name in azure_models:
        print(model_name[0])
        model = Model(model_name[0])
        result = QuestionFreeText.example().by(model).run(cache=False)
        result.select("answer.*").print()


def test_aws_bedrock_models():
    bedrock_models = Model.available("bedrock")
    for model_name in bedrock_models:
        print(model_name[0])
        if model_name in [
            "amazon.titan-text-express-v1",
            "amazon.titan-tg1-large",
            "amazon.titan-text-lite-v1",
        ]:
            continue
        model = Model(model_name[0])
        result = QuestionFreeText.example().by(model).run(cache=False)
        result.select("answer.*").print()
