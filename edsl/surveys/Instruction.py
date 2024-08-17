from typing import Union, Optional, List
from collections import UserList


class SituatedInstructionCollection:
    def __init__(self, situated_instructions, question_name_list=None):
        self.situated_instructions = situated_instructions
        self.question_name_list = question_name_list

    def instructions_before(self, question_name):
        ## Find all the questions that are after a given instruction
        ## Find out which ones got turned off
        if question_name not in self.question_name_list:
            raise ValueError(
                f"Question name not found in the list of questions: got {question_name}; list is {self.question_name_list}"
            )

        index = self.question_name_list.index(question_name)
        for (
            instruction_name,
            situated_instruction,
        ) in self.situated_instructions.items():
            if situated_instruction.pseudo_index < index:
                yield instruction_name

    def __len__(self):
        return len(self.situated_instructions)


class Instruction:

    def __init__(self, name, text):
        self.name = name
        self.text = text

    def __str__(self):
        return self.text

    def __repr__(self):
        return """Instruction(name={}, text={})""".format(self.name, self.text)

    def to_dict(self):
        return {"name": self.name, "text": self.text}

    @classmethod
    def from_dict(cls, data):
        return cls(data["name"], data["text"])


class ChangeInstruction:

    def __init__(
        self,
        name: str,
        keep: Optional[List[str]] = None,
        drop: Optional[List[str]] = None,
    ):
        self.name = name
        self.keep = keep
        self.drop = drop

    def __str__(self):
        return self.text

    def __repr__(self):
        return """Instruction(name={}, text={})""".format(self.name, self.text)

    def to_dict(self):
        return {"name": self.name, "text": self.text}

    @classmethod
    def from_dict(cls, data):
        return cls(data["name"], data["text"])


class SituatedInstruction:

    def __init__(
        self,
        instruction: Union[Instruction, ChangeInstruction],
        before_element: Union[str, None],
        after_element: Union[str],
        pseudo_index: float,
    ):
        self.instruction = instruction
        self.before_element = before_element
        self.after_element = after_element
        self.pseudo_index = pseudo_index
