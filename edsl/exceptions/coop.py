class CoopErrors(Exception):
    pass


class InvalidApiKeyError(CoopErrors):
    def __init__(
        self,
        message="The API key provided is invalid. Please check your API key and try again.",
    ):
        self.message = message
        super().__init__(self.message)
