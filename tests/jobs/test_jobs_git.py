import base64
import json
import shutil
import subprocess

import pytest

from edsl import Agent, AgentList, FileStore, Jobs, Model, ModelList, Scenario, ScenarioList
from edsl.base.base_exception import BaseException as EDSLBaseException
from edsl.jobs import JobsGitError, JobsGitNestedRepoWarning
from edsl.jobs.exceptions import JobsErrors
from edsl.questions import QuestionFreeText
from edsl.surveys import Survey


pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="Jobs git package tests require git"
)


def simple_job(answer: str = "SPAM!") -> Jobs:
    survey = Survey(
        [
            QuestionFreeText(
                question_name="name",
                question_text="What is your name in {{ period }}?",
            )
        ]
    )
    return Jobs(
        survey=survey,
        agents=AgentList([Agent(traits={"status": "Joyful"})]),
        models=ModelList([Model("test", canned_response=answer)]),
        scenarios=ScenarioList([Scenario({"period": "morning"})]),
    )


def test_jobs_git_error_uses_jobs_exception_hierarchy():
    assert issubclass(JobsGitError, JobsErrors)
    assert issubclass(JobsGitError, EDSLBaseException)
    assert issubclass(JobsGitNestedRepoWarning, UserWarning)


def test_jobs_git_save_default_path_and_load_round_trip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    job = simple_job()

    info = job.git.save()

    package_path = tmp_path / "jobs.jobs.ep"
    assert info["status"] == "ok"
    assert info["path"] == "jobs.jobs.ep"
    assert package_path.is_dir()
    assert (package_path / ".git").is_dir()
    assert (package_path / "manifest.json").is_file()
    assert (package_path / "job.json").is_file()
    for component in ["survey", "agents", "scenarios", "models"]:
        assert (package_path / component / "manifest.json").is_file()
        assert not (package_path / component / ".git").exists()

    manifest = json.loads((package_path / "manifest.json").read_text())
    assert manifest["format"] == "edsl.jobs.git_package"
    assert manifest["edsl_class_name"] == "Jobs"
    assert manifest["object_type"] == "Jobs"
    assert manifest["components"] == {
        "survey": "survey",
        "agents": "agents",
        "scenarios": "scenarios",
        "models": "models",
    }
    assert "edsl_version" in manifest

    loaded = Jobs.git.load(package_path)
    assert loaded == job
    assert loaded.git.path == package_path
    assert loaded.git.validate() == {"status": "ok", "errors": []}


def test_jobs_git_loads_historical_commit_without_checkout(tmp_path):
    package_path = tmp_path / "experiment.jobs.ep"
    first_job = simple_job("first")
    first = first_job.git.save(package_path, message="initial")

    second_job = simple_job("second")
    second = second_job.git.save(package_path, message="updated")

    old = Jobs.git.load(package_path, ref=first["commit"])
    current = Jobs.git.load(package_path)

    assert old == first_job
    assert current == second_job
    assert current.git.commit == second["commit"]


def test_jobs_git_branch_tag_restore(tmp_path):
    package_path = tmp_path / "experiment.jobs.ep"
    job = simple_job("main")
    first = job.git.save(package_path, message="main")
    tag_info = job.git.tag("baseline", message="baseline job")

    assert tag_info["commit"] == first["commit"]
    assert job.git.tags() == ["baseline"]

    job.git.branch("experiment")
    job.git.switch("experiment")
    updated = simple_job("experiment")
    updated.git.save(package_path, message="experiment")

    restore_info = updated.git.restore("baseline")

    assert restore_info["commit"] == first["commit"]
    assert updated == job
    assert subprocess.check_output(
        ["git", "-C", str(package_path), "branch", "--show-current"], text=True
    ).strip() == "experiment"


def test_jobs_git_push_and_pull_with_remote(tmp_path):
    remote_path = tmp_path / "remote.git"
    first_path = tmp_path / "first.jobs.ep"
    second_path = tmp_path / "second.jobs.ep"
    subprocess.run(["git", "init", "--bare", str(remote_path)], check=True)

    first = simple_job("initial")
    first.git.save(first_path, message="initial job")
    first.git.remote_add("origin", str(remote_path))
    push_info = first.git.push()

    assert push_info["status"] == "ok"
    assert push_info["remote"] == "origin"

    subprocess.run(["git", "clone", str(remote_path), str(second_path)], check=True)
    second = Jobs.git.load(second_path)
    assert second == first

    updated = simple_job("updated")
    updated.git.save(first_path, message="updated job")
    updated.git.push()

    pull_info = second.git.pull()

    assert pull_info["status"] == "ok"
    assert second == updated


def test_jobs_git_dependency_round_trip(tmp_path):
    package_path = tmp_path / "dependent.jobs.ep"
    base = simple_job("base")
    dependent = simple_job("dependent")
    dependent._depends_on = base
    dependent._post_run_methods = [("select", ("answer.name",), {})]

    dependent.git.save(package_path)

    assert (package_path / "dependencies" / "000001" / "job.json").is_file()
    loaded = Jobs.git.load(package_path)

    assert loaded == dependent
    assert loaded._depends_on == base
    assert loaded._post_run_methods == [("select", ("answer.name",), {})]


def test_jobs_git_embedded_scenario_filestore_round_trip(tmp_path):
    source_path = tmp_path / "source.txt"
    source_path.write_text("hello from jobs filestore\n")
    package_path = tmp_path / "files.jobs.ep"
    job = simple_job()
    job.scenarios = ScenarioList([Scenario({"period": "morning", "document": FileStore(str(source_path))})])

    job.git.save(package_path)

    scenario_json = json.loads(
        (package_path / "scenarios" / "scenarios" / "000001.json").read_text()
    )
    filestore_ref = scenario_json["document"]
    assert filestore_ref["edsl_type"] == "FileStoreRef"
    assert "base64_string" not in json.dumps(scenario_json)

    loaded = Jobs.git.load(package_path)
    loaded_file = loaded.scenarios[0]["document"]
    assert isinstance(loaded_file, FileStore)
    assert base64.b64decode(loaded_file.base64_string) == b"hello from jobs filestore\n"
