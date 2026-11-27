"""Check actual CLI envelopes and routing on reopened local surveys."""

import json

import pytest
from click.testing import CliRunner

from edsl import Question, Survey
from edsl.__main__ import app
from edsl.base.git_accessor import GitBackedInstanceAccessor


def question(name, kind="free_text", **options):
    return Question(kind, question_name=name, question_text=name + "?", **options)


def check(survey_path, cases):
    path = survey_path.parent / "paths.json"
    path.write_text(json.dumps({"cases": cases}))
    reply = CliRunner().invoke(
        app, ["surveys", "check-paths", str(survey_path), "--cases", str(path)]
    )
    return reply.exit_code, json.loads(reply.output)


def case(name, expected, **answers):
    return {"name": name, "expected_path": expected, "answers": answers}


def test_reports_first_divergence_for_each_failure_and_checks_end(
    tmp_path, monkeypatch
):
    survey = Survey(
        [
            question("consent", "multiple_choice", question_options=["Yes", "No"]),
            question("rating", "numerical"),
            question("urgent"),
            question("routine"),
            question("closing"),
        ]
    )
    survey.add_stop_rule("consent", "{{ consent.answer }} == 'No'")
    survey.add_rule("rating", "{{ rating.answer }} <= 3", "urgent")
    # The more general rule wins. It makes a realistic broken fixture.
    survey.add_rule("rating", "{{ rating.answer }} <= 6", "routine")
    path = tmp_path / "triage.ep"
    survey.git.save(path, sync_coop=False)
    original = path.read_bytes()

    def reject_sync(*args, **kwargs):
        pytest.fail("check-paths contacted Coop")

    monkeypatch.setattr(
        GitBackedInstanceAccessor, "_coop_pull_if_remote_updated", reject_sync
    )
    declined = case("declines", ["consent"], consent="No")
    code, result = check(
        path,
        [
            declined,
            case(
                "zero",
                ["consent", "rating", "urgent", "closing"],
                consent="Yes",
                rating=0,
            ),
            case(
                "too short", ["consent", "rating", "routine"], consent="Yes", rating=3.5
            ),
            case("too long", ["consent", "rating"], consent="No"),
        ],
    )
    assert code == 5
    err = result["error"]
    assert err["code"] == "PATH_CHECK_FAILED" and "3 of 4" in err["message"]
    assert [
        (r["name"], r["after"], r["expected"], r["actual"]) for r in err["details"]
    ] == [
        ("zero", "rating", "urgent", "routine"),
        ("too short", "routine", None, "closing"),
        ("too long", "consent", "rating", None),
    ]
    code, result = check(
        path,
        [
            declined,
            case(
                "routine",
                ["consent", "rating", "routine", "closing"],
                consent="Yes",
                rating=3.5,
            ),
        ],
    )
    assert code == 0 and result["data"]["passed"] == 2
    assert result["data"]["cases"][1]["visited"] == [
        "consent",
        "rating",
        "routine",
        "closing",
    ]
    assert path.read_bytes() == original


def test_context_first_skip_and_answers_from_skipped_questions(tmp_path):
    path = tmp_path / "context.ep"
    survey = Survey([question("intro"), question("detail"), question("end")])
    survey.add_skip_rule("intro", "'{{ scenario.region }}' == 'West'")
    survey.add_stop_rule("detail", "'{{ agent.role }}' == 'manager'")
    survey.git.save(path, sync_coop=False)
    first = {
        **case("west manager", ["detail"]),
        "scenario": {"region": "West"},
        "agent": {"role": "manager"},
    }
    second = {
        **case("east staff", ["intro", "detail", "end"]),
        "scenario": {"region": "East"},
        "agent": {"role": "staff"},
    }
    assert check(path, [first, second])[0] == 0

    other = tmp_path / "skipped.ep"
    survey = Survey(
        [question("enter"), question("skipme"), question("follow"), question("end")]
    )
    survey.add_skip_rule("skipme", "True")
    survey.add_skip_rule("follow", "{{ skipme.answer }} == 'skip'")
    survey.git.save(other, sync_coop=False)
    assert (
        check(
            other, [case("unused answer", ["enter", "follow", "end"], skipme="skip")]
        )[0]
        == 0
    )


def test_missing_routing_answer_cannot_pass_by_default(tmp_path):
    survey = Survey([question("signed"), question("end")])
    survey.add_stop_rule("signed", "{{ signed.answer }} == 'no'")
    path = tmp_path / "unchecked.ep"
    survey.git.save(path, sync_coop=False)
    code, result = check(path, [case("missing", ["signed", "end"])])
    assert code == 5 and "Supply an answer" in result["error"]["details"][0]["message"]


@pytest.mark.parametrize(
    "cases",
    [
        [],
        [{"name": "bad", "expected_path": "consent"}],
        [{"name": "bad", "expected_path": [], "typo": {}}],
    ],
)
def test_invalid_cases(tmp_path, cases):
    path = tmp_path / "survey.ep"
    Survey.example().git.save(path, sync_coop=False)
    code, result = check(path, cases)
    assert code == 2 and result["error"]["code"] == "INVALID_PATH_CASES"


def test_empty_and_randomized_surveys(tmp_path):
    empty = tmp_path / "empty.ep"
    Survey([]).git.save(empty, sync_coop=False)
    assert check(empty, [case("empty", [])])[0] == 0
    randomized = Survey([question("a"), question("b")])
    randomized.randomize_question_order("pair", ["a", "b"])
    path = tmp_path / "random.ep"
    randomized.git.save(path, sync_coop=False)
    assert (
        check(path, [case("fixed", ["a", "b"])])[1]["error"]["code"]
        == "UNSUPPORTED_ROUTING"
    )


def test_choose_question_or_group_mode(tmp_path):
    path = tmp_path / "test.ep"
    Survey.example().git.save(path, sync_coop=False)
    for flags in [
        [],
        ["--paths", "{}"],
        ["--schema", str(path)],
        ["--cases", str(path), "--paths", "{}"],
    ]:
        result = CliRunner().invoke(app, ["surveys", "check-paths", str(path), *flags])
        assert (
            result.exit_code == 2
            and json.loads(result.output)["error"]["code"] == "USAGE_ERROR"
        )
