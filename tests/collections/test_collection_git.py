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
