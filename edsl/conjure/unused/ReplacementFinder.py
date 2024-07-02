from typing import Optional
from edsl import QuestionFreeText
from collections import UserDict


class ReplacementFinder(UserDict):
    """This class finds a replacement name for a bad question name, and returns it.
    It also stores the replacement names for future reference, functioning as a closure of sorts.
    """

    def __init__(self, lookup_dict: Optional[dict] = None):
        if lookup_dict is None:
            lookup_dict = {}
        super().__init__(lookup_dict)

    def __call__(
        self,
        bad_question_name: str,
        model=None,
        cache=None,
        auto_increment=True,
        verbose=False,
    ) -> str:
        """Find a replacement name for a bad question name and returns it.

        :param bad_question_name: The bad question name.
        :param model: The language model to use for when finding a replacement.
        :param cache: The cache to pass to the 'run'

        >>> r = ReplacementFinder({'Poop ': 'poop2'})
        >>> r('Poop ')
        'poop2'

        >>> from edsl.language_models import LanguageModel
        >>> m = LanguageModel.example(test_model=True, canned_response="poop2")
        >>> r = ReplacementFinder()
        >>> r('Poop ', model = m, cache = False)
        'poop2'
        >>> r['Poop ']
        'poop2'
        >>> r('Poop ', verbose = True)
        'poop2'


        """
        from edsl import Model

        if model is None:
            if hasattr(self, "model"):
                model = self.model
            else:
                model = Model()

        if bad_question_name in self:
            if verbose:
                print(f"Found in self")
            return self[bad_question_name]

        q = QuestionFreeText(
            question_text=f"""We have a survey with a question name: {bad_question_name}. 
            The question name is not a valid Python identifier.
            We need a valid Python identifier to use as a column name in a dataframe.
            What would be a better name for this question?
            Shorter is better.
            Just return the proposed identifier with no other text.
            """,
            question_name="identifier",
        )
        results = q.by(model).run(cache=cache)
        new_identifier = results.select("identifier").first().lower()
        if new_identifier in self.values():
            if auto_increment:
                new_identifier = new_identifier + "_pp"
            else:
                raise Exception(f"New identifier {new_identifier} is already in use.")
        self[bad_question_name] = new_identifier
        return new_identifier

    def to_dict(self) -> dict:
        """Serialize this object to a dictionary."""
        return self

    @classmethod
    def from_dict(cls, d) -> "ReplacementFinder":
        """Create an object from a dictionary.

        >>> rf = ReplacementFinder.example()
        >>> newrf = ReplacementFinder.from_dict(rf.to_dict())
        >>> newrf.data == rf.data
        True
        """
        return cls(d)

    @classmethod
    def example(cls) -> "ReplacementFinder":
        """Create an example object for testing."""
        return cls({"Poop ": "poop2"})

    def __repr__(self):
        return f"ReplacementFinder({self.data})"


if __name__ == "__main__":
    import doctest

    doctest.testmod()
