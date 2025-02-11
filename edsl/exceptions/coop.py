class CoopErrors(Exception):
    pass


class CoopInvalidURLError(CoopErrors):
    pass


class CoopNoUUIDError(CoopErrors):
    pass


class CoopServerResponseError(CoopErrors):
    pass
