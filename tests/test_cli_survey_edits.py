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


def test_compose_modules_preserves_boundaries_and_priors(tmp_path):
    from edsl.instructions import Instruction
    from edsl.surveys.base import EndOfSurvey

    def item(name):
        return QuestionFreeText(question_name=name, question_text=f"Describe {name}.")

    a = Survey(
        [
            Instruction(name="a_prompt", text="First module only."),
            item("consent"),
            item("details"),
        ]
    )
    b = Survey(
        [
            Instruction(name="b_prompt", text="Second module only."),
            item("used"),
            item("when"),
            item("why"),
        ]
    )
    a.add_stop_rule("consent", "{{ consent.answer }} == 'decline'")
    a.add_skip_rule("details", "{{ consent.answer }} == 'brief'")
    b.add_rule("used", "{{ used.answer }} == 'earlier'", "why")
    b.add_question_group("when", "why", "followups")
    b.add_targeted_memory("why", "used")
    path_a, path_b, dest = [
        tmp_path / name for name in ("first.ep", "second.ep", "both.ep")
    ]
    for survey, path in [(a, path_a), (b, path_b)]:
        survey.git.save(path, sync_coop=False)
    originals = [p.read_bytes() for p in (path_a, path_b)]
    response = invoke("surveys", "compose", path_a, path_b, "-o", dest)
    assert response["data"]["question_count"] == 5
    combined = Survey.git.load(dest, sync_coop=False)
    assert combined.question_names == a.question_names + b.question_names
    assert combined.questions == a.questions + b.questions
    assert combined.question_groups == {"followups": (3, 4)}
    assert (
        combined.next_question("consent", {"consent.answer": "decline"}) == EndOfSurvey
    )
    assert combined.next_question("consent", {"consent.answer": "brief"}).name == "used"
    assert combined.next_question("details", {}).name == "used"
    assert combined.next_question("used", {"used.answer": "earlier"}).name == "why"
    assert combined.memory_plan.to_dict()["data"] == {
        "why": {"prior_questions": ["used"]}
    }
    for name in combined.question_names:
        assert [i.name for i in combined._relevant_instructions_dict[name]] == [
            "a_prompt" if name in a.question_names else "b_prompt"
        ]
    assert originals == [p.read_bytes() for p in (path_a, path_b)]


def test_compose_name_collision_and_input_output_alias(tmp_path):
    source = tmp_path / "survey.ep"
    Survey.example().git.save(source, sync_coop=False)
    alias = tmp_path / "alias.ep"
    alias.symlink_to(source)
    content = source.read_bytes()
    collision = invoke(
        "surveys", "compose", source, alias, "-o", tmp_path / "new.ep", success=False
    )
    assert "rename-question" in collision["error"]["message"]
    assert not (tmp_path / "new.ep").exists()
    conflict = invoke("surveys", "compose", source, source, "-o", alias, success=False)
    assert conflict["error"]["code"] == "USAGE_ERROR"
    assert content == source.read_bytes()


def test_compose_retains_question_scoped_randomization_and_rejects_dual_sample_pools():
    import pytest

    from edsl.surveys.composition import compose_surveys

    def module(prefix):
        return Survey(
            [
                QuestionMultipleChoice(
                    question_name=prefix + suffix,
                    question_text="Pick one.",
                    question_options=["Yes", "No", "Other"],
                )
                for suffix in ("a", "b")
            ]
        )

    first, second = module("left"), module("right")
    second.questions_to_randomize = ["righta"]
    combined = compose_surveys(first, second)
    assert combined.questions_to_randomize == ["righta"]
    assert first.questions_to_randomize == []
    first = first.sample_questions(["lefta", "leftb"], 1)
    second = second.sample_questions(["righta", "rightb"], 1)
    assert (
        compose_surveys(module("plain"), second).question_sampling
        == second.question_sampling
    )
    with pytest.raises(ValueError, match="Both modules define question_sampling"):
        compose_surveys(first, second)


def test_replace_question_type_retains_names_routes_groups_and_memory(tmp_path):
    survey = Survey(
        [
            QuestionMultipleChoice(
                question_name="rating",
                question_text="How reliable?",
                question_options=["1", "2", "3"],
            ),
            QuestionFreeText(question_name="why", question_text="Why?"),
        ]
    )
    survey.add_skip_rule("why", "{{ rating.answer }} == 3")
    survey.add_question_group("rating", "rating", "trip")
    survey.set_full_memory_mode()
    source, target = tmp_path / "source.ep", tmp_path / "revised.ep"
    survey.git.save(source, sync_coop=False)
    original = source.read_bytes()
    invoke(
        "surveys",
        "replace-question",
        source,
        "rating",
        "--question-json",
        '{"type":"linear_scale","options":[1,2,3]}',
        "-o",
        target,
    )
    invoke(
        "surveys",
        "replace-question",
        target,
        "why",
        "--question-json",
        '{"type":"interview","text":"Follow up","interview_guide":"Explain {{ rating.answer }}"}',
    )
    changed = Survey.git.load(target, sync_coop=False)
    assert changed.question_names == survey.question_names
    assert changed.get("rating").question_type == "linear_scale"
    assert changed.get("rating").question_text == "How reliable?"
    assert changed.get("rating").question_options == [1, 2, 3]
    assert changed.get("why").question_type == "interview"
    assert changed.get("why").interview_guide == "Explain {{ rating.answer }}"
    assert changed.rule_collection.to_dict() == survey.rule_collection.to_dict()
    assert changed.question_groups == survey.question_groups
    assert changed.memory_plan.to_dict()["survey_question_texts"] == [
        "How reliable?",
        "Follow up",
    ]
    assert source.read_bytes() == original
    previous = target.read_bytes()
    for definition in (
        '{"type":"free_text","name":"new_name"}',
        '{"type":"interview"}',
    ):
        invoke(
            "surveys",
            "replace-question",
            target,
            "why",
            "--question-json",
            definition,
            success=False,
        )
    assert target.read_bytes() == previous
