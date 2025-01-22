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
            To create an instance of this model, pass the model name to a `Model` object.
            You can optionally pass additional parameters to the model, e.g.: 
            >>> m = Model('gpt-4-1106-preview', temperature=0.5)
            
            To use the default model, simply run your job without specifying a model.
            To check the default model, run the following code:
            >>> Model()

            To see information about all available models, run the following code:
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
