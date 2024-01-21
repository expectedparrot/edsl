class QuestionErrors(Exception):
    pass


class QuestionCreationValidationError(QuestionErrors):
    pass


class QuestionResponseValidationError(QuestionErrors):
    pass


class QuestionAnswerValidationError(QuestionErrors):
    pass


class QuestionAttributeMissing(QuestionErrors):
    pass


class QuestionSerializationError(QuestionErrors):
    pass


class QuestionScenarioRenderError(QuestionErrors):
    pass


class QuestionMissingTypeError(QuestionErrors):
    pass


class QuestionBadTypeError(QuestionErrors):
    pass
