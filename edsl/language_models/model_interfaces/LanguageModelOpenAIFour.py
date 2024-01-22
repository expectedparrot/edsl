from edsl.language_models.OpenAI import create_openai_model
from edsl.enums import LanguageModelType

model_name = LanguageModelType.GPT_4.value

LanguageModelOpenAIFour = create_openai_model(
    model_name=model_name, model_class_name="LanguageModelOpenAIFour"
)
