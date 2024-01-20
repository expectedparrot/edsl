from edsl.language_models.model_interfaces.LanguageModelOpenAIFour import (
    LanguageModelOpenAIFour,
)


class LanguageModelOpenAIThreeFiveTurbo(LanguageModelOpenAIFour):
    _model_ = "gpt-3.5-turbo"
