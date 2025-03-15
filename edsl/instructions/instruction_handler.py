from dataclasses import dataclass


@dataclass
class SeparatedComponents:
    true_questions: list
    instruction_names_to_instructions: dict
    pseudo_indices: dict


class InstructionHandler:
    def __init__(self, survey):
        self.survey = survey

    @staticmethod
    def separate_questions_and_instructions(questions_and_instructions: list) -> tuple:
        """
        The 'pseudo_indices' attribute is a dictionary that maps question names to pseudo-indices
        that are used to order questions and instructions in the survey.
        Only questions get real indices; instructions get pseudo-indices.
        However, the order of the pseudo-indices is the same as the order questions and instructions are added to the survey.

        We don't have to know how many instructions there are to calculate the pseudo-indices because they are
        calculated by the inverse of one minus the sum of 1/2^n for n in the number of instructions run so far.

        >>> from edsl import Survey
        >>> from edsl import Instruction
        >>> i = Instruction(text = "Pay attention to the following questions.", name = "intro")
        >>> i2 = Instruction(text = "How are you feeling today?", name = "followon_intro")
        >>> from edsl import QuestionFreeText; q1 = QuestionFreeText.example()
        >>> from edsl import QuestionMultipleChoice; q2 = QuestionMultipleChoice.example()
        >>> s = Survey([q1, i, i2, q2])
        >>> len(s._instruction_names_to_instructions)
        2
        >>> s._pseudo_indices
        {'how_are_you': 0, 'intro': 0.5, 'followon_intro': 0.75, 'how_feeling': 1}

        >>> from edsl import ChangeInstruction
        >>> q3 = QuestionFreeText(question_text = "What is your favorite color?", question_name = "color")
        >>> i_change = ChangeInstruction(drop = ["intro"])
        >>> s = Survey([q1, i, q2, i_change, q3])
        >>> [i.name for i in s._relevant_instructions(q1)]
        []
        >>> [i.name for i in s._relevant_instructions(q2)]
        ['intro']
        >>> [i.name for i in s._relevant_instructions(q3)]
        []

        >>> i_change = ChangeInstruction(keep = ["poop"], drop = [])
        >>> s = Survey([q1, i, q2, i_change])
        Traceback (most recent call last):
        ...
        edsl.instructions.exceptions.InstructionValueError: ChangeInstruction change_instruction_0 references instruction poop which does not exist.
        <BLANKLINE>
        <BLANKLINE>
        For more information, see: https://docs.expectedparrot.com/en/latest/instructions.html
        """
        from .instruction import Instruction
        from .change_instruction import ChangeInstruction
        from edsl.questions import QuestionBase

        true_questions = []
        instruction_names_to_instructions = {}

        num_change_instructions = 0
        pseudo_indices = {}
        instructions_run_length = 0
        for entry in questions_and_instructions:
            if isinstance(entry, Instruction) or isinstance(entry, ChangeInstruction):
                if isinstance(entry, ChangeInstruction):
                    entry.add_name(num_change_instructions)
                    num_change_instructions += 1
                    for prior_instruction in entry.keep + entry.drop:
                        if prior_instruction not in instruction_names_to_instructions:
                            from edsl.instructions.exceptions import InstructionValueError
                            raise InstructionValueError(
                                f"ChangeInstruction {entry.name} references instruction {prior_instruction} which does not exist."
                            )
                instructions_run_length += 1
                delta = 1 - 1.0 / (2.0**instructions_run_length)
                pseudo_index = (len(true_questions) - 1) + delta
                entry.pseudo_index = pseudo_index
                instruction_names_to_instructions[entry.name] = entry
            elif isinstance(entry, QuestionBase):
                pseudo_index = len(true_questions)
                instructions_run_length = 0
                true_questions.append(entry)
            else:
                from edsl.instructions.exceptions import InstructionValueError
                raise InstructionValueError(
                    f"Entry {repr(entry)} is not a QuestionBase or an Instruction."
                )

            pseudo_indices[entry.name] = pseudo_index

        return SeparatedComponents(
            true_questions, instruction_names_to_instructions, pseudo_indices
        )


if __name__ == "__main__":
    import doctest

    doctest.testmod()
