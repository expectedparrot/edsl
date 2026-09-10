"""Tests for humanize schema validation (coop_humanize_schema module)."""

import pytest
from edsl.coop.coop_humanize_schema import (
    HumanizeSchema,
    validate_humanize_schema,
)
from edsl.coop.exceptions import HumanizeSchemaValidationError
from edsl.instructions import Instruction
from edsl.questions import (
    QuestionCheckBox,
    QuestionCheckBoxWithOther,
    QuestionDemand,
    QuestionFreeText,
    QuestionInterview,
    QuestionMultipleChoice,
    QuestionNumerical,
    SurveyMessage,
)
from edsl.surveys import Survey


class TestValidateHumanizeSchemaGeneral:
    """General validate_humanize_schema behavior."""

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

    def test_valid_schema_with_group_presentation_passes(self):
        """Humanize schema can request grouped survey presentation."""
        survey = Survey(
            [
                QuestionFreeText(
                    question_name="q1",
                    question_text="How are you?",
                ),
            ]
        )
        # A survey needs a group before it can be presented by group; see
        # TestValidateGroupPresentation for what is checked once one is asked for.
        survey.add_question_group("q1", "q1", "page_0")
        humanize_schema = {
            "questions": {"q1": {"optional": False}},
            "survey": {"presentation": "group"},
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

    def test_survey_message_accepts_only_empty_display_configuration(self):
        survey = Survey(
            [SurveyMessage(question_name="thanks", question_text="Thank you.")]
        )

        validate_humanize_schema(survey, {"questions": {"thanks": {}}})

        with pytest.raises(HumanizeSchemaValidationError):
            validate_humanize_schema(
                survey, {"questions": {"thanks": {"optional": True}}}
            )

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


class TestValidateHumanizeSchemaNumerical:
    """Numerical-specific validate_humanize_schema behavior."""

    @pytest.mark.parametrize(
        "slider_config, expected_error_snippet",
        [
            (
                {"type": "slider", "min": 5, "max": 5, "step": 1},
                "minimum must be less than maximum",
            ),
            (
                {"type": "slider", "min": 0, "max": 10, "step": 0},
                "step must be positive",
            ),
            (
                {"type": "slider", "min": 0, "max": 10, "step": 11},
                "step must not exceed (max - min)",
            ),
        ],
    )
    def test_numerical_slider_invalid_bounds_raise(
        self, slider_config, expected_error_snippet
    ):
        """Numerical slider rejects invalid min/max/step combinations."""
        survey = Survey(
            [
                QuestionNumerical(
                    question_name="num_q",
                    question_text="How many units?",
                ),
            ]
        )
        humanize_schema = {
            "questions": {
                "num_q": {
                    "optional": False,
                    "format": slider_config,
                }
            }
        }
        with pytest.raises(HumanizeSchemaValidationError) as exc_info:
            validate_humanize_schema(survey, humanize_schema)
        assert expected_error_snippet in str(exc_info.value)


class TestValidateHumanizeSchemaInterview:
    """Interview-specific validate_humanize_schema behavior."""

    def test_interview_mode_default_passes(self):
        """interview_mode defaults to 'text' when omitted."""
        survey = Survey(
            [
                QuestionInterview(
                    question_name="q1",
                    question_text="Tell me about your experience.",
                    interview_guide="Ask follow-up questions about details.",
                ),
            ]
        )
        humanize_schema = {"questions": {"q1": {"optional": False}}}
        validate_humanize_schema(survey, humanize_schema)

    def test_interview_mode_invalid_value_raises(self):
        """interview_mode with an unsupported value raises."""
        survey = Survey(
            [
                QuestionInterview(
                    question_name="q1",
                    question_text="Tell me about your experience.",
                    interview_guide="Ask follow-up questions about details.",
                ),
            ]
        )
        humanize_schema = {
            "questions": {"q1": {"optional": False, "interview_mode": "video"}}
        }
        with pytest.raises(HumanizeSchemaValidationError):
            validate_humanize_schema(survey, humanize_schema)

    def test_checklist_unique_ids_passes(self):
        """Text interview checklist with unique item ids passes."""
        survey = Survey(
            [
                QuestionInterview(
                    question_name="q1",
                    question_text="Tell me about your experience.",
                    interview_guide="Ask follow-up questions about details.",
                ),
            ]
        )
        humanize_schema = {
            "questions": {
                "q1": {
                    "optional": False,
                    "text_interview_config": {
                        "checklist": {
                            "initial": {
                                "items": [
                                    {
                                        "id": "role",
                                        "label": "Asked about their role",
                                        "instructions": "Check once their job title is known.",
                                    },
                                    {
                                        "id": "tenure",
                                        "label": "Asked how long they've been there",
                                        "instructions": "Check once tenure is known.",
                                    },
                                ]
                            }
                        }
                    },
                }
            }
        }
        validate_humanize_schema(survey, humanize_schema)

    def test_checklist_duplicate_ids_raises(self):
        """Text interview checklist with duplicate item ids raises."""
        survey = Survey(
            [
                QuestionInterview(
                    question_name="q1",
                    question_text="Tell me about your experience.",
                    interview_guide="Ask follow-up questions about details.",
                ),
            ]
        )
        humanize_schema = {
            "questions": {
                "q1": {
                    "optional": False,
                    "text_interview_config": {
                        "checklist": {
                            "initial": {
                                "items": [
                                    {
                                        "id": "dup",
                                        "label": "Asked about their role",
                                        "instructions": "Check once their job title is known.",
                                    },
                                    {
                                        "id": "dup",
                                        "label": "Asked how long they've been there",
                                        "instructions": "Check once tenure is known.",
                                    },
                                ]
                            }
                        }
                    },
                }
            }
        }
        with pytest.raises(HumanizeSchemaValidationError) as exc_info:
            validate_humanize_schema(survey, humanize_schema)
        assert "unique" in str(exc_info.value).lower()


class TestValidateHumanizeSchemaVoice:
    """Voice-interview-specific validate_humanize_schema behavior."""

    @staticmethod
    def _survey():
        return Survey(
            [
                QuestionInterview(
                    question_name="q1",
                    question_text="Tell me about your experience.",
                    interview_guide="Ask follow-up questions about details.",
                ),
            ]
        )

    def test_voice_config_default_language(self):
        """voice_interview_config defaults language to the default when omitted."""
        from edsl.coop.coop_humanize_schema import (
            InterviewHumanizeSchema,
        )
        from edsl.coop.voice_interview_languages import (
            DEFAULT_VOICE_INTERVIEW_LANGUAGE,
        )

        parsed = InterviewHumanizeSchema.model_validate(
            {"interview_mode": "voice", "voice_interview_config": {}}
        )
        assert (
            parsed.voice_interview_config.language
            == DEFAULT_VOICE_INTERVIEW_LANGUAGE
        )

    def test_voice_config_supported_language_passes(self):
        """A supported language validates through validate_humanize_schema."""
        humanize_schema = {
            "questions": {
                "q1": {
                    "interview_mode": "voice",
                    "voice_interview_config": {"language": "french"},
                }
            }
        }
        validate_humanize_schema(self._survey(), humanize_schema)

    def test_voice_config_language_normalized(self):
        """The before-validator normalizes case and surrounding whitespace."""
        from edsl.coop.coop_humanize_schema import InterviewHumanizeSchema

        parsed = InterviewHumanizeSchema.model_validate(
            {"voice_interview_config": {"language": "  French "}}
        )
        assert parsed.voice_interview_config.language == "french"

    def test_voice_config_language_none_uses_default(self):
        """A null language falls back to the default rather than failing."""
        from edsl.coop.coop_humanize_schema import InterviewHumanizeSchema
        from edsl.coop.voice_interview_languages import (
            DEFAULT_VOICE_INTERVIEW_LANGUAGE,
        )

        parsed = InterviewHumanizeSchema.model_validate(
            {"voice_interview_config": {"language": None}}
        )
        assert (
            parsed.voice_interview_config.language
            == DEFAULT_VOICE_INTERVIEW_LANGUAGE
        )

    def test_voice_config_unsupported_language_raises(self):
        """An unsupported language raises HumanizeSchemaValidationError."""
        humanize_schema = {
            "questions": {
                "q1": {
                    "interview_mode": "voice",
                    "voice_interview_config": {"language": "klingon"},
                }
            }
        }
        with pytest.raises(HumanizeSchemaValidationError) as exc_info:
            validate_humanize_schema(self._survey(), humanize_schema)
        assert "klingon" in str(exc_info.value).lower()


class TestValidateHumanizeSchemaComments:
    """Comment-related validate_humanize_schema behavior."""

    def test_valid_schema_with_comment_supported_type_passes(self):
        """Comment config validates for a supported question type."""
        survey = Survey(
            [
                QuestionFreeText(
                    question_name="q1",
                    question_text="How are you?",
                ),
            ]
        )
        humanize_schema = {
            "questions": {
                "q1": {
                    "optional": True,
                    "comment": {"label": "Anything else you'd like to share?"},
                }
            }
        }
        validate_humanize_schema(survey, humanize_schema)

    def test_comment_label_required_raises(self):
        """Comment config without required label raises."""
        survey = Survey(
            [
                QuestionFreeText(
                    question_name="q1",
                    question_text="How are you?",
                ),
            ]
        )
        humanize_schema = {
            "questions": {
                "q1": {
                    "optional": True,
                    "comment": {},
                }
            }
        }
        with pytest.raises(HumanizeSchemaValidationError) as exc_info:
            validate_humanize_schema(survey, humanize_schema)
        assert "label" in str(exc_info.value).lower()

    def test_comment_unsupported_question_type_raises(self):
        """Comment config on unsupported-for-comment type raises."""
        survey = Survey(
            [
                QuestionInterview(
                    question_name="q1",
                    question_text="Tell me about your experience.",
                    interview_guide="Ask follow-up questions about details.",
                ),
            ]
        )
        humanize_schema = {
            "questions": {
                "q1": {
                    "optional": True,
                    "comment": {"label": "Extra context"},
                }
            }
        }
        with pytest.raises(HumanizeSchemaValidationError) as exc_info:
            validate_humanize_schema(survey, humanize_schema)
        assert "comment" in str(exc_info.value).lower()


class TestValidateHumanizeSchemaSelectAll:
    """The Select all box on a checkbox question."""

    @staticmethod
    def _checkbox_survey() -> Survey:
        return Survey(
            [
                QuestionCheckBox(
                    question_name="q1",
                    question_text="Which did you order?",
                    question_options=["Starters", "Dessert"],
                ),
            ]
        )

    def test_default_keeps_the_box(self):
        """An entry that says nothing leaves the box a checkbox already shows.

        Read off the checkbox model rather than a parsed schema: an entry as
        sparse as ``{}`` fits every question type, so the union would land on
        whichever comes first rather than on the one under test.
        """
        from edsl.coop.coop_humanize_schema import CheckboxHumanizeSchema

        parsed = CheckboxHumanizeSchema.model_validate({})
        assert parsed.select_all is not None
        assert parsed.select_all.label is None

    def test_null_removes_the_box(self):
        """Explicit null is how an author takes the box away."""
        humanize_schema = {"questions": {"q1": {"select_all": None}}}
        validate_humanize_schema(self._checkbox_survey(), humanize_schema)

    def test_default_label_passes(self):
        """Naming today's wording is accepted, and says no more than omitting it."""
        humanize_schema = {"questions": {"q1": {"select_all": {"label": "Select all"}}}}
        validate_humanize_schema(self._checkbox_survey(), humanize_schema)

    @pytest.mark.parametrize("label", ["Pick every one", "select all", " Select all "])
    def test_other_label_raises(self, label):
        """No other wording is accepted yet, whitespace and case included."""
        humanize_schema = {"questions": {"q1": {"select_all": {"label": label}}}}
        with pytest.raises(HumanizeSchemaValidationError) as exc_info:
            validate_humanize_schema(self._checkbox_survey(), humanize_schema)
        assert "label" in str(exc_info.value).lower()

    def test_checkbox_with_other_raises(self):
        """checkbox_with_other has no Select all box, so it has no field for one."""
        survey = Survey(
            [
                QuestionCheckBoxWithOther(
                    question_name="q1",
                    question_text="Any dietary requirements?",
                    question_options=["Vegetarian", "Vegan"],
                ),
            ]
        )
        humanize_schema = {"questions": {"q1": {"select_all": None}}}
        with pytest.raises(HumanizeSchemaValidationError) as exc_info:
            validate_humanize_schema(survey, humanize_schema)
        assert "select_all" in str(exc_info.value).lower()


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


class TestStepsProgress:
    """Test the stepped progress indicator's boundaries."""

    def test_named_boundaries_pass(self):
        """Steps naming distinct items, with the last running to the end, parse."""
        from edsl.coop.coop_humanize_schema import StepsProgress

        parsed = StepsProgress.model_validate(
            {
                "steps": [
                    {"label": "Background", "complete_after": "q1"},
                    {"label": "Wrap-up"},
                ]
            }
        )
        assert parsed.steps[0].complete_after == "q1"
        assert parsed.steps[1].complete_after is None

    def test_boundary_is_stripped(self):
        """Surrounding whitespace is trimmed so the name matches the survey item."""
        from edsl.coop.coop_humanize_schema import StepsProgress

        parsed = StepsProgress.model_validate(
            {"steps": [{"complete_after": "  q1  "}, {}]}
        )
        assert parsed.steps[0].complete_after == "q1"

    @pytest.mark.parametrize("boundary", ["", "   "])
    def test_blank_boundary_raises(self, boundary):
        """A blank complete_after is rejected rather than taken as a boundary."""
        from edsl.coop.coop_humanize_schema import StepsProgress
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            StepsProgress.model_validate({"steps": [{"complete_after": boundary}, {}]})

    def test_blank_boundary_is_not_an_omission(self):
        """A blank name on a non-final step raises on its own, not as a repeat."""
        from edsl.coop.coop_humanize_schema import StepsProgress
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            StepsProgress.model_validate(
                {"steps": [{"complete_after": ""}, {"complete_after": ""}, {}]}
            )

    def test_earlier_step_must_name_a_boundary(self):
        """Only the final step may omit complete_after."""
        from edsl.coop.coop_humanize_schema import StepsProgress
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            StepsProgress.model_validate({"steps": [{}, {"complete_after": "q2"}]})

    def test_repeated_boundary_raises(self):
        """Two steps may not end after the same survey item."""
        from edsl.coop.coop_humanize_schema import StepsProgress
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            StepsProgress.model_validate(
                {"steps": [{"complete_after": "q1"}, {"complete_after": "q1"}, {}]}
            )


class TestValidateGroupPresentation:
    """Checks that only apply under ``presentation: "group"``.

    Each guards a failure that is silent at render time: a question that is never
    served, an instruction nobody reads, or a page that cannot be submitted. They
    exist so the author hears about it here, with the survey still unpublished,
    rather than a respondent meeting it later.
    """

    GROUP = {"survey": {"presentation": "group"}}

    @staticmethod
    def _survey(names):
        return Survey(
            [QuestionFreeText(question_name=n, question_text=n) for n in names]
        )

    def test_well_formed_groups_pass(self):
        survey = self._survey(["a", "b", "c", "d"])
        survey.question_groups = {"g0": (0, 1), "g1": (2, 3)}
        validate_humanize_schema(survey, self.GROUP)

    def test_group_presentation_without_groups_raises(self):
        """The one case with no legitimate reading: nothing to page by."""
        survey = self._survey(["a", "b"])
        with pytest.raises(HumanizeSchemaValidationError, match="no question groups"):
            validate_humanize_schema(survey, self.GROUP)

    def test_groups_are_ignored_when_presentation_is_not_group(self):
        """Malformed groups are inert unless the schema asks to page by them."""
        survey = self._survey(["a", "b", "c"])
        survey.question_groups = {"g0": (0, 0)}  # b and c in no group
        validate_humanize_schema(survey, {"questions": {}})

    def test_uncovered_question_raises(self):
        """A question in no group is never served and is recorded as skipped."""
        survey = self._survey(["a", "b", "c", "d"])
        survey.question_groups = {"g0": (0, 0), "g1": (3, 3)}
        with pytest.raises(HumanizeSchemaValidationError, match="'b', 'c'"):
            validate_humanize_schema(survey, self.GROUP)

    def test_overlapping_groups_raise(self):
        """Which page a shared question lands on would be settled by ordering."""
        survey = self._survey(["a", "b", "c"])
        survey.question_groups = {"g0": (0, 1), "g1": (1, 2)}
        with pytest.raises(HumanizeSchemaValidationError, match="more than one"):
            validate_humanize_schema(survey, self.GROUP)

    def test_interview_sharing_a_page_raises(self):
        """An interview fills the screen and ends itself; Next cannot submit it."""
        survey = Survey(
            [
                QuestionFreeText(question_name="a", question_text="a"),
                QuestionInterview(
                    question_name="iv", question_text="t", interview_guide="g"
                ),
            ]
        )
        survey.question_groups = {"g0": (0, 1)}
        with pytest.raises(HumanizeSchemaValidationError, match="page of its own"):
            validate_humanize_schema(survey, self.GROUP)

    def test_interview_alone_in_its_group_passes(self):
        survey = Survey(
            [
                QuestionFreeText(question_name="a", question_text="a"),
                QuestionInterview(
                    question_name="iv", question_text="t", interview_guide="g"
                ),
            ]
        )
        survey.question_groups = {"g0": (0, 0), "g1": (1, 1)}
        validate_humanize_schema(survey, self.GROUP)

    def test_trailing_instruction_raises(self):
        """An instruction past the last group has no page to appear on."""
        survey = Survey(
            [
                QuestionFreeText(question_name="a", question_text="a"),
                Instruction(name="outro", text="Thanks!"),
            ]
        )
        survey.question_groups = {"g0": (0, 0)}
        with pytest.raises(HumanizeSchemaValidationError, match="after the last"):
            validate_humanize_schema(survey, self.GROUP)

    def test_group_range_may_extend_to_catch_a_trailing_instruction(self):
        """Instructions attach by pseudo-index, so a range past the last question
        legitimately pulls a trailing one onto the final page."""
        survey = Survey(
            [
                QuestionFreeText(question_name="a", question_text="a"),
                Instruction(name="outro", text="Thanks!"),
            ]
        )
        survey.question_groups = {"g0": (0, 1)}
        validate_humanize_schema(survey, self.GROUP)

    def test_leading_and_mid_survey_instructions_pass(self):
        survey = Survey(
            [
                Instruction(name="intro", text="Welcome"),
                QuestionFreeText(question_name="a", question_text="a"),
                Instruction(name="mid", text="Part two"),
                QuestionFreeText(question_name="b", question_text="b"),
            ]
        )
        survey.question_groups = {"g0": (0, 0), "g1": (1, 1)}
        validate_humanize_schema(survey, self.GROUP)

    def test_instruction_on_a_background_only_group_raises(self):
        """That group is run and passed over, taking the instruction with it."""
        from edsl.questions import QuestionCompute

        survey = Survey(
            [
                QuestionFreeText(question_name="a", question_text="a"),
                Instruction(name="mid", text="Part two"),
                QuestionCompute(question_name="c0", question_text="{{ 1 + 1 }}"),
                QuestionFreeText(question_name="b", question_text="b"),
            ]
        )
        survey.question_groups = {"g0": (0, 0), "g1": (1, 1), "g2": (2, 2)}
        with pytest.raises(HumanizeSchemaValidationError, match="never be read"):
            validate_humanize_schema(survey, self.GROUP)
