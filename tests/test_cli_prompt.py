"""CLI support for Prompt, which is stored as JSON rather than a .ep package."""

import gzip
import json

import pytest
from click.testing import CliRunner

import edsl.__main__ as cli_module
from edsl import Prompt
from edsl.cli_shared import is_serialized_prompt, jsonable, load_openable_json

TEXT = "Explain {{ topic }} for {{ audience }}."


def invoke(*args):
    result = CliRunner().invoke(cli_module.app, list(args))
    return result, json.loads(result.output) if result.output.strip() else None


def write_json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "data",
    [
        Prompt(TEXT).to_dict(add_edsl_version=True),
        # What Prompt.save() writes: the class is named only in class_name.
        {"text": TEXT, "class_name": "Prompt"},
    ],
)
def test_load_openable_json_reads_prompts(tmp_path, data):
    loaded = load_openable_json(write_json(tmp_path / "prompt.json", data))
    assert type(loaded) is Prompt
    assert str(loaded) == TEXT


def test_load_openable_json_reads_gzipped_prompts(tmp_path):
    path = tmp_path / "prompt.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(Prompt(TEXT).to_dict(add_edsl_version=True), f)
    assert str(load_openable_json(path)) == TEXT


def test_prompt_save_output_loads(tmp_path):
    path = tmp_path / "saved.json"
    Prompt(TEXT).save(str(path))
    assert str(load_openable_json(path)) == TEXT


@pytest.mark.parametrize(
    "data",
    [
        {"text": "a dict with a text key"},
        {"text": "x", "class_name": "Scenario"},
        {"text": 5, "class_name": "Prompt"},
        {"text": "x", "class_name": "Prompt", "edsl_class_name": "Survey"},
        ["not", "a", "dict"],
    ],
)
def test_is_serialized_prompt_is_narrow(data):
    assert not is_serialized_prompt(data)


def test_jsonable_keeps_prompt_text():
    assert jsonable(Prompt(TEXT)) == TEXT
    assert jsonable({"prompt": Prompt(TEXT)}) == {"prompt": TEXT}


def test_push_json_prompt(tmp_path, monkeypatch):
    path = write_json(tmp_path / "prompt.json", {"text": TEXT, "class_name": "Prompt"})
    push_calls = []

    class FakeCoop:
        def push(self, obj, **kwargs):
            push_calls.append((obj, kwargs))
            return {"uuid": "created-uuid", "object_type": "prompt", "alias": kwargs["alias"]}

    import edsl.coop as coop_module

    monkeypatch.setattr(coop_module, "Coop", FakeCoop)

    result, out = invoke(
        "push", str(path), "--alias", "explanation-template", "--visibility", "private"
    )

    assert result.exit_code == 0, result.output
    assert out["data"]["object_type"] == "Prompt"
    assert out["data"]["operation"] == "push"
    assert out["data"]["coop_info"]["uuid"] == "created-uuid"
    (obj, kwargs) = push_calls[0]
    assert type(obj) is Prompt and str(obj) == TEXT
    assert kwargs == {
        "description": None,
        "alias": "explanation-template",
        "force": False,
        "visibility": "private",
    }


def test_push_json_still_rejects_package_backed_objects(tmp_path, monkeypatch):
    from edsl.surveys import Survey

    class FakeCoop:
        def push(self, obj, **kwargs):
            raise AssertionError("a package-backed object should not be pushed from JSON")

    import edsl.coop as coop_module

    monkeypatch.setattr(coop_module, "Coop", FakeCoop)
    path = write_json(tmp_path / "survey.json", Survey.example().to_dict())

    result, out = invoke("push", str(path))

    assert result.exit_code == cli_module.EXIT_USAGE
    assert out["error"]["code"] == "USAGE_ERROR"


def test_push_rejects_other_files(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text(TEXT, encoding="utf-8")
    result, out = invoke("push", str(path))
    assert result.exit_code != 0
    assert out["error"]["code"] == "USAGE_ERROR"


def test_inspect_prompt(tmp_path):
    path = write_json(tmp_path / "prompt.json", Prompt(TEXT + "\n{{ topic }}").to_dict())
    result, out = invoke("inspect", str(path))
    assert result.exit_code == 0, result.output
    data = out["data"]
    assert data["object_type"] == "Prompt"
    assert data["template_variables"] == ["audience", "topic"]
    assert data["template_error"] is None
    assert data["line_count"] == 2
    assert data["text"] == TEXT + "\n{{ topic }}"


def test_inspect_reports_invalid_templates(tmp_path):
    path = write_json(tmp_path / "prompt.json", {"text": "{{ unclosed", "class_name": "Prompt"})
    result, out = invoke("inspect", str(path))
    assert result.exit_code == 0, result.output
    assert out["data"]["template_variables"] == []
    assert out["data"]["template_error"]


def test_inspect_long_prompt_text(tmp_path):
    # The generic branch used to treat str(obj) as a filesystem path.
    path = write_json(tmp_path / "prompt.json", {"text": "x" * 5000, "class_name": "Prompt"})
    result, out = invoke("inspect", str(path))
    assert result.exit_code == 0, result.output
    assert out["data"]["character_count"] == 5000


def test_inspect_save_as_ep_is_unsupported(tmp_path):
    path = write_json(tmp_path / "prompt.json", {"text": TEXT, "class_name": "Prompt"})
    result, out = invoke("inspect", str(path), "--save", str(tmp_path / "prompt.ep"))
    assert result.exit_code != 0
    assert out["error"]["code"] == "UNSUPPORTED_OBJECT"
    assert not (tmp_path / "prompt.ep").exists()


def test_inspect_save_as_json_writes_the_standalone_form(tmp_path):
    source = write_json(tmp_path / "prompt.json", {"text": TEXT, "class_name": "Prompt"})
    target = tmp_path / "copy.json"
    result, _ = invoke("inspect", str(source), "--save", str(target))
    assert result.exit_code == 0, result.output
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved["edsl_class_name"] == "Prompt"
    assert saved["text"] == TEXT


def test_validate_prompt(tmp_path):
    path = write_json(tmp_path / "prompt.json", {"text": TEXT, "class_name": "Prompt"})
    result, out = invoke("validate", "--file", str(path))
    assert result.exit_code == 0, result.output
    assert out["data"]["object_type"] == "prompt"
    assert out["data"]["template_variables"] == ["audience", "topic"]
    assert out["data"]["normalized"]["edsl_class_name"] == "Prompt"


def test_validate_prompt_warns_on_invalid_templates():
    result, out = invoke(
        "validate", "--json", json.dumps({"text": "{{ unclosed", "edsl_class_name": "Prompt"})
    )
    assert result.exit_code == 0, result.output
    assert out["data"]["valid"] is True
    assert out["warnings"]


def test_validate_rejects_non_string_prompt_text():
    result, out = invoke(
        "validate", "--json", json.dumps({"text": 5, "edsl_class_name": "Prompt"})
    )
    assert result.exit_code != 0
    assert out["error"]["code"] == "VALIDATION_ERROR"


def test_schema_shows_prompt():
    result, out = invoke("schema", "show", "--class", "Prompt")
    assert result.exit_code == 0, result.output
    assert out["data"]["example"]["edsl_class_name"] == "Prompt"
