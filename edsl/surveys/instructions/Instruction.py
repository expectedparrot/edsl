from typing import Union, Optional, List, Generator, Dict
from edsl.questions import QuestionBase


class Instruction:

    def __init__(self, name, text):
        self.name = name
        self.text = text

    def __str__(self):
        return self.text

    def __repr__(self):
        return """Instruction(name="{}", text="{}")""".format(self.name, self.text)

    def to_dict(self):
        return {"name": self.name, "text": self.text}

    @classmethod
    def from_dict(cls, data):
        return cls(data["name"], data["text"])
