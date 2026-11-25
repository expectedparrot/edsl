import pytest

from edsl import Instruction, QuestionFreeText, Survey
from edsl.surveys import EndOfSurvey


def _question(name):
    return QuestionFreeText(question_name=name, question_text=name)


def _back_schema(boundary=None):
    schema = {"survey": {"navigation": {"back_button": True}}, "questions": {}}
    if boundary:
        schema["questions"][boundary] = {"navigation": {"allow_back_past": False}}
    return schema


def test_back_disabled_by_default():
    session = Survey([_question("q0"), _question("q1")]).start_session()
    session.answer("q0", "a")
    session.forward()
    assert not session.can_back()
    with pytest.raises(RuntimeError, match="not available"):
        session.back()


def test_linear_back_forward_and_answer_revisions():
    session = Survey([_question("q0"), _question("q1")]).start_session(_back_schema())
    session.answer("q0", "first")
    assert session.forward().question_name == "q1"
    assert session.back().question_name == "q0"
    session.answer("q0", "revised")
    assert session.forward().question_name == "q1"
    assert session.final_answers() == {"q0": "revised"}
    assert session.navigation_history()[-2]["revision"] == 2


def test_branch_change_invalidates_old_answer():
    q0, car, transit = _question("q0"), _question("car"), _question("transit")
    survey = Survey([q0, car, transit]).add_rule(q0, "{{ q0.answer }} == 'no'", transit)
    session = survey.start_session(_back_schema())
    session.answer("q0", "no")
    assert session.forward().question_name == "transit"
    session.answer("transit", "bus")
    session.back()
    session.answer("q0", "yes")
    assert session.forward().question_name == "car"
    assert session.final_answers() == {"q0": "yes"}
    assert session.inactive_answers()["transit"] == {
        "answer": "bus",
        "revision": 1,
        "reason": "path_truncated",
    }
    assert {
        "event": "invalidate",
        "question": "transit",
        "reason": "path_truncated",
    } in session.final_result_metadata()["humanize_navigation"]["events"]


def test_back_boundary_allows_return_to_boundary_but_not_crossing_it():
    session = Survey(
        [_question("before"), _question("consent"), _question("after")]
    ).start_session(_back_schema("consent"))
    session.answer("before", True)
    session.forward()
    session.answer("consent", True)
    session.forward()
    assert session.back().question_name == "consent"
    assert not session.can_back()


def test_back_from_end_and_instructions():
    survey = Survey([Instruction(name="intro", text="Welcome"), _question("q0")])
    session = survey.start_session(_back_schema())
    assert session.current_name == "intro"
    session.forward()
    session.answer("q0", "done")
    assert session.forward() is EndOfSurvey
    assert session.back().question_name == "q0"


def test_first_answer_after_return_recomputes_the_route():
    q0, q1, q2, q3 = (_question(name) for name in ("q0", "q1", "q2", "q3"))
    survey = Survey([q0, q1, q2, q3]).add_rule(
        q1, "{{ q1.answer }} == 'skip'", q3
    )
    session = survey.start_session(_back_schema())
    assert session.forward().question_name == "q1"
    assert session.forward().question_name == "q2"  # q1 was left unanswered
    assert session.back().question_name == "q1"
    session.answer("q1", "skip")
    assert session.forward().question_name == "q3"


def test_null_navigation_settings_use_defaults():
    schema = {
        "survey": {"navigation": None},
        "questions": {"q0": {"navigation": None}},
    }
    session = Survey([_question("q0"), _question("q1")]).start_session(schema)
    session.answer("q0", "a")
    session.forward()
    assert not session.can_back()


def test_mutated_answer_values_are_copied_before_comparison():
    q0, q1, q2 = (_question(name) for name in ("q0", "q1", "q2"))
    session = Survey([q0, q1, q2]).start_session(_back_schema())
    value = ["first"]
    session.answer("q0", value)
    session.forward()
    session.forward()
    session.back()
    session.back()
    value[0] = "revised"
    session.answer("q0", value)
    assert session.active_path == [q0]
    assert session.answer_records["q0"][-1]["answer"] == ["revised"]
