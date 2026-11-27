"""Edit real local packages through the same commands a coding agent runs."""

import json

from click.testing import CliRunner

from edsl import QuestionFreeText, QuestionMultipleChoice, Survey
from edsl.__main__ import app
from edsl.base.git_accessor import GitBackedInstanceAccessor


def invoke(*args, success=True):
    result = CliRunner().invoke(app, list(map(str, args)))
    assert (result.exit_code == 0) == success, result.output
    envelope = json.loads(result.output)
    assert envelope["status"] == ("ok" if success else "error")
    return envelope


def test_local_update_preserves_history_routing_and_memory(tmp_path, monkeypatch):
    path = tmp_path / "intake.ep"
    original = Survey.example().set_full_memory_mode()
    initial = original.git.save(path)["commit"]

    def reject_sync(*args, **kwargs):
        raise AssertionError("Local editing contacted Coop")

    monkeypatch.setattr(
        GitBackedInstanceAccessor, "_coop_pull_if_remote_updated", reject_sync
    )
    invoke("surveys", "update-question", path, "q0", "--question-text", "Enjoy school?")
    edited = Survey.git.load(path, sync_coop=False)
    assert edited.memory_plan.to_dict()["survey_question_texts"][0] == "Enjoy school?"
    assert edited.rule_collection.to_dict() == original.rule_collection.to_dict()
    assert (
        edited.questions[0].question_options == original.questions[0].question_options
    )
    assert Survey.git.load(path, ref=initial).questions[0] == original.questions[0]

    before = path.read_bytes()
    invoke(
        "surveys",
        "update-question",
        path,
        "q0",
        "--patch",
        '{"question_name":"other"}',
        success=False,
    )
    assert path.read_bytes() == before


def test_rename_distinguishes_references_and_literals(tmp_path):
    source = tmp_path / "source.ep"
    destination = tmp_path / "edited.ep"
    survey = Survey(
        [
            QuestionMultipleChoice(
                question_name="method",
                question_text="Method?",
                question_options=["method", "other"],
            ),
            QuestionFreeText(
                question_name="detail",
                question_text="About {{ method.answer | lower }} and {{ scenario.method }}",
            ),
        ]
    )
    survey.add_skip_rule("detail", "{{ method.answer }} == 'method'")
    survey.git.save(source)
    before = source.read_bytes()
    invoke("surveys", "rename-question", source, "method", "mode", "-o", destination)
    edited = Survey.git.load(destination, sync_coop=False)
    assert edited.get("mode").question_options == ["method", "other"]
    assert (
        edited.get("detail").question_text
        == "About {{ mode.answer | lower }} and {{ scenario.method }}"
    )
    assert (
        edited.rule_collection.non_default_rules[0].expression
        == "{{ mode.answer }} == 'method'"
    )
    assert source.read_bytes() == before


def test_insert_group_and_check_both_respondent_paths(tmp_path):
    package = tmp_path / "survey.ep"
    settings = tmp_path / "browser.json"
    survey = Survey(
        [
            QuestionMultipleChoice(
                question_name="channel",
                question_text="Where?",
                question_options=["Store", "Online"],
            ),
            QuestionFreeText(question_name="notes", question_text="Any notes?"),
        ]
    )
    survey.add_question_group("notes", "notes", "finish")
    survey.git.save(package)
    invoke(
        "surveys",
        "add-question",
        package,
        "--question-type",
        "free_text",
        "--question-name",
        "receipt",
        "--question-text",
        "Receipt number?",
        "--index",
        "1",
    )
    assert Survey.git.load(package, sync_coop=False).question_groups["finish"] == (2, 2)
    invoke(
        "surveys",
        "add-skip-rule",
        package,
        "--question",
        "receipt",
        "--expression",
        "{{ channel.answer }} == 'Online'",
    )
    invoke(
        "surveys",
        "set-groups",
        package,
        "--groups",
        json.dumps(
            {
                "start": ["channel", "channel"],
                "details": ["receipt", "receipt"],
                "finish": ["notes", "notes"],
            }
        ),
    )
    base = tmp_path / "original.json"
    base.write_text('{"questions":{"notes":{"optional":true}}}')
    invoke(
        "humanize",
        "schema",
        "create",
        "--survey",
        package,
        "--base-schema",
        base,
        "--presentation",
        "group",
        "--optional",
        "receipt",
        "--output",
        settings,
    )
    assert json.loads(settings.read_text())["questions"]["notes"] == {"optional": True}
    paths = {
        "store": [
            {"page": ["channel"], "answers": {"channel": "Store"}},
            {"page": ["receipt"]},
            {"page": ["notes"]},
        ],
        "online": [
            {"page": ["channel"], "answers": {"channel": "Online"}},
            {"page": ["notes"]},
        ],
    }
    result = invoke(
        "surveys",
        "check-paths",
        package,
        "--schema",
        settings,
        "--paths",
        json.dumps(paths),
    )
    assert result["data"]["passed_paths"] == ["store", "online"]
    paths["store"].pop(1)
    result = invoke(
        "surveys",
        "check-paths",
        package,
        "--schema",
        settings,
        "--paths",
        json.dumps(paths),
        success=False,
    )
    assert "store, page 2" in result["error"]["message"]
