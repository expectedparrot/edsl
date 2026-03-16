"""Tests for humanize schema validation (coop_humanize_schema module)."""

import pytest
from edsl.coop.coop_humanize_schema import (
    HumanizeSchema,
    validate_humanize_schema,
)
from edsl.coop.exceptions import HumanizeSchemaValidationError
from edsl.instructions import Instruction
from edsl.questions import QuestionDemand, QuestionFreeText, QuestionMultipleChoice
from edsl.surveys import Survey


class TestValidateHumanizeSchema:
    """Test validate_humanize_schema with valid and invalid inputs."""

    def test_valid_schema_passes(self):
        """Valid humanize schema for a survey completes without error."""
        survey = Survey(
            [
                QuestionFreeText(
                    question_name="q1",
                    question_text="How are you?",
                ),
            ]
        )
        humanize_schema = {"questions": {"q1": {"optional": True}}}
        validate_humanize_schema(survey, humanize_schema)

    def test_valid_schema_empty_questions_passes(self):
        """Humanize schema with empty questions dict passes."""
        survey = Survey(
            [
                QuestionFreeText(
                    question_name="q1",
                    question_text="How are you?",
                ),
            ]
        )
        humanize_schema = {"questions": {}}
        validate_humanize_schema(survey, humanize_schema)

    def test_valid_schema_with_survey_key_passes(self):
        """Humanize schema with optional survey key passes."""
        survey = Survey(
            [
                QuestionFreeText(
                    question_name="q1",
                    question_text="How are you?",
                ),
            ]
        )
        humanize_schema = {
            "questions": {"q1": {"optional": False}},
            "survey": {"custom_css": None},
        }
        validate_humanize_schema(survey, humanize_schema)

    def test_valid_schema_with_format_passes(self):
        """Humanize schema with format (radio/dropdown) for supported question type passes."""
        survey = Survey(
            [
                QuestionMultipleChoice(
                    question_name="fruit",
                    question_text="Which fruit do you prefer?",
                    question_options=["Apple", "Banana", "Cherry"],
                ),
            ]
        )
        humanize_schema = {
            "questions": {
                "fruit": {"optional": False, "format": {"type": "dropdown"}},
            },
        }
        validate_humanize_schema(survey, humanize_schema)

    def test_question_not_in_survey_raises(self):
        """Humanize schema referencing a question not in the survey raises."""
        survey = Survey(
            [
                QuestionFreeText(
                    question_name="q1",
                    question_text="How are you?",
                ),
            ]
        )
        humanize_schema = {"questions": {"nonexistent": {"optional": True}}}
        with pytest.raises(HumanizeSchemaValidationError) as exc_info:
            validate_humanize_schema(survey, humanize_schema)
        assert "nonexistent" in str(exc_info.value)
        assert "not in the survey" in str(exc_info.value)

    def test_instruction_in_schema_raises(self):
        """Humanize schema referencing an instruction raises."""
        instruction = Instruction(name="intro", text="Welcome.")
        question = QuestionFreeText(
            question_name="q1",
            question_text="How are you?",
        )
        survey = Survey([instruction, question])
        humanize_schema = {"questions": {"intro": {"optional": True}}}
        with pytest.raises(HumanizeSchemaValidationError) as exc_info:
            validate_humanize_schema(survey, humanize_schema)
        assert "intro" in str(exc_info.value)
        assert "instruction" in str(exc_info.value).lower()

    def test_unsupported_question_type_raises(self):
        """Humanize schema for an unsupported question type (e.g. demand) raises."""
        survey = Survey(
            [
                QuestionDemand(
                    question_name="demand_q",
                    question_text="How many would you buy at each price?",
                    prices=[1.0, 2.0, 3.0],
                ),
            ]
        )
        humanize_schema = {"questions": {"demand_q": {"optional": True}}}
        with pytest.raises(HumanizeSchemaValidationError) as exc_info:
            validate_humanize_schema(survey, humanize_schema)
        assert "demand_q" in str(exc_info.value)
        assert "not supported" in str(exc_info.value).lower()

    def test_invalid_schema_structure_raises(self):
        """Invalid top-level schema structure raises HumanizeSchemaValidationError."""
        survey = Survey(
            [
                QuestionFreeText(
                    question_name="q1",
                    question_text="How are you?",
                ),
            ]
        )
        humanize_schema = {"questions": {"q1": "not_a_dict"}}
        with pytest.raises(HumanizeSchemaValidationError):
            validate_humanize_schema(survey, humanize_schema)

    def test_invalid_question_entry_type_raises(self):
        """Invalid type for a question's schema entry raises."""
        survey = Survey(
            [
                QuestionFreeText(
                    question_name="q1",
                    question_text="How are you?",
                ),
            ]
        )
        humanize_schema = {"questions": {"q1": {"optional": "not_a_bool"}}}
        with pytest.raises(HumanizeSchemaValidationError):
            validate_humanize_schema(survey, humanize_schema)

    def test_multiple_questions_valid(self):
        """Schema with multiple questions of different supported types passes."""
        survey = Survey(
            [
                QuestionFreeText(
                    question_name="text_q",
                    question_text="Free text?",
                ),
                QuestionFreeText(
                    question_name="another",
                    question_text="Another?",
                ),
            ]
        )
        humanize_schema = {
            "questions": {
                "text_q": {"optional": True},
                "another": {"optional": False},
            }
        }
        validate_humanize_schema(survey, humanize_schema)

    def test_extra_field_in_question_entry_raises(self):
        """Question entry with an extra (forbidden) field raises."""
        survey = Survey(
            [
                QuestionFreeText(
                    question_name="q1",
                    question_text="How are you?",
                ),
            ]
        )
        humanize_schema = {"questions": {"q1": {"optional": True, "unknown_key": 1}}}
        with pytest.raises(HumanizeSchemaValidationError):
            validate_humanize_schema(survey, humanize_schema)

    def test_extra_field_in_survey_entry_raises(self):
        """Survey-level entry with an extra (forbidden) field raises."""
        survey = Survey(
            [
                QuestionFreeText(
                    question_name="q1",
                    question_text="How are you?",
                ),
            ]
        )
        humanize_schema = {
            "questions": {"q1": {"optional": False}},
            "survey": {"custom_css": None, "unknown_key": "x"},
        }
        with pytest.raises(HumanizeSchemaValidationError):
            validate_humanize_schema(survey, humanize_schema)

    def test_extra_field_at_top_level_raises(self):
        """Top-level humanize schema with an extra (forbidden) field raises."""
        survey = Survey(
            [
                QuestionFreeText(
                    question_name="q1",
                    question_text="How are you?",
                ),
            ]
        )
        humanize_schema = {
            "questions": {"q1": {"optional": False}},
            "survey": None,
            "unknown_top_level": True,
        }
        with pytest.raises(HumanizeSchemaValidationError):
            validate_humanize_schema(survey, humanize_schema)


class TestHumanizeSchemaModel:
    """Test HumanizeSchema Pydantic model."""

    def test_parse_valid_schema(self):
        """HumanizeSchema.model_validate accepts valid dict."""
        data = {"questions": {"q1": {"optional": True}}, "survey": None}
        parsed = HumanizeSchema.model_validate(data)
        assert "q1" in parsed.questions
        assert parsed.questions["q1"].optional is True
        assert parsed.survey is None

    def test_parse_empty_questions(self):
        """HumanizeSchema accepts empty questions."""
        data = {"questions": {}}
        parsed = HumanizeSchema.model_validate(data)
        assert parsed.questions == {}

    def test_extra_fields_forbidden_top_level(self):
        """HumanizeSchema forbids extra top-level fields."""
        from pydantic import ValidationError

        data = {"questions": {}, "survey": None, "extra_key": True}
        with pytest.raises(ValidationError):
            HumanizeSchema.model_validate(data)

    def test_extra_fields_forbidden_question_entry(self):
        """Question schema models forbid extra fields."""
        from edsl.coop.coop_humanize_schema import FreeTextHumanizeSchema
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            FreeTextHumanizeSchema.model_validate({"optional": True, "extra": 1})

    def test_extra_fields_forbidden_survey_entry(self):
        """SurveyHumanizeSchema forbids extra fields."""
        from edsl.coop.coop_humanize_schema import SurveyHumanizeSchema
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SurveyHumanizeSchema.model_validate({"custom_css": None, "extra": "x"})
