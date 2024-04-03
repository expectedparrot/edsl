import pytest
from edsl.data import CacheEntry
from edsl.data.LocalDict import main


def test_LocalDict_set_and_get_item(local_dict):
    key = "test_key"
    value = CacheEntry.example()
    local_dict[key] = value
    assert local_dict[key] == value


def test_LocalDict_get_nonexistent_key(local_dict):
    with pytest.raises(KeyError):
        _ = local_dict["nonexistent_key"]


def test_LocalDict_get_with_default(local_dict):
    default_value = "default"
    assert local_dict.get("nonexistent_key", default_value) == default_value


def test_LocalDict_update(local_dict):
    new_dict = {"key1": CacheEntry.example(), "key2": CacheEntry.example()}
    local_dict.update(new_dict)
    assert local_dict["key1"] == new_dict["key1"]
    assert local_dict["key2"] == new_dict["key2"]


def test_LocalDict_update_overwrite(local_dict):
    key = "test_key"
    old_value = CacheEntry.example()
    new_value = CacheEntry.example()
    local_dict[key] = old_value
    local_dict.update({key: new_value}, overwrite=True)
    assert local_dict[key] == new_value


def test_LocalDict_values(local_dict):
    values = [CacheEntry.example(), CacheEntry.example()]
    for i, value in enumerate(values):
        local_dict[f"key{i}"] = value
    assert list(local_dict.values()) == values


def test_LocalDict_items(local_dict):
    items = [("key1", CacheEntry.example()), ("key2", CacheEntry.example())]
    for key, value in items:
        local_dict[key] = value
    assert list(local_dict.items()) == items


def test_LocalDict_delete_item(local_dict):
    key = "test_key"
    local_dict[key] = CacheEntry.example()
    del local_dict[key]
    assert key not in local_dict


def test_LocalDict_delete_nonexistent_key(local_dict):
    with pytest.raises(KeyError):
        del local_dict["nonexistent_key"]


def test_LocalDict_contains(local_dict):
    key = "test_key"
    local_dict[key] = CacheEntry.example()
    assert key in local_dict
    assert "nonexistent_key" not in local_dict


def test_LocalDict_iter(local_dict):
    keys = ["key1", "key2", "key3"]
    for key in keys:
        local_dict[key] = CacheEntry.example()
    assert list(iter(local_dict)) == keys


def test_LocalDict_len(local_dict):
    assert len(local_dict) == 0
    local_dict["key1"] = CacheEntry.example()
    assert len(local_dict) == 1


def test_LocalDict_keys(local_dict):
    keys = ["key1", "key2"]
    for key in keys:
        local_dict[key] = CacheEntry.example()
    assert list(local_dict.keys()) == keys


def test_LocalDict_main(local_dict):
    main()
