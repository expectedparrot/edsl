import pytest
import tempfile
import os
from typing import Optional
from edsl.data.CacheEntry import CacheEntry
from edsl.data.SQLiteDict import SQLiteDict

@pytest.fixture
def temp_db_path() -> str:
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        db_path = temp_file.name
    yield db_path
    os.unlink(db_path)

@pytest.fixture
def sqlite_dict(temp_db_path: str) -> SQLiteDict:
    return SQLiteDict(db_path=temp_db_path)

def test_set_and_get_item(sqlite_dict: SQLiteDict):
    key = "test_key"
    value = CacheEntry.example()
    sqlite_dict[key] = value
    assert sqlite_dict[key] == value

def test_get_nonexistent_key(sqlite_dict: SQLiteDict):
    with pytest.raises(KeyError):
        _ = sqlite_dict["nonexistent_key"]

def test_get_with_default(sqlite_dict: SQLiteDict):
    default_value = "default"
    assert sqlite_dict.get("nonexistent_key", default_value) == default_value

def test_update(sqlite_dict: SQLiteDict):
    new_dict = {"key1": CacheEntry.example(), "key2": CacheEntry.example()}
    sqlite_dict.update(new_dict)
    assert sqlite_dict["key1"] == new_dict["key1"]
    assert sqlite_dict["key2"] == new_dict["key2"]

def test_update_overwrite(sqlite_dict: SQLiteDict):
    key = "test_key"
    old_value = CacheEntry.example()
    new_value = CacheEntry.example()
    sqlite_dict[key] = old_value
    sqlite_dict.update({key: new_value}, overwrite=True)
    assert sqlite_dict[key] == new_value

def test_values(sqlite_dict: SQLiteDict):
    values = [CacheEntry.example(), CacheEntry.example()]
    for i, value in enumerate(values):
        sqlite_dict[f"key{i}"] = value
    assert list(sqlite_dict.values()) == values

def test_items(sqlite_dict: SQLiteDict):
    items = [("key1", CacheEntry.example()), ("key2", CacheEntry.example())]
    for key, value in items:
        sqlite_dict[key] = value
    assert list(sqlite_dict.items()) == items

def test_delete_item(sqlite_dict: SQLiteDict):
    key = "test_key"
    sqlite_dict[key] = CacheEntry.example()
    del sqlite_dict[key]
    assert key not in sqlite_dict

def test_delete_nonexistent_key(sqlite_dict: SQLiteDict):
    with pytest.raises(KeyError):
        del sqlite_dict["nonexistent_key"]

def test_contains(sqlite_dict: SQLiteDict):
    key = "test_key"
    sqlite_dict[key] = CacheEntry.example()
    assert key in sqlite_dict
    assert "nonexistent_key" not in sqlite_dict

def test_iter(sqlite_dict: SQLiteDict):
    keys = ["key1", "key2", "key3"]
    for key in keys:
        sqlite_dict[key] = CacheEntry.example()
    assert list(iter(sqlite_dict)) == keys

def test_len(sqlite_dict: SQLiteDict):
    assert len(sqlite_dict) == 0
    sqlite_dict["key1"] = CacheEntry.example()
    assert len(sqlite_dict) == 1

def test_keys(sqlite_dict: SQLiteDict):
    keys = ["key1", "key2"]
    for key in keys:
        sqlite_dict[key] = CacheEntry.example()
    assert list(sqlite_dict.keys()) == keys