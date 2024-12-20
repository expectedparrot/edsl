from edsl.exceptions.BaseException import BaseException


class ResultsError(BaseException):
    relevant_docs = "https://docs.expectedparrot.com/en/latest/results.html"


class ResultsDeserializationError(ResultsError):
    pass


class ResultsBadMutationstringError(ResultsError):
    pass


class ResultsColumnNotFoundError(ResultsError):
    pass


class ResultsInvalidNameError(ResultsError):
    pass


class ResultsMutateError(ResultsError):
    pass


class ResultsFilterError(ResultsError):
    pass
