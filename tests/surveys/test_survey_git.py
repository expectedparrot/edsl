import json
import shutil
import subprocess
from pathlib import Path

import pytest

from edsl import QuestionFreeText, Survey
from edsl.surveys import SurveyGitError, SurveyGitNestedRepoWarning
from edsl.surveys.exceptions import SurveyError
from edsl.base.base_exception import BaseException as EDSLBaseException


pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="Survey git package tests require git"
)


def test_survey_git_error_uses_survey_exception_hierarchy():
    assert issubclass(SurveyGitError, SurveyError)
    assert issubclass(SurveyGitError, EDSLBaseException)
    assert issubclass(SurveyGitNestedRepoWarning, UserWarning)


def test_survey_git_save_default_path_and_load_round_trip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    survey = Survey.example()

    info = survey.git.save()

    package_path = tmp_path / "survey.survey.ep"
    assert info["status"] == "ok"
    assert info["path"] == "survey.survey.ep"
    assert package_path.is_dir()
    assert (package_path / ".git").is_dir()
    assert (package_path / "manifest.json").is_file()
    assert (package_path / "questions" / "000001.json").is_file()
    assert (package_path / "metadata" / "memory_plan.json").is_file()
    assert (package_path / "metadata" / "rule_collection.json").is_file()
    assert (package_path / "metadata" / "question_groups.json").is_file()

    manifest = json.loads((package_path / "manifest.json").read_text())
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
    expected_path = tmp_path / "customer_survey.survey.ep"
    survey = Survey.example()

    info = survey.git.save(package_stem, message="initial survey")

    assert info["path"] == str(expected_path)
    assert expected_path.is_dir()
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
    assert subprocess.check_output(
        ["git", "-C", str(package_path), "branch", "--show-current"], text=True
    ).strip() == "experiment"


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

    subprocess.run(["git", "clone", str(remote_path), str(second_path)], check=True)
    second = Survey.git.load(second_path)
    assert second == first

    updated = Survey.example().add_question(
        QuestionFreeText(question_name="extra", question_text="Extra?")
    )
    updated.git.save(first_path, message="updated survey")
    updated.git.push()

    pull_info = second.git.pull()

    assert pull_info["status"] == "ok"
    assert second == updated
