import os
import shutil
import sqlite3
import pytest
from edsl.data import CacheHandler, CacheEntry, Cache


@pytest.fixture
def cache_handler():
    # Create a temporary directory for testing
    temp_dir = "tests/.temp_cache"
    os.makedirs(temp_dir, exist_ok=True)

    # Update the cache path to use the temporary directory
    CacheHandler.CACHE_PATH = os.path.join(temp_dir, "data.db")

    # Create an instance of CacheHandler
    handler = CacheHandler(test=True)

    yield handler

    # Clean up the temporary directory after testing
    shutil.rmtree(temp_dir)


def test_create_cache_directory(cache_handler):
    assert os.path.exists("tests/.temp_cache")


def test_gen_cache(cache_handler):
    cache = cache_handler.gen_cache()
    assert isinstance(cache, Cache)


def test_get_cache(cache_handler):
    cache = cache_handler.get_cache()
    assert isinstance(cache, Cache)


@pytest.mark.linux_only
def test_from_old_sqlite_cache_db(cache_handler, tmp_path):
    # Create a temporary old-style cache database for testing
    old_cache_path = os.path.join(tmp_path, "old_cache.db")
    conn = sqlite3.connect(old_cache_path)
    with conn:
        conn.execute(
            """
            CREATE TABLE responses (
                id INTEGER NOT NULL,
                model VARCHAR(100) NOT NULL,
                parameters TEXT NOT NULL,
                system_prompt TEXT NOT NULL,
                prompt TEXT NOT NULL,
                output TEXT NOT NULL,
                PRIMARY KEY (id)
            )
        """
        )
        conn.execute(
            """
            INSERT INTO responses (model, parameters, system_prompt, prompt, output)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                "test_model",
                str({"key": "value"}),
                "test_system_prompt",
                "test_prompt",
                "test_output",
            ),
        )
    conn.close()

    # Call the from_old_sqlite_cache_db method
    newdata = cache_handler.from_old_sqlite_cache(old_cache_path)

    # Assert the converted data
    assert len(newdata) == 1
    entry = list(newdata.values())[0]
    assert isinstance(entry, CacheEntry)
    assert entry.model == "test_model"
    assert entry.parameters == {"key": "value"}
    assert entry.system_prompt == "test_system_prompt"
    assert entry.user_prompt == "test_prompt"


def test_add_from_dict(cache_handler):
    newdata = {
        "key1": CacheEntry(
            model="model1",
            parameters={"param1": "value1"},
            system_prompt="system_prompt1",
            user_prompt="prompt1",
            output="output1",
        ),
        "key2": CacheEntry(
            model="model2",
            parameters={"param2": "value2"},
            system_prompt="system_prompt2",
            user_prompt="prompt2",
            output="output2",
        ),
    }
    cache_handler.cache.add_from_dict(newdata)

    assert len(cache_handler.cache.data) == 2
    assert cache_handler.cache.data["key1"].model == "model1"
    assert cache_handler.cache.data["key1"].parameters == {"param1": "value1"}
    assert cache_handler.cache.data["key1"].system_prompt == "system_prompt1"
    assert cache_handler.cache.data["key1"].user_prompt == "prompt1"
    assert cache_handler.cache.data["key1"].output == "output1"
    assert cache_handler.cache.data["key2"].model == "model2"
    assert cache_handler.cache.data["key2"].parameters == {"param2": "value2"}
    assert cache_handler.cache.data["key2"].system_prompt == "system_prompt2"
    assert cache_handler.cache.data["key2"].user_prompt == "prompt2"
    assert cache_handler.cache.data["key2"].output == "output2"
