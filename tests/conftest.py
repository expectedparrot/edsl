import os
import pytest
from edsl.config import CONFIG
from edsl.data.SQLiteDict import SQLiteDict
import subprocess
import os
import signal
import time
import requests
import pytest


##############
# Custom pytest options and markers
##############
def pytest_addoption(parser):
    """
    Adds custom CLI options to pytest.
    """
    parser.addoption("--nocoop", action="store_true", help="Do not run coop tests")
    parser.addoption("--coop", action="store_true", help="Run only coop tests")


def pytest_configure(config):
    """
    Defines custom pytest markers
    """
    config.addinivalue_line("markers", "coop: Requires running coop")
    config.coop_enabled = config.getoption("--coop")


def pytest_collection_modifyitems(config, items):
    """
    Tells pytest which tests to run based on pytest markers and CLI options.
    """
    if config.getoption("--nocoop"):
        skip_coop = pytest.mark.skip(reason="Skipping coop tests")
        for item in items:
            if "coop" in item.keywords:
                item.add_marker(skip_coop)

    if config.getoption("--coop"):
        skip_notcoop = pytest.mark.skip(reason="Skipping non-coop tests")
        for item in items:
            if "coop" not in item.keywords:
                item.add_marker(skip_notcoop)


# Uncomment to automatically try to start the server if --coop is passed

# @pytest.fixture(scope="session", autouse=True)
# def start_server(request):
#     """
#     Starts the server before running tests.
#     """
#     EDSL_PATH = os.getcwd()
#     COOP_PATH = os.path.expanduser("~/coop")
#     if request.config.coop_enabled:
#         os.chdir(COOP_PATH)
#         try:
#             env = {
#                 "PATH": os.path.expanduser("~/coop/venv/bin")
#                 + ":"
#                 + os.environ["PATH"],
#             }
#             subprocess.check_call(["poetry", "run", "make", "fresh-db"], env=env)
#             server_process = subprocess.Popen(
#                 ["poetry", "run", "make", "launch"], preexec_fn=os.setsid, env=env
#             )
#             server_url = "http://localhost:8000/"
#             timeout = time.time() + 30
#             while True:
#                 try:
#                     requests.get(server_url)
#                     print("Server is up and running!")
#                     break
#                 except requests.ConnectionError:
#                     if time.time() > timeout:
#                         print("Failed to connect to the server.")
#                         raise
#                 time.sleep(1)
#         except subprocess.CalledProcessError as e:
#             print(f"An error occurred while setting up the server: {e}")
#             raise e
#         finally:
#             # Return to the original directory
#             os.chdir(EDSL_PATH)

#         # This code will run after the test session is over
#         yield

#         os.killpg(os.getpgid(server_process.pid), signal.SIGTERM)
#         server_process.wait()
#         os.chdir(EDSL_PATH)


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
