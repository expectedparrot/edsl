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
