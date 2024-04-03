import os
import pytest
from edsl.config import CONFIG
from edsl.data.SQLiteDict import SQLiteDict


@pytest.fixture(scope="function")
def sqlite_dict():
    """
    Yields a fresh SQLiteDict instance for each test.
    - Deletes the database file after the test.
    """
    print(CONFIG.get("EDSL_DATABASE_PATH"))
    yield SQLiteDict(db_path=CONFIG.get("EDSL_DATABASE_PATH"))
    os.remove(CONFIG.get("EDSL_DATABASE_PATH").replace("sqlite:///", ""))


@pytest.fixture(scope="function", autouse=True)
async def clear_after_test():
    """
    This fixture does some things after each test (function) runs.
    """
    # Before the test runs, do nothing
    yield
    # After the test completes, do the following

    # e.g., you could clear your database
