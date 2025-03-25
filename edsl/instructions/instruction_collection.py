from typing import TYPE_CHECKING, Dict, List, Generator, Union, Tuple
from collections import UserDict

from .instruction import Instruction
from .change_instruction import ChangeInstruction

if TYPE_CHECKING:
    from ..questions import QuestionBase


class InstructionCollection(UserDict):
    def __init__(
        self,
        instruction_names_to_instruction: Dict[str, Instruction],
        questions: List["QuestionBase"],
    ):
        self.instruction_names_to_instruction = instruction_names_to_instruction
        self.questions = questions
        data = {}
        for question in self.questions:
            # just add both the question and the question name
            data[question.name] = list(self.relevant_instructions(question))
            # data[question] = list(self.relevant_instructions(question))
        super().__init__(data)

    def __getitem__(self, key):
        # in case the person uses question instead of the name
        from ..questions import QuestionBase

        if isinstance(key, QuestionBase):
            key = key.name
        return self.data[key]

    @property
    def question_names(self):
        return [q.name for q in self.questions]

    def question_index(self, question_name):
        return self.question_names.index(question_name)

    def _entries_before(
        self, question_name
    ) -> Tuple[List[Instruction], List[ChangeInstruction]]:
        if question_name not in self.question_names:
            from .exceptions import InstructionCollectionError
            raise InstructionCollectionError(
                f"Question name not found in the list of questions: got '{question_name}'; list is {self.question_names}"
            )
        instructions: List[Instruction] = []
        changes: List[ChangeInstruction] = []

        index = self.question_index(question_name)
        for instruction in self.instruction_names_to_instruction.values():
            if instruction.pseudo_index < index:
                if isinstance(instruction, Instruction):
                    instructions.append(instruction)
                elif isinstance(instruction, ChangeInstruction):
                    changes.append(instruction)
        return instructions, changes

    def relevant_instructions(
        self, question: Union[str, "QuestionBase"]
    ) -> Generator[Instruction, None, None]:
        ## Find all the questions that are after a given instruction
        from ..questions import QuestionBase

        if isinstance(question, str):
            question_name = question
        elif isinstance(question, QuestionBase):
            question_name = question.name

        instructions_before, changes_before = self._entries_before(question_name)
        keep_list = []
        drop_list = []
        for change in changes_before:
            keep_list.extend(change.keep)
            drop_list.extend(change.drop)

        for instruction in instructions_before:
            if instruction.name in keep_list or instruction.name not in drop_list:
                yield instruction

    def __len__(self):
        return len(self.instruction_names_to_instruction)


if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)