"""Tests for humanize schema validation (coop_humanize_schema module)."""

import pytest
from pydantic import ValidationError
from edsl.coop.coop_humanize_schema import (
    QUESTION_TYPE_TO_HUMANIZE_CLASS,
    HumanizeSchema,
    validate_humanize_schema,
)
from edsl.coop.exceptions import HumanizeSchemaValidationError
from edsl.instructions import Instruction
from edsl.questions import (
    QuestionCheckBox,
    QuestionCheckBoxWithOther,
    QuestionDemand,
    QuestionDistribution,
    QuestionFreeText,
    QuestionInterview,
    QuestionMultipleChoice,
    QuestionNumerical,
    SurveyMessage,
)
from edsl.surveys import Survey


@pytest.mark.parametrize("initial", ["uniform", "empty"])
def test_distribution_initial_state_is_humanize_only(initial):
    question = QuestionDistribution(
        question_name="forecast", question_text="Predict.", question_options=["a", "b"]
    )
    original = question.to_dict()
    validate_humanize_schema(
        Survey([question]),
        {"questions": {"forecast": {"initial_distribution": initial}}},
    )
    assert question.to_dict() == original


@pytest.mark.parametrize("initial", [None, "normal", True])
def test_distribution_rejects_invalid_initial_state(initial):
    question = QuestionDistribution.example()
    with pytest.raises(HumanizeSchemaValidationError):
        validate_humanize_schema(
            Survey([question]),
            {"questions": {question.question_name: {"initial_distribution": initial}}},
        )


def test_distribution_initial_state_default_and_question_type():
    model = QUESTION_TYPE_TO_HUMANIZE_CLASS["distribution"]
    assert model().initial_distribution == "uniform"
    assert model().model_dump(exclude_unset=True) == {}
    question = QuestionFreeText.example()
    with pytest.raises(HumanizeSchemaValidationError):
        validate_humanize_schema(
            Survey([question]),
            {"questions": {question.question_name: {"initial_distribution": "empty"}}},
        )


@pytest.mark.parametrize("show", [True, False])
def test_distribution_optional_moments(show):
    question = QuestionDistribution.example()
    validate_humanize_schema(Survey([question]), {"questions": {question.question_name: {"show_moments": show}}})
    assert QUESTION_TYPE_TO_HUMANIZE_CLASS["distribution"]().show_moments is False


@pytest.mark.parametrize("show", [None, "true", 1])
def test_distribution_moments_requires_boolean(show):
    question = QuestionDistribution.example()
    with pytest.raises(HumanizeSchemaValidationError):
        validate_humanize_schema(Survey([question]), {"questions": {question.question_name: {"show_moments": show}}})


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


class TestValidateHumanizeSchemaTimeLimit:
    """The per-question time limit."""

    SUPPORTED_TYPES = [
        "free_text",
        "budget",
        "checkbox",
        "checkbox_with_other",
        "file_upload",
        "likert_five",
        "linear_scale",
        "list",
        "matrix",
        "multiple_choice",
        "multiple_choice_with_other",
        "numerical",
        "rank",
        "top_k",
        "yes_no",
    ]

    @staticmethod
    def _survey() -> Survey:
        return Survey(
            [
                QuestionFreeText(
                    question_name="q1",
                    question_text="How are you?",
                ),
            ]
        )

    @staticmethod
    def _schema(time_limit) -> dict:
        return {"questions": {"q1": {"time_limit": time_limit}}}

    @pytest.mark.parametrize("seconds", [30, 300, 7200])
    def test_fixed_duration_within_bounds_passes(self, seconds):
        """Both bounds are inclusive."""
        time_limit = {"duration": {"type": "fixed", "seconds": seconds}}
        validate_humanize_schema(self._survey(), self._schema(time_limit))

    @pytest.mark.parametrize("seconds", [0, 29, 7201])
    def test_fixed_duration_out_of_bounds_raises(self, seconds):
        time_limit = {"duration": {"type": "fixed", "seconds": seconds}}
        with pytest.raises(HumanizeSchemaValidationError) as exc_info:
            validate_humanize_schema(self._survey(), self._schema(time_limit))
        assert "seconds" in str(exc_info.value).lower()

    def test_null_time_limit_passes(self):
        """Null is how an author says there is no limit."""
        validate_humanize_schema(self._survey(), self._schema(None))

    def test_untagged_duration_raises(self):
        """The type tag is required, even though "fixed" is its only value."""
        time_limit = {"duration": {"seconds": 300}}
        with pytest.raises(HumanizeSchemaValidationError) as exc_info:
            validate_humanize_schema(self._survey(), self._schema(time_limit))
        assert "type" in str(exc_info.value).lower()

    def test_unknown_duration_type_raises(self):
        time_limit = {"duration": {"type": "per_respondent", "seconds": 300}}
        with pytest.raises(HumanizeSchemaValidationError):
            validate_humanize_schema(self._survey(), self._schema(time_limit))

    def test_duration_without_seconds_raises(self):
        """A limit whose duration was never chosen is not a limit."""
        time_limit = {"duration": {"type": "fixed"}}
        with pytest.raises(HumanizeSchemaValidationError) as exc_info:
            validate_humanize_schema(self._survey(), self._schema(time_limit))
        assert "seconds" in str(exc_info.value).lower()

    def test_time_limit_without_duration_raises(self):
        with pytest.raises(HumanizeSchemaValidationError) as exc_info:
            validate_humanize_schema(self._survey(), self._schema({}))
        assert "duration" in str(exc_info.value).lower()

    def test_flat_seconds_raises(self):
        """Seconds belong inside ``duration``, not directly on the time limit."""
        time_limit = {"seconds": 300}
        with pytest.raises(HumanizeSchemaValidationError):
            validate_humanize_schema(self._survey(), self._schema(time_limit))

    @pytest.mark.parametrize("question_type", SUPPORTED_TYPES)
    def test_supported_question_types_accept_a_time_limit(self, question_type):
        """Read off each type's model rather than a parsed schema: the union would
        accept the entry for whichever type fits first, not the one under test.
        """
        model_class = QUESTION_TYPE_TO_HUMANIZE_CLASS[question_type]
        parsed = model_class.model_validate(
            {"time_limit": {"duration": {"type": "fixed", "seconds": 300}}}
        )
        assert parsed.time_limit.duration.seconds == 300

    @pytest.mark.parametrize(
        "question_type",
        sorted(set(QUESTION_TYPE_TO_HUMANIZE_CLASS) - set(SUPPORTED_TYPES)),
    )
    def test_other_question_types_reject_a_time_limit(self, question_type):
        """Interviews, background questions and survey messages have no field for one."""
        model_class = QUESTION_TYPE_TO_HUMANIZE_CLASS[question_type]
        with pytest.raises(ValidationError):
            model_class.model_validate(
                {"time_limit": {"duration": {"type": "fixed", "seconds": 300}}}
            )

    def test_interview_raises(self):
        """The same rejection, through validate_humanize_schema."""
        survey = Survey(
            [
                QuestionInterview(
                    question_name="q1",
                    question_text="Tell me about your experience.",
                    interview_guide="Ask follow-up questions about details.",
                ),
            ]
        )
        time_limit = {"duration": {"type": "fixed", "seconds": 300}}
        with pytest.raises(HumanizeSchemaValidationError) as exc_info:
            validate_humanize_schema(survey, self._schema(time_limit))
        assert "time_limit" in str(exc_info.value).lower()

    def test_group_presentation_accepts_a_time_limit(self):
        """Under group presentation a question's limit is ignored, not rejected."""
        survey = self._survey()
        survey.add_question_group("q1", "q1", "page_0")
        humanize_schema = {
            **self._schema({"duration": {"type": "fixed", "seconds": 300}}),
            "survey": {"presentation": "group"},
        }
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


class TestSurveyBranding:
    """The logo a survey draws in its banner, under survey.branding.

    Only the shape is checked here. Whether the asset exists and this author may
    use it needs the server, which checks it when the schema is written.
    """

    ASSET_UUID = "3f8b1c2e-0000-4a0b-8c1d-2e3f4a5b6c7d"

    def survey(self):
        return Survey(
            [QuestionFreeText(question_name="q1", question_text="How are you?")]
        )

    def schema(self, **logo):
        return {
            "questions": {},
            "survey": {
                "branding": {
                    "logo": {
                        "source": {"type": "asset", "asset_uuid": self.ASSET_UUID},
                        "alt": "Lab name",
                        **logo,
                    }
                }
            },
        }

    def test_a_logo_passes(self):
        validate_humanize_schema(self.survey(), self.schema())

    def test_each_position_passes(self):
        for position in ("left", "center", "right"):
            validate_humanize_schema(self.survey(), self.schema(position=position))

    def test_position_defaults_to_left(self):
        """Omitting position is not an error; the frontend default applies."""
        validated = HumanizeSchema.model_validate(self.schema())
        assert validated.survey.branding.logo.position == "left"

    def test_a_decorative_logo_passes(self):
        """An empty alt is how a logo is marked decorative."""
        validate_humanize_schema(self.survey(), self.schema(alt=""))

    def test_branding_without_a_logo_passes(self):
        schema = {"questions": {}, "survey": {"branding": {"logo": None}}}
        validate_humanize_schema(self.survey(), schema)

    def test_branding_is_optional(self):
        """Every schema written before branding existed stays valid."""
        validated = HumanizeSchema.model_validate({"questions": {}, "survey": {}})
        assert validated.survey.branding is None

    def test_a_logo_without_alt_raises(self):
        """alt is required, so leaving it out is a decision rather than an accident."""
        schema = self.schema()
        del schema["survey"]["branding"]["logo"]["alt"]
        with pytest.raises(HumanizeSchemaValidationError):
            validate_humanize_schema(self.survey(), schema)

    def test_a_logo_without_a_source_raises(self):
        schema = self.schema()
        del schema["survey"]["branding"]["logo"]["source"]
        with pytest.raises(HumanizeSchemaValidationError):
            validate_humanize_schema(self.survey(), schema)

    def test_an_unknown_source_type_raises(self):
        """An asset in the author's library is the only source today."""
        schema = self.schema()
        schema["survey"]["branding"]["logo"]["source"] = {
            "type": "url",
            "url": "https://example.com/logo.png",
        }
        with pytest.raises(HumanizeSchemaValidationError):
            validate_humanize_schema(self.survey(), schema)

    def test_a_malformed_asset_uuid_raises(self):
        """Caught here rather than by the server."""
        schema = self.schema()
        schema["survey"]["branding"]["logo"]["source"]["asset_uuid"] = "not-a-uuid"
        with pytest.raises(HumanizeSchemaValidationError):
            validate_humanize_schema(self.survey(), schema)

    def test_an_invalid_position_raises(self):
        with pytest.raises(HumanizeSchemaValidationError):
            validate_humanize_schema(self.survey(), self.schema(position="middle"))

    def test_an_extra_field_in_the_logo_raises(self):
        """Sizing is done in custom_css, not by a field the server would ignore."""
        with pytest.raises(HumanizeSchemaValidationError):
            validate_humanize_schema(self.survey(), self.schema(width=200))

    def test_alt_is_stripped(self):
        validated = HumanizeSchema.model_validate(self.schema(alt="  Lab name  "))
        assert validated.survey.branding.logo.alt == "Lab name"

    def test_an_overlong_alt_raises(self):
        with pytest.raises(HumanizeSchemaValidationError):
            validate_humanize_schema(self.survey(), self.schema(alt="x" * 201))
