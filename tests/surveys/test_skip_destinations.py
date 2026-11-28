import pytest

from edsl import Instruction, Model, QuestionFreeText, Survey
from edsl.surveys.base import EndOfSurvey


def question(name):
    return QuestionFreeText(question_name=name, question_text=name + "?")


@pytest.mark.parametrize("round_trip", [False, True])
def test_navigator_uses_before_rule_destination(round_trip, tmp_path):
    survey = Survey(
        [question(n) for n in ("eligibility", "detail", "followup", "closing")]
    )
    survey.add_rule(
        "detail", "{{ eligibility.answer }} == 'skip'", "closing", before_rule=True
    )
    if round_trip:
        path = tmp_path / "survey.ep"
        survey.git.save(path, sync_coop=False)
        survey = Survey.git.load(path, sync_coop=False)

    assert (
        survey.next_question("eligibility", {"eligibility.answer": "continue"}).name
        == "detail"
    )
    walk = survey.gen_path_through_survey()
    assert next(walk).name == "eligibility"
    assert walk.send({"eligibility.answer": "skip"}).name == "closing"
    with pytest.raises(StopIteration):
        walk.send({"closing.answer": "done"})


def test_chained_initial_skip_and_first_matching_destination():
    survey = Survey([question(n) for n in ("first", "second", "third", "fourth")])
    survey.add_rule("first", "True", "third", before_rule=True)
    survey.add_rule("first", "True", "second", before_rule=True)
    survey.add_rule("third", "True", EndOfSurvey, before_rule=True)
    assert survey.next_question() is EndOfSurvey
    assert list(survey.gen_path_through_survey()) == []


def test_instruction_inside_a_skip_resumes_at_destination():
    survey = Survey(
        [
            question("gate"),
            question("detail"),
            Instruction(name="notice", text="Notice"),
            question("followup"),
            question("closing"),
        ]
    )
    survey.add_rule("detail", "True", "closing", before_rule=True)
    answers = {"gate.answer": "skip"}
    assert survey.next_question_with_instructions("gate", answers).name == "notice"
    assert survey.next_question_with_instructions("notice", answers).name == "closing"


def test_group_skip_lands_in_middle_of_destination_page():
    survey = Survey(
        [question(n) for n in ("gate", "detail", "via", "followup", "closing")]
    )
    survey.question_groups = {"intro": (0, 0), "details": (1, 2), "last": (3, 4)}
    survey.add_rule("detail", "True", "closing", before_rule=True)
    assert survey.next_group("intro")["question_names"] == ["closing"]
    for navigate in (
        survey.next_question_group,
        survey.next_question_group_with_instructions,
    ):
        page, questions = navigate("gate")
        assert page == "last"
        assert [q.name for q in questions] == ["closing"]


def test_navigator_matches_answered_questions_from_local_job():
    survey = Survey(
        [question(n) for n in ("eligibility", "detail", "followup", "closing")]
    )
    survey.add_rule(
        "detail", "{{ eligibility.answer }} == 'skip'", "closing", before_rule=True
    )
    result = survey.by(Model("test", canned_response="skip")).run(
        cache=False, disable_remote_cache=True, disable_remote_inference=True
    )[0]
    walk = survey.gen_path_through_survey()
    visited = []
    q = next(walk)
    with pytest.raises(StopIteration):
        while True:
            visited.append(q.name)
            q = walk.send({f"{q.name}.answer": result.answer[q.name]})
    assert visited == ["eligibility", "closing"]
    assert set(visited) == {
        name for name, value in result.answer.items() if value is not None
    }
