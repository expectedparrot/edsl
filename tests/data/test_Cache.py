import pytest
import os
from edsl import CONFIG
from edsl.data.CacheEntry import CacheEntry
from edsl.data.Cache import Cache

from edsl import QuestionFreeText
from edsl.data.Cache import Cache

@pytest.fixture(scope="module")
def db_path():
    return CONFIG.get("EDSL_DATABASE_PATH").replace("sqlite:///", "")

@pytest.fixture(scope="function")
def cache_example():
    return Cache.example()

@pytest.fixture(scope="function")
def cache_empty():
    return Cache()

def test_fetch_nonexistent_entry():
    cache = Cache()
    assert cache.fetch(
        model="gpt-3.5-turbo",
        parameters="{'temperature': 0.5}",
        system_prompt="The quick brown fox jumps over the lazy dog.",
        user_prompt="What does the fox say?",
        iteration=1,
    ) == None

def test_fetch_existing_entry(cache_example):
    cache = cache_example
    assert cache.fetch(**cache.fetch_input_example()) == "The fox says 'hello'"

def test_store_with_immediate_write():
    cache = Cache()
    input = CacheEntry.store_input_example()
    cache.store(**input)
    assert list(cache.data.keys()) == ["5513286eb6967abc0511211f0402587d"]

def test_store_with_delayed_write():
    cache = Cache(immediate_write=False)
    input = CacheEntry.store_input_example()
    cache.store(**input)
    assert list(cache.data.keys()) == []

    cache = cache.__enter__()
    cache.store(**input)
    assert list(cache.data.keys()) == []
    cache.__exit__(None, None, None)
    assert list(cache.data.keys()) == ["5513286eb6967abc0511211f0402587d"]

def test_add_entries_from_dict_immediate_and_delayed_write():
    # Immediate write
    cache = Cache()
    data = {"poo": CacheEntry.example(), "bandits": CacheEntry.example()}
    cache.add_from_dict(new_data=data)
    assert cache.data["poo"] == CacheEntry.example()

    # Delayed write
    cache = Cache()
    cache.add_from_dict(new_data=data, write_now=False)
    assert cache.data == {}
    cache.__exit__(None, None, None)
    assert cache.data["poo"] == CacheEntry.example()

def test_file_operations(cache_example, db_path):
    # Test operations involving file IO such as jsonl and SQLite
    # Add relevant assertions and operations as in the provided main function
    pass

def test_cache_comparison_and_operations(cache_empty, cache_example):
    # Tests involving cache comparison and operations like __len__, __eq__, __add__
    assert len(cache_empty) == 0
    assert len(cache_example) == 1
    assert cache_empty == cache_empty
    assert cache_example == cache_example
    assert cache_empty != cache_example
    assert len(cache_empty + cache_example) == 1
    assert (cache_empty + cache_example) == cache_example


def test_throw_file_note_found_error():
    try:
        Cache.from_jsonl("non_existent_file.jsonl")
    except FileNotFoundError as e:
        assert True

def test_caching(language_model_good):
    m = language_model_good
    m.remote = False
    c = Cache()
    results = QuestionFreeText.example().by(m).run(cache=c, 
                                                   batch_mode = True, 
                                                   check_api_keys = False, 
                                                   remote = False)
    assert not results.select(
        "raw_model_response.how_are_you_raw_model_response"
    ).first()["cached_response"]
    results = QuestionFreeText.example().by(m).run(cache=c, batch_mode = True, check_api_keys = False)
    assert results.select("raw_model_response.how_are_you_raw_model_response").first()[
        "cached_response"
    ]
