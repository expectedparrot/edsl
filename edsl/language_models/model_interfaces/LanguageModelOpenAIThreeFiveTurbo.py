from edsl.language_models.OpenAI import create_openai_model
from edsl.enums import LanguageModelType

model_name = LanguageModelType.GPT_3_5_Turbo.value

LanguageModelOpenAIThreeFiveTurbo = create_openai_model(
    model_name=model_name, model_class_name="LanguageModelOpenAIThreeFiveTurbo"
)
