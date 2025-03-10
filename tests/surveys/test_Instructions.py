import pytest
from edsl.surveys import Survey
from edsl.instructions import Instruction
from edsl.instructions import ChangeInstruction
from edsl.questions import QuestionFreeText, QuestionMultipleChoice


def test_instructions():
    i = Instruction(text="Pay attention to the following questions.", name="intro")
    assert isinstance(i, Instruction)

    i2 = Instruction(text="How are you feeling today?", name="followon_intro")
    q1 = QuestionFreeText.example()
    q2 = QuestionMultipleChoice.example()

    s = Survey([q1, i, i2, q2])

    # instructions, change = s.instructions._entries_before("how_feeling")
    instructions, change = s._relevant_instructions_dict._entries_before("how_feeling")
    assert [x.name for x in instructions] == ["intro", "followon_intro"]


def test_change_instruction_drop():
    q1 = QuestionFreeText.example()
    i = Instruction(text="Pay attention to the following questions.", name="intro")
    q2 = QuestionMultipleChoice.example()
    q3 = QuestionFreeText(
        question_text="What is your favorite color?", question_name="color"
    )

    i_change = ChangeInstruction(drop=["intro"])
    s = Survey([q1, i, q2, i_change, q3])

    assert [i.name for i in s._relevant_instructions("how_are_you")] == []
    assert [i.name for i in s._relevant_instructions("how_feeling")] == ["intro"]
    assert [i.name for i in s._relevant_instructions("color")] == []


def test_change_instruction_keep():
    q1 = QuestionFreeText.example()
    i = Instruction(text="Pay attention to the following questions.", name="intro")
    q2 = QuestionMultipleChoice.example()
    q3 = QuestionFreeText(
        question_text="What is your favorite color?", question_name="color"
    )

    i_change_keep = ChangeInstruction(keep=["intro"])
    s = Survey([q1, i, q2, i_change_keep, q3])

    assert [i.name for i in s._relevant_instructions("how_are_you")] == []
    assert [i.name for i in s._relevant_instructions("how_feeling")] == ["intro"]
    assert [i.name for i in s._relevant_instructions("color")] == ["intro"]


def test_serialization():
    q1 = QuestionFreeText.example()
    i = Instruction(text="Pay attention to the following questions.", name="intro")
    q2 = QuestionMultipleChoice.example()
    q3 = QuestionFreeText(
        question_text="What is your favorite color?", question_name="color"
    )
    i_change_keep = ChangeInstruction(keep=["intro"])
    survey = Survey([q1, i, q2, i_change_keep, q3])
    # breakpoint()
    new_s = Survey.from_dict(survey.to_dict())
    assert survey == new_s
    # breakpoint()


if __name__ == "__main__":
    pytest.main()
