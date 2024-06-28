import re
from collections import UserDict

from edsl.conjure.ReplacementFinder import ReplacementFinder


class KeyValidator:
    """A class to represent a key validator.

    >>> k = KeyValidator()
    >>> k.validate_key("asdf")
    True
    >>> k.validate_key("ASDF")
    False

    """

    def __set_name__(self, owner, name):
        self.name = name

    def validate_key(self, key):
        if not isinstance(key, str):
            # "Key must be a string"
            return False
        if key.lower() != key:
            # "Key must be lowercase"
            return False
        if not key.isidentifier() or not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", key):
            # raise ValueError("Key must be a valid Python identifier")
            return False
        return True


class DictWithIdentifierKeys(UserDict):
    """
    This class is a dictionary that only allows lowercase keys that are valid Python identifiers.
    If a key is not a valid Python identifier, it will be replaced with a valid Python identifier.

    >>> d = DictWithIdentifierKeys()
    >>> d = DictWithIdentifierKeys({"7asdf": 123, "FAMILY": 12})
    >>> d
    {'q7asdf': 123, 'family': 12}
    """

    key_validator = KeyValidator()

    def __init__(
        self,
        data: dict = None,
        verbose: bool = False,
        replacement_finder: ReplacementFinder = None,
    ):
        super().__init__()
        self.verbose = verbose
        if replacement_finder is None:
            replacement_finder = ReplacementFinder({})
        self.replacement_finder = replacement_finder
        if data:
            for key, value in data.items():
                self[key] = value  # This will call the __setitem__ method

    def __setitem__(self, key, value):
        """Ensures that the key is a valid Python identifier. If not, it will be replaced, using the replacement_finder.

        >>> from edsl.conjure.ReplacementFinder import ReplacementFinder
        >>> from edsl.language_models import LanguageModel
        >>> m = LanguageModel.example(test_model=True, canned_response="poop2")
        >>> r = ReplacementFinder()
        >>> r.model = m
        >>> d = DictWithIdentifierKeys(verbose = True, replacement_finder=r)
        >>> d['Poop '] = 123
        Column incapable of being a key: 'Poop '
        Finding replacement
        New key found: 'poop2'

        >>> d['poop2']
        123
        """
        if self.verbose:
            print("Current dictionary is: ", self)
            print("Current replacement finder is: ", self.replacement_finder)
        while not self.key_validator.validate_key(key):
            if self.verbose:
                print(f"Column incapable of being a key: '{key}'")
            if key in self.replacement_finder:
                print(f"Replacing {key} with {self.replacement_finder[key]}")
                key = self.replacement_finder[key]
            else:
                if self.verbose:
                    print(f"Finding replacement")
                key = self.replacement_finder(key)
            if self.verbose:
                print(f"New key found: '{key}'")
        super().__setitem__(key, value)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
