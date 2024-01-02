class LanguageModelExceptions(Exception):
    pass


class LanguageModelResponseNotJSONError(LanguageModelExceptions):
    pass


class LanguageModelMissingAttributeError(LanguageModelExceptions):
    pass


class LanguageModelAttributeTypeError(LanguageModelExceptions):
    pass


class LanguageModelDoNotAddError(LanguageModelExceptions):
    pass
