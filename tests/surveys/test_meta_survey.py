"""Tests for Survey.to_meta_survey() conversion fidelity.

Covers the four correctness fixes to the mechanical conversion:
  - rule priority is honored when deriving skip conditions (ambiguous flows
    are rejected, not silently mislabeled);
  - dynamically piped response options (list, string, or mapping form) are
    rejected before conversion;
  - linear-scale option_labels are carried into the prompt;
  - checkbox prompts include the full choice list and selection limits.
"""

import pytest

from edsl import Survey
from edsl.questions import (
    QuestionCheckBox,
    QuestionFreeText,
    QuestionLinearScale,
    QuestionMultipleChoice,
    QuestionYesNo,
)


def test_linear_scale_prompt_includes_option_labels():
    q = QuestionLinearScale(
        question_name="like",
        question_text="How much do you like it?",
        question_options=[1, 2, 3, 4, 5],
        option_labels={1: "dislike", 5: "like"},
    )
    meta = Survey([q]).to_meta_survey()
    text = meta.questions[0].question_text
    # Labels present so the scale has meaning, numeric keys preserved as outcomes.
    assert "dislike" in text and "like" in text
    assert "[1" in text or "'1'" in text


def test_checkbox_prompt_includes_full_choices_and_selection_limits():
    q = QuestionCheckBox(
        question_name="snacks",
        question_text="Which snacks would you buy?",
        question_options=["chips", "nuts", "fruit", "candy"],
        min_selections=1,
        max_selections=2,
    )
    meta = Survey([q]).to_meta_survey()
    # One binary distribution per option, each carrying the whole choice set.
    assert len(meta.questions) == 4
    first = meta.questions[0].question_text
    assert "chips" in first and "candy" in first  # competing choices present
    assert "at least 1" in first and "at most 2" in first  # selection limits present


def test_dynamic_options_list_is_rejected():
    q = QuestionMultipleChoice(
        question_name="a",
        question_text="Pick one",
        question_options=["fixed", "{{ piped }}"],
    )
    with pytest.raises(ValueError, match="dynamically piped"):
        Survey([q]).to_meta_survey()


def test_dynamic_options_template_string_is_rejected():
    q = QuestionMultipleChoice(
        question_name="b", question_text="Pick one", question_options=["a", "b"]
    )
    q.question_options = "{{ choices }}"  # whole-options template form
    with pytest.raises(ValueError, match="dynamically piped"):
        Survey([q]).to_meta_survey()


def test_dynamic_options_mapping_is_rejected():
    q = QuestionMultipleChoice(
        question_name="c", question_text="Pick one", question_options=["a", "b"]
    )
    q.question_options = {"from": "{{ choices }}", "add": ["Other"]}  # combine form
    with pytest.raises(ValueError, match="dynamically piped"):
        Survey([q]).to_meta_survey()


def test_single_skip_rule_still_converts():
    # A lone skip/stop rule competes only with the default fall-through, so it is
    # an unambiguous skip condition and must convert cleanly.
    survey = Survey(
        [
            QuestionYesNo(question_name="q0", question_text="Continue?"),
            QuestionFreeText(question_name="q1", question_text="Why?"),
        ]
    ).add_stop_rule("q0", "{{ q0.answer }} == 'No'")
    meta = survey.to_meta_survey()
    assert len(meta.questions) >= 2


def test_priority_conflicting_jump_is_rejected():
    # Two rules at q0 with the same condition: a lower-priority one jumps past q1,
    # a higher-priority one routes into q1. The source population reaches q1, so a
    # naive reading would mislabel it as skipped. The conversion must refuse.
    survey = Survey(
        [
            QuestionMultipleChoice(
                question_name="q0", question_text="?", question_options=["Yes", "No"]
            ),
            QuestionFreeText(question_name="q1", question_text="?"),
            QuestionFreeText(question_name="q2", question_text="?"),
            QuestionFreeText(question_name="q3", question_text="?"),
        ]
    )
    survey = survey.add_rule("q0", "{{ q0.answer }} == 'Yes'", "q3")  # lower priority
    survey = survey.add_rule("q0", "{{ q0.answer }} == 'Yes'", "q1")  # higher priority
    with pytest.raises(ValueError, match="faithfully derive the skip"):
        survey.to_meta_survey()
