class CoopErrors(Exception):
    pass


class CoopNoUUIDError(CoopErrors):
    pass


class CoopServerResponseError(CoopErrors):
    pass
