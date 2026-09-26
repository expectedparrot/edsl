import pytest

from edsl import AgentList, Jobs, ModelList, Results, ScenarioList, Survey
from edsl.questions import QuestionFreeText


GIT_BACKED_EXAMPLES = [
    Survey.example,
    AgentList.example,
    ScenarioList.example,
    ModelList.example,
    Jobs.example,
    Results.example,
]


@pytest.mark.parametrize("example", GIT_BACKED_EXAMPLES)
def test_git_backed_save_and_load_use_ep_for_extensionless_path(tmp_path, example):
    obj = example()
    path = tmp_path / type(obj).__name__.lower()

    info = obj.save(path)

    package_path = path.with_suffix(".ep")
    assert package_path.exists()
    assert info["path"] == str(package_path)
    assert type(obj).load(path) == obj


@pytest.mark.parametrize("example", GIT_BACKED_EXAMPLES)
def test_git_backed_objects_preserve_explicit_json_formats(tmp_path, example):
    obj = example()
    json_path = tmp_path / f"{type(obj).__name__.lower()}.json"
    gzip_path = tmp_path / f"{type(obj).__name__.lower()}.json.gz"

    obj.save(json_path)
    obj.save(gzip_path)

    assert json_path.exists()
    assert gzip_path.exists()
    assert type(obj).load(json_path) == obj
    assert type(obj).load(gzip_path) == obj


def test_save_json_and_load_json_are_explicit_legacy_api(tmp_path):
    survey = Survey.example()
    path = tmp_path / "survey.json"

    survey.save_json(path, compress=False)

    assert Survey.load_json(path) == survey


def test_git_backed_save_without_filename_uses_default_ep_path(tmp_path, monkeypatch):
    survey = Survey.example()
    monkeypatch.chdir(tmp_path)

    info = survey.save()

    assert (tmp_path / "survey.ep").exists()
    assert info["path"] == "survey.ep"
    assert Survey.load("survey") == survey


def test_non_git_backed_base_objects_keep_json_default(tmp_path):
    question = QuestionFreeText.example()
    path = tmp_path / "question"

    question.save(path)

    json_path = tmp_path / "question.json.gz"
    assert json_path.exists()
    assert QuestionFreeText.load(path) == question
