from textwrap import dedent
from typing import Optional


class LanguageModelExceptions(Exception):
    explanation = (
        "This is the base class for all exceptions in the LanguageModel class."
    )

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class LanguageModelNoResponseError(LanguageModelExceptions):
    explanation = (
        """This happens when the LLM API cannot be reached and/or does not respond."""
    )

    def __init__(self, message):
        super().__init__(message)


class LanguageModelBadResponseError(LanguageModelExceptions):
    explanation = """This happens when the LLM API can be reached and responds, does not return a usable answer."""

    def __init__(self, message, response_json: Optional[dict] = None):
        super().__init__(message)
        self.response_json = response_json


class LanguageModelNotFound(LanguageModelExceptions):
    def __init__(self, model_name):
        msg = dedent(
            f"""\
            Model {model_name} not found.
            To create an instance, you can do: 
            >>> m = Model('gpt-4-1106-preview', temperature=0.5, ...)
            
            To get the default model, you can leave out the model name. 
            To see the available models, you can do:
            >>> Model.available()

            See https://docs.expectedparrot.com/en/latest/language_models.html#available-models for more details.
            """
        )
        super().__init__(msg)


class LanguageModelResponseNotJSONError(LanguageModelExceptions):
    pass


class LanguageModelMissingAttributeError(LanguageModelExceptions):
    pass


class LanguageModelAttributeTypeError(LanguageModelExceptions):
    pass


class LanguageModelDoNotAddError(LanguageModelExceptions):
    pass
