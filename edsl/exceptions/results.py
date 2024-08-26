class ResultsErrors(Exception):
    pass


class ResultsDeserializationError(ResultsErrors):
    pass


class ResultsBadMutationstringError(ResultsErrors):
    pass


class ResultsColumnNotFoundError(ResultsErrors):
    pass


class ResultsInvalidNameError(ResultsErrors):
    pass


class ResultsMutateError(ResultsErrors):
    pass


class ResultsFilterError(ResultsErrors):
    pass
