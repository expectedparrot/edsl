import json
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from edsl.results import Results, ResultsGitError, ResultsGitNestedRepoWarning
from edsl import Agent, Model, QuestionFreeText, QuestionInterview, Scenario, Survey
from edsl.results import Result
from edsl.results.results_git import _result_row, _transcript_row
from edsl.results.exceptions import ResultsError
from edsl.base.base_exception import BaseException as EDSLBaseException
from edsl.tasks import TaskHistory


pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="Results git package tests require git"
)


def _package_json(package_path: Path, member: str):
    with zipfile.ZipFile(package_path) as archive:
        return json.loads(archive.read(member).decode())


def _package_names(package_path: Path) -> set[str]:
    with zipfile.ZipFile(package_path) as archive:
        return set(archive.namelist())


def _results_with_task_history(*, fixed=False):
    results = Results.example().sample(1)
    history = TaskHistory.from_dict(
        {
            "include_traceback": True,
            "interviews": [
                {
                    "id": "interview-1",
                    "type": "InterviewReference",
                    "exceptions": {
                        "q0": [
                            {
                                "exception": {
                                    "type": "ValidationError",
                                    "module": "edsl.runner",
                                    "message": "invalid answer",
                                    "traceback": "Exception: invalid answer",
                                },
                                "invigilator": None,
                                "additional_data": {"attempts": 3},
                            }
                        ]
                    },
                    "fixed_questions": ["q0"] if fixed else [],
                    "task_status_logs": {},
                }
            ],
        }
    )
    results.task_history = history
    return results


def test_results_git_error_uses_results_exception_hierarchy():
    assert issubclass(ResultsGitError, ResultsError)
    assert issubclass(ResultsGitError, EDSLBaseException)
    assert issubclass(ResultsGitNestedRepoWarning, UserWarning)


def test_results_git_save_default_path_and_load_round_trip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    results = Results.example()
    results._job_uuid = "job-123"
    results.results_uuid = "results-456"

    info = results.git.save()

    package_path = tmp_path / "results.ep"
    assert info["status"] == "ok"
    assert info["path"] == "results.ep"
    assert package_path.is_file()
    names = _package_names(package_path)
    assert ".git/HEAD" in names
    assert "manifest.json" in names
    assert "results.jsonl" in names

    manifest = _package_json(package_path, "manifest.json")
    assert manifest["format"] == "edsl.results.git_package"
    assert manifest["edsl_class_name"] == "Results"
    assert manifest["object_type"] == "Results"
    assert manifest["n_results"] == len(results)
    assert manifest["content_sha256"] == info["content_sha256"]
    assert manifest["source"]["job_uuid"] == "job-123"
    assert manifest["source"]["results_uuid"] == "results-456"
    assert "edsl_version" in manifest

    loaded = Results.git.load(package_path)
    assert loaded == results
    assert loaded.git.path == package_path
    assert loaded.git.validate() == {"status": "ok", "errors": []}


def test_results_jsonl_round_trip_preserves_task_history():
    results = _results_with_task_history()

    loaded = Results.from_jsonl(results.to_jsonl())

    assert loaded.has_unfixed_exceptions
    assert len(loaded.task_history.exceptions) == 1
    entry = loaded.task_history.to_dict()["interviews"][0]["exceptions"]["q0"][0]
    assert entry["exception"]["message"] == "invalid answer"
    assert entry["additional_data"]["attempts"] == 3


def test_results_jsonl_records_authoritative_empty_task_history():
    results = Results.example().sample(1)
    lines = results.to_jsonl().splitlines()

    assert json.loads(lines[0])["format_version"] == 2
    assert json.loads(lines[1])["n_task_history_lines"] == 1
    loaded = Results.from_jsonl("\n".join(lines))
    assert loaded.task_history.total_interviews == []
    assert not loaded.has_unfixed_exceptions


def test_results_jsonl_round_trip_preserves_fixed_history():
    results = _results_with_task_history(fixed=True)
    assert not results.has_unfixed_exceptions

    loaded = Results.from_jsonl(results.to_jsonl())

    assert len(loaded.task_history.exceptions) == 1
    assert not loaded.has_unfixed_exceptions
    assert loaded.task_history.to_dict()["interviews"][0]["fixed_questions"] == [
        "q0"
    ]


def test_results_git_round_trip_preserves_task_history(tmp_path):
    results = _results_with_task_history()
    package_path = tmp_path / "failed-results.ep"

    results.git.save(package_path)
    loaded = Results.git.load(package_path)

    assert loaded.has_unfixed_exceptions
    assert len(loaded.task_history.exceptions) == 1


def test_results_jsonl_loads_legacy_format_without_task_history():
    results = Results.example().sample(1)
    lines = results.to_jsonl().splitlines()
    manifest = json.loads(lines[1])
    n_survey = manifest["n_survey_lines"]
    n_history = manifest.pop("n_task_history_lines")
    legacy_lines = (
        [lines[0], json.dumps(manifest)]
        + lines[2 : 2 + n_survey]
        + lines[2 + n_survey + n_history :]
    )

    loaded = Results.from_jsonl("\n".join(legacy_lines))

    assert len(loaded) == len(results)
    assert loaded.task_history.total_interviews == []


def test_results_git_save_is_immutable_by_default(tmp_path):
    package_path = tmp_path / "archive.results.ep"
    first = Results.example()
    first.git.save(package_path, message="first")

    second = Results.example().sample(1)
    with pytest.raises(ResultsGitError, match="immutable"):
        second.git.save(package_path, message="second")

    info = second.git.save(package_path, message="second", allow_new_commit=True)
    assert info["status"] == "ok"
    assert Results.git.load(package_path) == second


def test_results_git_loads_historical_commit_without_checkout(tmp_path):
    package_path = tmp_path / "archive.results.ep"
    first_results = Results.example()
    first = first_results.git.save(package_path, message="initial")

    second_results = Results.example().sample(1)
    second = second_results.git.save(
        package_path, message="updated", allow_new_commit=True
    )

    old = Results.git.load(package_path, ref=first["commit"])
    current = Results.git.load(package_path)

    assert old == first_results
    assert current == second_results
    assert current.git.commit == second["commit"]


def test_results_git_package_html(tmp_path):
    package_path = tmp_path / "results.ep"
    html_path = tmp_path / "results.html"
    results = Results.example()
    results.git.save(package_path)
    results.git._write_coop_info_and_commit(
        {
            "uuid": "results-uuid",
            "url": "https://www.expectedparrot.com/content/results-uuid",
            "alias_url": "https://www.expectedparrot.com/content/alice/shared-results",
            "alias": "shared-results",
            "description": "A shared results object",
            "owner": "alice",
        },
        message="Add Coop info",
    )

    html = Results.git.open(package_path).html(filename=html_path)

    assert "<title>Results</title>" in html
    assert "<title>EDSL Results</title>" not in html
    assert "Expected Parrot" in html
    assert "Expected Parrot Server" in html
    assert "remote-meta" in html
    assert "copy-mini" in html
    assert "object alias" in html
    assert "owner" in html
    assert "results-uuid" in html
    assert "alice/shared-results" in html
    assert "alias URL" in html
    assert "https://www.expectedparrot.com/content/alice/shared-results" in html
    assert "shared-results" in html
    assert "A shared results object" in html
    assert "alice" in html
    assert '"href": "https://www.expectedparrot.com/content/results-uuid"' in html
    assert 'target="_blank"' in html
    assert "collection-table" in html
    assert "<table" in html
    assert 'class="facts-table"' in html
    assert '"label": "Results"' in html
    assert '"label": "Questions"' in html
    assert 'id="table-tab"' in html
    assert 'id="transcript-tab"' in html
    assert 'id="transcript-panel" hidden' in html
    assert 'id="transcript-toolbar"' in html
    assert 'data-dimension="${field}"' in html
    assert 'class="context-fields"' in html
    assert 'class="scenario-token"' in html
    assert 'class="${columnClass(col)}"' in html
    assert 'class="interview-link"' in html
    assert '"answer.how_feeling"' in html
    assert 'id="columns-button"' in html
    assert 'id="copy-csv"' in html
    assert "function shownCsv()" in html
    assert "dimensionPosition(row, field)" in html
    assert html_path.read_text(encoding="utf-8") == html


def test_results_git_package_html_renders_interview_answers_as_turns(tmp_path):
    opening = QuestionFreeText(
        question_name="opening", question_text="What is your initial reaction?"
    )
    question = QuestionInterview(
        question_name="experience",
        question_text="Tell me about your experience.",
        interview_guide="Ask for a concrete example.",
    )
    closing = QuestionFreeText(
        question_name="closing", question_text="What should improve?"
    )
    survey = Survey([opening, question, closing])
    answer = [
        {
            "role": "interviewer",
            "content": [
                {"type": "text", "text": "What changed?"},
                {"type": "image", "url": "https://example.com/image.png"},
                {"type": "text", "text": "Please be specific."},
            ],
        },
        {
            "role": "respondent",
            "content": [
                {"type": "text", "text": "Everything <script>alert(1)</script>."}
            ],
        },
    ]
    result = Result(
        agent=Agent(name="participant-1"),
        scenario=Scenario(),
        model=Model("test"),
        iteration=0,
        answer={
            "opening": "Positive",
            "experience": answer,
            "closing": "Faster checkout",
        },
        survey=survey,
    )
    results = Results(survey=survey, data=[result])
    package_path = tmp_path / "interview-results.ep"
    results.git.save(package_path)

    html = Results.git.open(package_path).html()
    transcript = _transcript_row(1, result, survey.question_names)

    assert [item["name"] for item in transcript["questions"]] == [
        "opening",
        "experience",
        "closing",
    ]
    assert '"__interview_transcripts"' in html
    assert '"interview_turns"' in html
    assert 'class="interview-transcript"' in html
    assert 'class="interview-turn ${role}"' in html
    assert "What changed?\\nPlease be specific." in html
    assert "Tell me about your experience." in html
    assert '"label": "participant-1"' in html
    assert "participant-1" in html


def test_results_git_package_html_preserves_malformed_interview_answer(tmp_path):
    question = QuestionInterview(
        question_name="experience",
        question_text="Tell me about your experience.",
        interview_guide="Ask for a concrete example.",
    )
    survey = Survey([question])
    result = Result(
        agent=Agent(name="participant-1"),
        scenario=Scenario(),
        model=Model("test"),
        iteration=0,
        answer={"experience": {"unexpected": "shape"}},
        survey=survey,
    )
    package_path = tmp_path / "malformed-interview-results.ep"
    Results(survey=survey, data=[result]).git.save(package_path)

    html = Results.git.open(package_path).html()

    assert '"unexpected": "shape"' in html
    assert '"interview_turns": null' in html


def test_results_html_reserved_marker_cannot_hide_user_answer():
    question = QuestionFreeText(
        question_name="structured", question_text="Return structured data."
    )
    survey = Survey([question])
    answer = {
        "__edsl_cell_type": "interview_transcript",
        "turns": ["user-authored", "data"],
        "actual_value": "preserve me",
    }
    result = Result(
        agent=Agent(name="participant-1"),
        scenario=Scenario(),
        model=Model("test"),
        iteration=0,
        answer={"structured": answer},
        survey=survey,
    )

    row = _result_row(1, result)

    assert row["answer.structured"] == answer
    assert row["__interview_transcripts"] == {}


def test_results_git_tag_restore(tmp_path):
    package_path = tmp_path / "archive.results.ep"
    results = Results.example()
    first = results.git.save(package_path, message="main")
    tag_info = results.git.tag("published", message="published results")

    assert tag_info["commit"] == first["commit"]
    assert results.git.tags() == ["published"]

    updated = Results.example().sample(1)
    updated.git.save(package_path, message="updated", allow_new_commit=True)
    restore_info = updated.git.restore("published")

    assert restore_info["commit"] == first["commit"]
    assert updated == results


def test_results_git_push_and_pull_with_remote(tmp_path):
    remote_path = tmp_path / "remote.git"
    first_path = tmp_path / "first.results.ep"
    second_path = tmp_path / "second.results.ep"
    subprocess.run(["git", "init", "--bare", str(remote_path)], check=True)

    first = Results.example()
    first.git.save(first_path, message="initial results")
    first.git.remote_add("origin", str(remote_path))
    push_info = first.git.push()

    assert push_info["status"] == "ok"
    assert push_info["remote"] == "origin"

    second = Results.git.clone(str(remote_path), path=second_path)
    assert second == first
