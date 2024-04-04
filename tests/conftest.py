import os
import pytest
from edsl.config import CONFIG
from edsl.data.SQLiteDict import SQLiteDict


##############
# Custom pytest options and markers
##############
def pytest_addoption(parser):
    """
    Adds custom CLI options to pytest.
    """
    parser.addoption("--noserver", action="store_true", help="Do not run server tests")
    parser.addoption("--server", action="store_true", help="Run only server tests")


def pytest_configure(config):
    """
    Defines custom pytest markers
    """
    config.addinivalue_line("markers", "server: requires running server")


def pytest_collection_modifyitems(config, items):
    """
    Tells pytest which tests to run based on pytest markers and CLI options.
    """
    if config.getoption("--noserver"):
        skip_server = pytest.mark.skip(reason="Skipping server tests")
        for item in items:
            if "server" in item.keywords:
                item.add_marker(skip_server)

    if config.getoption("--server"):
        skip_notserver = pytest.mark.skip(reason="Skipping non-server tests")
        for item in items:
            if "server" not in item.keywords:
                item.add_marker(skip_notserver)


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
