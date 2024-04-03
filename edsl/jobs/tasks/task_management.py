from collections import UserDict


class TokensUsed(UserDict):
    """ "Container for tokens used by a task."""

    def __init__(self, cached_tokens, new_tokens):
        d = {"cached_tokens": cached_tokens, "new_tokens": new_tokens}
        super().__init__(d)


if __name__ == "__main__":
    pass
