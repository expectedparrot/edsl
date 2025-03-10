from ..base import BaseException

class CoopErrors(BaseException):
    pass


class CoopInvalidURLError(CoopErrors):
    pass


class CoopNoUUIDError(CoopErrors):
    pass


class CoopServerResponseError(CoopErrors):
    pass
