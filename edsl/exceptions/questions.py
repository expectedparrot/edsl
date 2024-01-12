class QuestionErrors(Exception):
    pass


class QuestionAnswerValidationError(QuestionErrors):
    pass


class QuestionAttributeMissing(QuestionErrors):
    pass


class QuestionCreationValidationError(QuestionErrors):
    pass


class QuestionScenarioRenderError(QuestionErrors):
    pass


class QuestionSerializationError(QuestionErrors):
    pass
