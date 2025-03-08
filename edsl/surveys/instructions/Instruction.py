from typing import Union, Optional, List, Generator, Dict
from edsl.utilities.remove_edsl_version import remove_edsl_version
from edsl.base import RepresentationMixin
#from edsl.surveys import Survey


class Instruction(RepresentationMixin):
    def __init__(
        self, name, text, preamble="You were given the following instructions:"
    ):
        self.name = name
        self.text = text
        self.preamble = preamble

    def __str__(self):
        return self.text

    def __repr__(self):
        return """Instruction(name="{}", text="{}")""".format(self.name, self.text)

    @classmethod
    def example(cls) -> "Instruction":
        return cls(name="example", text="This is an example instruction.")

    def to_dict(self, add_edsl_version=True):
        d = {
            "name": self.name,
            "text": self.text,
            "edsl_class_name": "Instruction",
            "preamble": self.preamble,
        }
        if add_edsl_version:
            from edsl import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = "Instruction"
        return d

    def add_question(self, question) -> "Survey":
        from edsl.surveys import Survey
        return Survey([self, question])

    def __hash__(self) -> int:
        """Return a hash of the question."""
        from edsl.utilities.utilities import dict_hash

        return dict_hash(self.to_dict(add_edsl_version=False))

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data):
        return cls(
            data["name"],
            data["text"],
            data.get("preamble", "You were given the following instructions:"),
        )


if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)