"""Tests for enumeration styles (letters, numeric, etc.) in QuestionMultipleChoice."""

import pytest
from edsl.questions import QuestionMultipleChoice
from edsl.questions.question_multiple_choice import AnswerEnumeration


class TestAnswerEnumeration:
    """Test the AnswerEnumeration enum."""

    def test_enum_values(self):
        assert AnswerEnumeration.NONE is not None
        assert AnswerEnumeration.NUMERIC_STARTS_WITH_0 is not None
        assert AnswerEnumeration.NUMERIC_STARTS_WITH_1 is not None
        assert AnswerEnumeration.LETTERS is not None
        assert AnswerEnumeration.LETTERS_LOWER is not None

    def test_from_string(self):
        assert AnswerEnumeration("numeric_starts_with_0") == AnswerEnumeration.NUMERIC_STARTS_WITH_0
        assert AnswerEnumeration("letters") == AnswerEnumeration.LETTERS


class TestEnumerationCreation:
    """Test creating questions with different enumeration styles."""

    def test_default_no_enumeration(self):
        q = QuestionMultipleChoice(
            question_name="q1", question_text="Pick.", question_options=["A", "B"],
        )
        assert q.enumeration == AnswerEnumeration.NONE

    def test_enumeration_letters(self):
        q = QuestionMultipleChoice(
            question_name="q1", question_text="Pick.", question_options=["Red", "Blue"],
            enumeration="letters",
        )
        assert q.enumeration == AnswerEnumeration.LETTERS

    def test_enumeration_numeric_starts_with_0(self):
        q = QuestionMultipleChoice(
            question_name="q1", question_text="Pick.", question_options=["Red", "Blue"],
            enumeration="numeric_starts_with_0",
        )
        assert q.enumeration == AnswerEnumeration.NUMERIC_STARTS_WITH_0

    def test_use_code_backward_compat(self):
        """use_code=True should map to enumeration=NUMERIC_STARTS_WITH_0."""
        q = QuestionMultipleChoice(
            question_name="q1", question_text="Pick.", question_options=["Red", "Blue"],
            use_code=True,
        )
        assert q.enumeration == AnswerEnumeration.NUMERIC_STARTS_WITH_0

    def test_invalid_enumeration_raises(self):
        with pytest.raises(ValueError):
            QuestionMultipleChoice(
                question_name="q1", question_text="Pick.", question_options=["A", "B"],
                enumeration="roman_numerals",
            )

    def test_letters_max_26(self):
        with pytest.raises(ValueError):
            QuestionMultipleChoice(
                question_name="q1", question_text="Pick.",
                question_options=[f"Opt {i}" for i in range(27)],
                enumeration="letters",
            )

    def test_use_code_and_enumeration_raises(self):
        with pytest.raises(ValueError):
            QuestionMultipleChoice(
                question_name="q1", question_text="Pick.", question_options=["A", "B"],
                use_code=True, enumeration="letters",
            )


class TestEnumerationValidation:
    """Test answer validation with different enumeration styles."""

    def test_letters_accepts_valid(self):
        q = QuestionMultipleChoice(
            question_name="q1", question_text="Pick.",
            question_options=["Red", "Blue", "Green"],
            enumeration="letters",
        )
        result = q.response_validator.validate({"answer": "B"})
        assert result["answer"] == "B"

    def test_letters_rejects_out_of_range(self):
        from edsl.questions.exceptions import QuestionAnswerValidationError
        q = QuestionMultipleChoice(
            question_name="q1", question_text="Pick.",
            question_options=["Red", "Blue"],
            enumeration="letters",
        )
        with pytest.raises(QuestionAnswerValidationError):
            q.response_validator.validate({"answer": "C"})

    def test_letters_lower_accepts_lowercase(self):
        q = QuestionMultipleChoice(
            question_name="q1", question_text="Pick.",
            question_options=["Red", "Blue"],
            enumeration="letters_lower",
        )
        result = q.response_validator.validate({"answer": "b"})
        assert result["answer"] == "b"

    def test_numeric_starts_with_1_accepts(self):
        q = QuestionMultipleChoice(
            question_name="q1", question_text="Pick.",
            question_options=["Red", "Blue", "Green"],
            enumeration="numeric_starts_with_1",
        )
        result = q.response_validator.validate({"answer": 2})
        assert result["answer"] == 2

    def test_numeric_starts_with_1_rejects_zero(self):
        from edsl.questions.exceptions import QuestionAnswerValidationError
        q = QuestionMultipleChoice(
            question_name="q1", question_text="Pick.",
            question_options=["Red", "Blue"],
            enumeration="numeric_starts_with_1",
        )
        with pytest.raises(QuestionAnswerValidationError):
            q.response_validator.validate({"answer": 0})


class TestEnumerationTranslation:
    """Test translating enumerated answers back to option text."""

    def test_letters_translate(self):
        q = QuestionMultipleChoice(
            question_name="q1", question_text="Pick.",
            question_options=["Red", "Blue", "Green"],
            enumeration="letters",
        )
        assert q._translate_answer_code_to_answer("A", {}) == "Red"
        assert q._translate_answer_code_to_answer("B", {}) == "Blue"
        assert q._translate_answer_code_to_answer("C", {}) == "Green"

    def test_letters_lower_translate(self):
        q = QuestionMultipleChoice(
            question_name="q1", question_text="Pick.",
            question_options=["Red", "Blue"],
            enumeration="letters_lower",
        )
        assert q._translate_answer_code_to_answer("a", {}) == "Red"
        assert q._translate_answer_code_to_answer("b", {}) == "Blue"

    def test_numeric_starts_with_1_translate(self):
        q = QuestionMultipleChoice(
            question_name="q1", question_text="Pick.",
            question_options=["Red", "Blue", "Green"],
            enumeration="numeric_starts_with_1",
        )
        assert q._translate_answer_code_to_answer(1, {}) == "Red"
        assert q._translate_answer_code_to_answer(3, {}) == "Green"

    def test_numeric_starts_with_0_translate(self):
        """Numeric 0-based should work same as old use_code."""
        q = QuestionMultipleChoice(
            question_name="q1", question_text="Pick.",
            question_options=["Red", "Blue"],
            enumeration="numeric_starts_with_0",
        )
        assert q._translate_answer_code_to_answer(0, {}) == "Red"
        assert q._translate_answer_code_to_answer(1, {}) == "Blue"


class TestEnumerationFix:
    """Test fix() method with enumerated responses."""

    def test_fix_letter_with_label(self):
        q = QuestionMultipleChoice(
            question_name="q1", question_text="Pick.",
            question_options=["Red", "Blue", "Green"],
            enumeration="letters",
        )
        fixed = q.response_validator.fix({"answer": "B: Blue"})
        assert fixed["answer"] == "B"

    def test_fix_lowercase_to_uppercase(self):
        q = QuestionMultipleChoice(
            question_name="q1", question_text="Pick.",
            question_options=["Red", "Blue"],
            enumeration="letters",
        )
        fixed = q.response_validator.fix({"answer": "b"})
        assert fixed["answer"] == "B"

    def test_fix_numeric_starts_with_1_with_label(self):
        q = QuestionMultipleChoice(
            question_name="q1", question_text="Pick.",
            question_options=["Red", "Blue"],
            enumeration="numeric_starts_with_1",
        )
        fixed = q.response_validator.fix({"answer": "1: Red"})
        assert fixed["answer"] == 1


class TestEnumerationPrompt:
    """Test prompt generation with different enumeration styles."""

    def test_letters_in_prompt(self):
        q = QuestionMultipleChoice(
            question_name="q1", question_text="Pick a color.",
            question_options=["Red", "Blue", "Green"],
            enumeration="letters",
        )
        from edsl import Survey, Model
        prompts = Survey([q]).by(Model("test")).prompts()
        user_prompt = prompts.select("user_prompt").to_list()[0]
        assert "A:" in user_prompt or "A: " in user_prompt
        assert "B:" in user_prompt or "B: " in user_prompt

    def test_letters_instruction_in_prompt(self):
        q = QuestionMultipleChoice(
            question_name="q1", question_text="Pick a color.",
            question_options=["Red", "Blue"],
            enumeration="letters",
        )
        from edsl import Survey, Model
        prompts = Survey([q]).by(Model("test")).prompts()
        user_prompt = prompts.select("user_prompt").to_list()[0]
        assert "letter" in user_prompt.lower()

    def test_numeric_starts_with_1_in_prompt(self):
        q = QuestionMultipleChoice(
            question_name="q1", question_text="Pick.",
            question_options=["Red", "Blue"],
            enumeration="numeric_starts_with_1",
        )
        from edsl import Survey, Model
        prompts = Survey([q]).by(Model("test")).prompts()
        user_prompt = prompts.select("user_prompt").to_list()[0]
        assert "1:" in user_prompt or "1: " in user_prompt
        assert "2:" in user_prompt or "2: " in user_prompt


class TestEnumerationSerialization:
    """Test serialization roundtrip."""

    def test_roundtrip_letters(self):
        q = QuestionMultipleChoice(
            question_name="q1", question_text="Pick.",
            question_options=["Red", "Blue"],
            enumeration="letters",
        )
        d = q.to_dict()
        q2 = QuestionMultipleChoice.from_dict(d)
        assert q2.enumeration == AnswerEnumeration.LETTERS

    def test_roundtrip_numeric_starts_with_1(self):
        q = QuestionMultipleChoice(
            question_name="q1", question_text="Pick.",
            question_options=["Red", "Blue"],
            enumeration="numeric_starts_with_1",
        )
        d = q.to_dict()
        q2 = QuestionMultipleChoice.from_dict(d)
        assert q2.enumeration == AnswerEnumeration.NUMERIC_STARTS_WITH_1

    def test_roundtrip_none(self):
        q = QuestionMultipleChoice(
            question_name="q1", question_text="Pick.",
            question_options=["Red", "Blue"],
        )
        d = q.to_dict()
        q2 = QuestionMultipleChoice.from_dict(d)
        assert q2.enumeration == AnswerEnumeration.NONE
