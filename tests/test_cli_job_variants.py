import json

from click.testing import CliRunner

from edsl import Agent, Model, QuestionMultipleChoice, Scenario, Survey
from edsl.__main__ import app


def invoke(*args, code=0):
    result = CliRunner().invoke(app, ["jobs", *map(str, args)])
    assert result.exit_code == code, result.output
    body = json.loads(result.stdout)
    return body["data" if code == 0 else "error"]


def test_rehearse_the_actual_versions(tmp_path):
    question = QuestionMultipleChoice(
        question_name="count",
        question_text="How many activities?",
        question_options="{{ scenario.options }}",
        include_comment=False,
    )
    job = (
        Survey([question])
        .by(Agent(name="E1"), Agent(name="E2"))
        .by(
            Scenario(arm="long", options=["0", "1", "2", "3", "4", "5"]),
            Scenario(arm="short", options=["0", "1", "2", "3", "4"]),
        )
        .by(Model("test"))
    )
    path = tmp_path / "job.ep"
    job.git.save(path, sync_coop=False)
    args = (
        "variants",
        path,
        "--group-by",
        "scenario.arm",
        "--unique-by",
        "agent.name",
        "--expect-interviews",
        2,
    )
    assert "scenario.arm" in invoke("variants", path)["available_fields"]
    detail = invoke(*args, code=5)["details"][0]
    assert (detail["planned_interviews"], detail["duplicate_keys"]) == (4, 2)
    assert (
        invoke("variants", path, "--unique-by", "scenario.missing", code=5)["code"]
        == "VALIDATION_ERROR"
    )
    assert (
        invoke(
            "variants", path, "--unique-by", "agent.name", "--unique-by", "scenario.arm"
        )["unique_keys"]
        == 4
    )

    job.zip_assign()
    paired = tmp_path / "paired.ep"
    job.git.save(paired, sync_coop=False)
    assignment = invoke(*[paired if arg == path else arg for arg in args])
    assert assignment["planned_interviews"] == assignment["unique_keys"] == 2
    for group in assignment["groups"]:
        assert group["interviews"] == 1
        index = group["interview_index"]
        is_short = group["values"]["scenario.arm"] == "short"
        prompt = invoke(
            "preview-prompt",
            paired,
            "count",
            "--interview-index",
            index,
            "--expect-comments",
            "false",
        )
        assert prompt["include_comment"] is False
        case = ("test-case", paired, "--interview-index", index)
        invoke(*case, "--responses", '{"count":"4"}', "--expect", '{"count":"4"}')
        reject = (*case, "--responses", '{"count":"5"}', "--expect-rejection", "count")
        if is_short:
            assert invoke(*reject)["validation_rejected"]
            assert (
                invoke(*reject, "-o", tmp_path / "invalid.ep", code=2)["code"]
                == "USAGE_ERROR"
            )
        else:
            invoke(*case, "--responses", '{"count":"5"}', "--expect", '{"count":"5"}')
            assert not invoke(*reject, code=5)["details"][0]["validation_rejected"]
        assert (
            invoke(
                "preview-prompt", paired, "count", "--expect-comments", "true", code=5
            )["code"]
            == "PROMPT_COMMENT_MISMATCH"
        )


def test_skipped_reply_is_not_a_validation_rejection(tmp_path):
    survey = Survey(
        [
            QuestionMultipleChoice(
                question_name=name,
                question_text="Continue?",
                question_options=["yes", "no"],
            )
            for name in ("first", "later")
        ]
    )
    survey.add_stop_rule("first", "{{ first.answer }} == 'no'")
    job = survey.by(Model("test"))
    path = tmp_path / "skip.ep"
    job.git.save(path, sync_coop=False)
    err = invoke(
        "test-case",
        path,
        "--responses",
        '{"first":"no","later":"bad"}',
        "--expect-rejection",
        "later",
        code=5,
    )
    assert err["details"][0]["validation_rejected"] is False
