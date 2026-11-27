"""Verify scripted interviews using the real option renderer and validators."""

import json

from click.testing import CliRunner

from edsl import (
    Agent,
    Jobs,
    Model,
    QuestionBudget,
    QuestionCheckBox,
    QuestionFreeText,
    Results,
    Scenario,
    Survey,
)
from edsl.__main__ import app


def test_scripted_case_preserves_selected_assignment_and_validates_replies(tmp_path):
    q = QuestionCheckBox(
        question_name="choices",
        question_text="Choose two in {{ scenario.city }}.",
        question_options="{{ scenario.menu }}",
        min_selections=2,
        max_selections=2,
    )
    budget = QuestionBudget(
        question_name="allocation",
        question_text="Allocate.",
        question_options="{{ choices.answer }}",
        budget_sum=100,
    )
    survey = Survey([q, budget])
    job = (
        survey.by(Agent(name="resident"))
        .by(
            Scenario({"city": "A", "menu": ["tea", "soup"]}),
            Scenario({"city": "B", "menu": ["bus", "rail", "walk"]}),
        )
        .by(Model("test"))
    )
    path = tmp_path / "study.ep"
    job.git.save(path, sync_coop=False)
    original = path.read_bytes()
    replies = {"choices": ["rail", "walk"], "allocation": [0, 100]}
    expected = {"choices": ["rail", "walk"], "allocation": [{"rail": 0}, {"walk": 100}]}
    runner = CliRunner()
    args = [
        "jobs",
        "test-case",
        str(path),
        "--interview-index",
        "1",
        "--responses",
        json.dumps(replies),
    ]
    output = tmp_path / "checks" / "b.ep"
    good = runner.invoke(
        app, [*args, "--expect", json.dumps(expected), "-o", str(output)]
    )
    assert good.exit_code == 0, good.output
    assert json.loads(good.output)["data"]["answers"] == expected
    saved = Results.git.load(output, sync_coop=False)
    r = saved[0]
    assert r.model.model == "test" and r.agent.name == "resident"
    assert r.indices["scenario"] == 1 and r.scenario["city"] == "B"
    assert r.answer == expected
    assert isinstance(
        r.get("raw_model_response")["allocation_raw_model_response"], dict
    )

    # Wrong amounts and swapped labels must fail without replacing a prior passing artifact.
    stored = output.read_bytes()
    diff = runner.invoke(
        app,
        [
            *args,
            "--expect",
            '{"allocation":[{"rail":100},{"walk":0}]}',
            "-o",
            str(output),
        ],
    )
    assert (
        diff.exit_code == 5
        and "allocation" in json.loads(diff.output)["error"]["details"][0]["mismatches"]
    )
    invalid = runner.invoke(
        app,
        [
            *args[:-1],
            json.dumps({**replies, "allocation": [25, 25]}),
            "-o",
            str(output),
        ],
    )
    assert (
        invalid.exit_code == 5
        and "allocation"
        in json.loads(invalid.stdout)["error"]["details"][0]["failed_questions"]
    )
    assert output.read_bytes() == stored and path.read_bytes() == original


def test_skip_does_not_need_a_reply_and_unanswered_live_question_fails(tmp_path):
    a = QuestionFreeText(question_name="consent", question_text="Continue?")
    b = QuestionFreeText(question_name="reason", question_text="Why?")
    survey = Survey([a, b])
    survey.add_stop_rule("consent", "{{ consent.answer }} == 'No'")
    p = tmp_path / "consent.ep"
    survey.by(Model("test")).git.save(p, sync_coop=False)
    runner = CliRunner()
    cmd = ["jobs", "test-case", str(p), "--responses"]
    assert runner.invoke(app, [*cmd, '{"consent":"No"}']).exit_code == 0
    missing = runner.invoke(app, [*cmd, '{"consent":"Yes"}'])
    assert missing.exit_code == 5 and json.loads(missing.stdout)["error"]["details"][0][
        "missing_responses"
    ] == ["reason"]
    assert runner.invoke(app, [*cmd, '{"typo":"Yes"}']).exit_code == 2
    assert runner.invoke(app, [*cmd, "{}", "-o", str(p)]).exit_code == 2


def test_override_uses_scripted_model_and_remains_local(tmp_path, monkeypatch):
    import socket
    from edsl.questions import thinking_question

    q = thinking_question(
        QuestionFreeText(question_name="review", question_text="Review the case."),
        model=Model("test", canned_response="wrong question-model reply"),
        system_prompt="Be brief.",
    )
    path = tmp_path / "review.ep"
    Survey([q]).by(Model("test", canned_response="wrong job-model reply")).git.save(
        path, sync_coop=False
    )
    source = path.read_bytes()
    connections = []

    def offline(self, address):
        connections.append(str(address))
        raise RuntimeError("offline")

    monkeypatch.setattr(socket.socket, "connect", offline)
    argv = [
        "jobs",
        "test-case",
        str(path),
        "--responses",
        '{"review":"assigned reply"}',
        "--expect",
        '{"review":"assigned reply"}',
    ]
    result = CliRunner().invoke(app, argv)
    assert result.exit_code == 0, result.stdout
    assert not connections
    assert path.read_bytes() == source
