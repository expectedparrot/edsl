from textwrap import dedent


class LanguageModelExceptions(Exception):
    pass


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
