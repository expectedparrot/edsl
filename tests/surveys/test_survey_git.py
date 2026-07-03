import json
from copy import deepcopy
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from edsl import QuestionFreeText, QuestionMultipleChoice, Survey
from edsl.surveys import SurveyGitError, SurveyGitNestedRepoWarning
from edsl.surveys.exceptions import SurveyError
from edsl.base.base_exception import BaseException as EDSLBaseException


pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="Survey git package tests require git"
)


def _package_json(package_path: Path, member: str):
    with zipfile.ZipFile(package_path) as archive:
        return json.loads(archive.read(member).decode())


def _package_names(package_path: Path) -> set[str]:
    with zipfile.ZipFile(package_path) as archive:
        return set(archive.namelist())


def test_survey_git_error_uses_survey_exception_hierarchy():
    assert issubclass(SurveyGitError, SurveyError)
    assert issubclass(SurveyGitError, EDSLBaseException)
    assert issubclass(SurveyGitNestedRepoWarning, UserWarning)


def test_survey_git_save_default_path_and_load_round_trip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    survey = Survey.example()

    info = survey.git.save()

    package_path = tmp_path / "survey.ep"
    assert info["status"] == "ok"
    assert info["path"] == "survey.ep"
    assert package_path.is_file()
    names = _package_names(package_path)
    assert ".git/HEAD" in names
    assert "manifest.json" in names
    assert "questions/000001.json" in names
    assert "metadata/memory_plan.json" in names
    assert "metadata/rule_collection.json" in names
    assert "metadata/question_groups.json" in names

    manifest = _package_json(package_path, "manifest.json")
    assert manifest["format"] == "edsl.survey.git_package"
    assert manifest["edsl_class_name"] == "Survey"
    assert manifest["object_type"] == "Survey"
    assert manifest["question_order"] == ["000001", "000002", "000003"]
    assert "edsl_version" in manifest

    loaded = Survey.git.load(package_path)
    assert loaded == survey
    assert loaded.git.path == package_path


def test_survey_git_save_accepts_stem_and_validate(tmp_path):
    package_stem = tmp_path / "customer_survey"
    expected_path = tmp_path / "customer_survey.ep"
    survey = Survey.example()

    info = survey.git.save(package_stem, message="initial survey")

    assert info["path"] == str(expected_path)
    assert expected_path.is_file()
    assert survey.git.validate() == {"status": "ok", "errors": []}


def test_survey_git_loads_historical_commit_without_checkout(tmp_path):
    package_path = tmp_path / "survey.survey.ep"
    first_survey = Survey.example()
    first = first_survey.git.save(package_path, message="initial")

    second_survey = Survey.example().add_question(
        QuestionFreeText(question_name="extra", question_text="Extra?")
    )
    second = second_survey.git.save(package_path, message="updated")

    old = Survey.git.load(package_path, ref=first["commit"])
    current = Survey.git.load(package_path)

    assert old == first_survey
    assert current == second_survey
    assert current.git.commit == second["commit"]


def test_survey_git_mutation_save_cleans_stale_questions_and_round_trips(tmp_path):
    package_path = tmp_path / "survey.survey.ep"
    kept_question = QuestionFreeText(
        question_name="kept",
        question_text="Keep this question?",
    )
    first_survey = Survey(
        [
            QuestionFreeText(question_name="removed", question_text="Remove this?"),
            kept_question,
        ]
    )
    first = first_survey.git.save(package_path, message="initial survey")

    second_survey = Survey(
        [
            kept_question,
            QuestionFreeText(question_name="added", question_text="Add this?"),
        ]
    )
    second = second_survey.git.save(package_path, message="mutated survey")

    manifest = _package_json(package_path, "manifest.json")
    assert manifest["question_order"] == ["000002", "000003"]
    names = _package_names(package_path)
    assert "questions/000001.json" not in names
    assert "questions/000002.json" in names
    assert "questions/000003.json" in names
    assert Survey.git.load(package_path) == second_survey
    assert Survey.git.load(package_path, ref=first["commit"]) == first_survey
    assert second["commit"] != first["commit"]


def test_survey_git_public_edits_round_trip_from_bound_package(tmp_path):
    package_path = tmp_path / "editable.survey.ep"
    survey = Survey(
        [
            QuestionFreeText(question_name="q0", question_text="First?"),
            QuestionFreeText(question_name="q1", question_text="Second?"),
            QuestionFreeText(question_name="q2", question_text="Third?"),
        ]
    )
    first = survey.git.save(package_path, message="initial survey")

    survey.move_question("q2", 0)
    survey.delete_question("q0")
    survey.add_question(
        QuestionFreeText(question_name="q3", question_text="Inserted?"),
        index=1,
    )
    second = survey.git.save(message="edited survey")

    manifest = _package_json(package_path, "manifest.json")
    assert survey.question_names == ["q2", "q3", "q1"]
    assert manifest["question_order"] == ["000003", "000004", "000002"]
    names = _package_names(package_path)
    assert "questions/000001.json" not in names
    assert "questions/000002.json" in names
    assert "questions/000003.json" in names
    assert "questions/000004.json" in names
    assert Survey.git.load(package_path) == survey
    assert Survey.git.load(package_path, ref=first["commit"]).question_names == [
        "q0",
        "q1",
        "q2",
    ]
    assert second["commit"] != first["commit"]


def test_survey_git_metadata_edits_round_trip(tmp_path):
    package_path = tmp_path / "metadata.survey.ep"
    survey = Survey(
        [
            QuestionMultipleChoice(
                question_name="q0",
                question_text="Choose one.",
                question_options=["yes", "no", "maybe"],
            ),
            QuestionFreeText(question_name="q1", question_text="Why?"),
            QuestionFreeText(question_name="q2", question_text="Anything else?"),
        ],
        name="metadata survey",
        questions_to_randomize=["q0"],
        options_to_pin={"q0": ["yes"]},
    )
    survey.add_targeted_memory("q2", "q0")
    survey.add_skip_rule("q1", "{{ q0.answer }} == 'no'")
    survey.add_question_group("q0", "q0", "intro")
    first = survey.git.save(package_path, message="metadata survey")

    loaded = Survey.git.load(package_path)

    assert loaded == survey
    assert loaded.to_dict(add_edsl_version=False) == survey.to_dict(
        add_edsl_version=False
    )
    assert _package_json(package_path, "metadata/name.json") == "metadata survey"
    assert _package_json(package_path, "metadata/questions_to_randomize.json") == ["q0"]
    assert _package_json(package_path, "metadata/options_to_pin.json") == {
        "q0": ["yes"]
    }
    assert _package_json(package_path, "metadata/question_groups.json") == {
        "intro": [0, 0]
    }
    assert loaded.memory_plan.to_dict(add_edsl_version=False) == (
        survey.memory_plan.to_dict(add_edsl_version=False)
    )
    assert loaded.rule_collection.to_dict(add_edsl_version=False) == (
        survey.rule_collection.to_dict(add_edsl_version=False)
    )

    survey.name = None
    survey.questions_to_randomize = []
    survey.options_to_pin = {}
    survey.question_groups = {}
    second = survey.git.save(message="remove optional metadata")

    names = _package_names(package_path)
    assert "metadata/name.json" not in names
    assert "metadata/questions_to_randomize.json" not in names
    assert "metadata/options_to_pin.json" not in names
    assert Survey.git.load(package_path) == survey
    assert Survey.git.load(package_path, ref=first["commit"]) == loaded
    assert second["commit"] != first["commit"]


def test_survey_git_complex_metadata_edit_restore_exact_dict_round_trip(tmp_path):
    package_path = tmp_path / "complex.survey.ep"
    survey = Survey(
        [
            QuestionMultipleChoice(
                question_name="q0",
                question_text="Choose one.",
                question_options=["yes", "no", "maybe"],
            ),
            QuestionFreeText(question_name="q1", question_text="Why?"),
            QuestionFreeText(question_name="q2", question_text="Explain more."),
            QuestionFreeText(question_name="q3", question_text="Final note."),
        ],
        name="complex survey",
        questions_to_randomize=["q0"],
        options_to_pin={"q0": ["yes"]},
    )
    survey.add_targeted_memory("q2", "q0")
    survey.add_memory_collection("q3", ["q0", "q1"])
    survey.add_skip_rule("q1", "{{ q0.answer }} == 'no'")
    survey.add_stop_rule("q3", "{{ q3.answer }} == 'stop'")
    survey.add_question_group("q0", "q0", "intro")
    first_dict = deepcopy(survey.to_dict(add_edsl_version=False))
    first = survey.git.save(package_path, message="complex initial")

    survey.delete_question("q1")
    survey.add_question(
        QuestionFreeText(question_name="q4", question_text="Inserted after edit."),
        index=1,
    )
    survey.add_targeted_memory("q4", "q0")
    survey.question_groups = {"intro": (0, 0), "inserted": (1, 1)}
    second_dict = deepcopy(survey.to_dict(add_edsl_version=False))
    second = survey.git.save(message="complex edited")

    loaded_current = Survey.git.load(package_path)
    loaded_old = Survey.git.load(package_path, ref=first["commit"])

    assert loaded_current.to_dict(add_edsl_version=False) == second_dict
    assert loaded_old.to_dict(add_edsl_version=False) == first_dict
    restore_info = loaded_current.git.restore(first["commit"])
    assert restore_info["commit"] == first["commit"]
    assert loaded_current.to_dict(add_edsl_version=False) == first_dict
    assert second["commit"] != first["commit"]


def test_survey_git_branch_tag_restore(tmp_path):
    package_path = tmp_path / "survey.survey.ep"
    survey = Survey.example()
    first = survey.git.save(package_path, message="main")
    tag_info = survey.git.tag("baseline", message="baseline survey")

    assert tag_info["commit"] == first["commit"]
    assert survey.git.tags() == ["baseline"]

    survey.git.branch("experiment")
    survey.git.switch("experiment")
    updated = Survey.example().add_question(
        QuestionFreeText(question_name="extra", question_text="Extra?")
    )
    updated.git.save(package_path, message="experiment")

    restore_info = updated.git.restore("baseline")

    assert restore_info["commit"] == first["commit"]
    assert updated == survey
    assert (
        subprocess.check_output(
            ["git", "-C", str(updated.git.worktree_path), "branch", "--show-current"],
            text=True,
        ).strip()
        == "experiment"
    )


def test_survey_git_push_and_pull_with_remote(tmp_path):
    remote_path = tmp_path / "remote.git"
    first_path = tmp_path / "first.survey.ep"
    second_path = tmp_path / "second.survey.ep"
    subprocess.run(["git", "init", "--bare", str(remote_path)], check=True)

    first = Survey.example()
    first.git.save(first_path, message="initial survey")
    first.git.remote_add("origin", str(remote_path))
    push_info = first.git.push()

    assert push_info["status"] == "ok"
    assert push_info["remote"] == "origin"

    second = Survey.git.clone(str(remote_path), path=second_path)
    assert second == first

    updated = Survey.example().add_question(
        QuestionFreeText(question_name="extra", question_text="Extra?")
    )
    updated.git.save(first_path, message="updated survey")
    updated.git.push()

    pull_info = second.git.pull()

    assert pull_info["status"] == "ok"
    assert second == updated
