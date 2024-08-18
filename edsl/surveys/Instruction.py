from typing import Union, Optional, List, Generator, Dict
from collections import UserList
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


class ChangeInstruction:

    def __init__(
        self,
        keep: Optional[List[str]] = None,
        drop: Optional[List[str]] = None,
    ):
        if keep is None and drop is None:
            raise ValueError("Keep and drop cannot both be None")

        self.keep = keep or []
        self.drop = drop or []

    def include_instruction(self, instruction_name) -> bool:
        return (instruction_name in self.keep) or (not instruction_name in self.drop)

    def add_name(self, index) -> None:
        self.name = "change_instruction_{}".format(index)

    def __str__(self):
        return self.text

    def to_dict(self):
        return {"keep": self.keep, "drop": self.drop}

    @classmethod
    def from_dict(cls, data):
        return cls(data["name"], data["text"])


class SituatedInstructionCollection:
    def __init__(
        self,
        instruction_names_to_instruction: Dict[str, Instruction],
        questions: List[QuestionBase],
    ):
        self.instruction_names_to_instruction = instruction_names_to_instruction
        self.questions = questions

    @property
    def question_names(self):
        return [q.name for q in self.questions]

    def question_index(self, question_name):
        return self.question_names.index(question_name)

    def change_instructions_before(self, question_name):
        if question_name not in self.question_names:
            raise ValueError(
                f"Question name not found in the list of questions: got {question_name}; list is {self.question_names}"
            )

        index = self.question_index(question_name)
        for (
            instruction_name,
            instruction,
        ) in self.instruction_names_to_instruction.items():
            if instruction.pseudo_index < index and isinstance(
                instruction, ChangeInstruction
            ):
                yield instruction

    def instructions_before(self, question_name) -> Generator[Instruction, None, None]:
        if question_name not in self.question_names:
            raise ValueError(
                f"Question name not found in the list of questions: got {question_name}; list is {self.question_names}"
            )

        index = self.question_index(question_name)
        for (
            instruction_name,
            instruction,
        ) in self.instruction_names_to_instruction.items():
            if instruction.pseudo_index < index and isinstance(
                instruction, Instruction
            ):
                yield instruction

    def relevant_instructions(
        self, question: Union[str, QuestionBase]
    ) -> Generator[Instruction, None, None]:
        ## Find all the questions that are after a given instruction
        if isinstance(question, str):
            question_name = question
        elif isinstance(question, QuestionBase):
            question_name = question.name
        instructions_before = list(self.instructions_before(question_name))
        change_instructions_before = list(
            self.change_instructions_before(question_name)
        )
        keep_list = []
        drop_list = []
        for instruction in change_instructions_before:
            keep_list.extend(instruction.keep)
            drop_list.extend(instruction.drop)

        for instruction in instructions_before:
            if instruction.name in keep_list or instruction.name not in drop_list:
                yield instruction

    def __len__(self):
        return len(self.instruction_names_to_instruction)

    # len(s.instructions)
    # assert s.pseudo_indices == {
    #     "how_are_you": 0,
    #     "intro": 0.5,
    #     "followon_intro": 0.75,
    #     "how_feeling": 1,
    # }

    # assert [
    #     x.name for x in list(s.instructions.instructions_before("how_feeling"))
    # ] == ["intro", "followon_intro"]

    # q3 = QuestionFreeText(
    #     question_text="What is your favorite color?", question_name="color"
    # )
    # i_change = ChangeInstruction(drop=["intro"])
    # s = Survey([q1, i, q2, i_change, q3])
    # assert [i.name for i in s.relevant_instructions("how_are_you")] == []
    # assert [i.name for i in s.relevant_instructions("how_feeling")] == ["intro"]
    # assert [i.name for i in s.relevant_instructions("color")] == []
