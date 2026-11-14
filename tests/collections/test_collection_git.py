import json
from uuid import uuid4

import pytest

from edsl.collections import Collection
from edsl.collections.collection_git import _validate_package


def test_collection_git_round_trip_preserves_order_and_metadata(tmp_path):
    collection = Collection("Research", purpose="Explore", tags=["study"], metadata={"owner": "team"})
    collection.add("survey", str(uuid4()), added_at="2026-01-01T00:00:00Z")
    collection.add("question", str(uuid4()), added_at="2026-01-02T00:00:00Z")
    path = tmp_path / "research.ep"

    collection.git.save(path, message="initial")
    loaded = Collection.git.load(path)

    assert [item.object_type for item in loaded.items] == ["survey", "question"]
    assert loaded.items[0].added_at == "2026-01-01T00:00:00Z"
    assert loaded.tags == ["study"]
    assert loaded.metadata == {"owner": "team"}


def test_collection_git_loads_previous_commit(tmp_path):
    path = tmp_path / "history.ep"
    collection = Collection("Before", metadata={"version": 1})
    first = collection.git.save(path, message="first")
    collection.name = "After"
    collection.metadata["version"] = 2
    collection.git.save(message="second")

    historical = Collection.git.load(path, ref=first["commit"])

    assert historical.name == "Before"
    assert historical.metadata == {"version": 1}


def test_collection_rejects_duplicate_members():
    object_uuid = str(uuid4())
    collection = Collection("Duplicates").add("survey", object_uuid)

    with pytest.raises(ValueError, match="already in this collection"):
        collection.add("survey", object_uuid)


@pytest.mark.parametrize("added_at", ["yesterday", "11/13/2026", "2026-11-13T19:00:00 UTC"])
def test_collection_rejects_non_iso_added_at(added_at):
    with pytest.raises(ValueError, match="ISO 8601"):
        Collection("Dates").add("survey", str(uuid4()), added_at=added_at)
    with pytest.raises(ValueError, match="ISO 8601"):
        Collection.from_dict(
            {
                "name": "Dates",
                "items": [
                    {"object_type": "survey", "object_uuid": str(uuid4()), "added_at": added_at}
                ],
            }
        )


@pytest.mark.parametrize(
    "added_at",
    [
        "2026-11-13T19:00:00+00:00",
        "2026-11-13T19:00:00Z",
        "2026-11-13T19:00:00.123456Z",
        "2026-11-13T19:00:00-05:00",
        "2026-11-13",
    ],
)
def test_collection_accepts_iso_added_at(added_at):
    collection = Collection("Dates").add("survey", str(uuid4()), added_at=added_at)

    assert collection.items[0].added_at == added_at


def test_collection_fetch_metadata_rejects_type_mismatch(monkeypatch):
    from edsl.coop.coop import Coop

    object_uuid = str(uuid4())
    collection = Collection("Types").add("survey", object_uuid)

    monkeypatch.setattr(Coop, "get_metadata", lambda self, _uuid: {"object_type": "question"})
    with pytest.raises(ValueError, match="Coop reports 'question'"):
        collection.fetch_metadata()


@pytest.mark.parametrize("manifest", [[], None, "not an object"])
def test_collection_package_validation_rejects_non_object_manifest(tmp_path, manifest):
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "collection.json").write_text("{}", encoding="utf-8")

    errors = _validate_package(tmp_path)

    assert errors == ["invalid manifest.json: expected a JSON object"]


def _saved_json_collection(tmp_path):
    collection = Collection("Saved", tags=["json"])
    collection.add("survey", str(uuid4()), added_at="2026-01-01T00:00:00Z")
    path = tmp_path / "collection.json"
    collection.save(str(path))
    return collection, path


def test_saved_json_collection_loads_in_the_cli(tmp_path):
    from edsl.cli_shared import load_openable_json

    collection, path = _saved_json_collection(tmp_path)

    loaded = load_openable_json(path)

    assert type(loaded) is Collection
    assert loaded.to_dict(add_edsl_version=False) == collection.to_dict(add_edsl_version=False)


def test_ep_inspect_reads_a_saved_json_collection(tmp_path):
    from click.testing import CliRunner

    import edsl.__main__ as cli_module

    _, path = _saved_json_collection(tmp_path)

    result = CliRunner().invoke(cli_module.app, ["inspect", str(path)])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)["data"]
    assert data["object_type"] == "Collection"
    assert data["length"] == 1


def test_ep_push_asks_for_a_package_for_a_json_collection(tmp_path):
    from click.testing import CliRunner

    import edsl.__main__ as cli_module

    _, path = _saved_json_collection(tmp_path)

    result = CliRunner().invoke(cli_module.app, ["push", str(path)])

    assert result.exit_code == cli_module.EXIT_USAGE
    error = json.loads(result.output)["error"]
    assert error["code"] == "USAGE_ERROR"
    assert ".ep package" in error["message"]
