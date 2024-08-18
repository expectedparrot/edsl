from edsl.surveys.instructions.Instruction import Instruction
from edsl.surveys.instructions.ChangeInstruction import ChangeInstruction
from edsl.questions import QuestionBase
from typing import Union, Optional, List, Generator, Dict


class InstructionCollection:
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

    def _entries_before(
        self, question_name
    ) -> tuple[List[Instruction], List[ChangeInstruction]]:
        if question_name not in self.question_names:
            raise ValueError(
                f"Question name not found in the list of questions: got {question_name}; list is {self.question_names}"
            )
        instructions, changes = [], []

        index = self.question_index(question_name)
        for instruction in self.instruction_names_to_instruction.values():
            if instruction.pseudo_index < index:
                if isinstance(instruction, Instruction):
                    instructions.append(instruction)
                elif isinstance(instruction, ChangeInstruction):
                    changes.append(instruction)
        return instructions, changes

    def relevant_instructions(
        self, question: Union[str, QuestionBase]
    ) -> Generator[Instruction, None, None]:
        ## Find all the questions that are after a given instruction
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
