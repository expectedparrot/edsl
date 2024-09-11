import asyncio
import os
import pytest
from typing import Any
from edsl.config import CONFIG
from edsl.data.SQLiteDict import SQLiteDict
from edsl.enums import InferenceServiceType
from edsl.language_models.LanguageModel import LanguageModel


##############
# Custom pytest options and markers
##############
def pytest_addoption(parser):
    """
    Adds custom CLI options to pytest.
    """
    parser.addoption("--nocoop", action="store_true", help="Do not run coop tests")
    parser.addoption("--coop", action="store_true", help="Run only coop tests")
    parser.addoption("--windows", action="store_true", help="Run only windows tests")


def pytest_configure(config):
    """
    Defines custom pytest markers
    """
    config.addinivalue_line("markers", "coop: Requires running coop")
    config.coop_enabled = config.getoption("--coop")
    config.addinivalue_line(
        "markers", "linux_only: Requires running linux - test will not pass on windows"
    )


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

    if config.getoption("--windows"):
        skip_notwindows = pytest.mark.skip(reason="Skipping non-windows tests")
        for item in items:
            if "linux_only" in item.keywords:
                item.add_marker(skip_notwindows)


##############
# Fixtures
##############

# TODO: Uncomment to automatically try to start the server if --coop is passed
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


@pytest.fixture
def set_env_vars():
    """
    Sets environment variables for the duration of the test.
    After the test, it restores the env to their original state.

    Usage:
    - Pass this fixture to the test
    - Call the fixture, e.g. `set_env_vars(ENV_VAR1='value1', ENV_VAR2='value2')`
    - Set a variable equal to None to delete it from the env
    """
    original_env = os.environ.copy()

    def _set_env_vars(**env_vars):
        for var, value in env_vars.items():
            if value is None and var in os.environ:
                del os.environ[var]
            else:
                os.environ[var] = value

    yield _set_env_vars

    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture(scope="function")
def sqlite_dict():
    """
    Yields a fresh SQLiteDict instance for each test.
    - Deletes the database file after the test.
    """
    import uuid

    db_path = CONFIG.get("EDSL_DATABASE_PATH") + str(uuid.uuid4())
    yield SQLiteDict(db_path=db_path)
    os.remove(db_path.replace("sqlite:///", ""))


@pytest.fixture
def language_model_good():
    """
    Provides a good language model for testing.
    """

    class TestLanguageModelGood(LanguageModel):
        use_cache = False
        _model_ = "test"
        _parameters_ = {"temperature": 0.5}
        _inference_service_ = InferenceServiceType.TEST.value
        key_sequence = ["message", "answer"]

        async def async_execute_model_call(
            self, user_prompt: str, system_prompt: str
        ) -> dict[str, Any]:
            await asyncio.sleep(0.1)
            return {"message": """{"answer": "Hello world"}"""}

        # def parse_response(self, raw_response: dict[str, Any]) -> str:
        #     return raw_response["message"]

    return TestLanguageModelGood()


@pytest.fixture(scope="function", autouse=True)
async def clear_after_test_function():
    """
    Clean before and after each test.
    """
    # Do nothing before the test runs
    yield
    # TODO: Do some things after the test, e.g., clear the database


@pytest.fixture(scope="session", autouse=True)
def clear_after_test_session():
    """
    Clean before and after all the test session.
    """
    os.system("make clean")
    os.system("make clean-test")
    yield
    os.system("make clean")
    os.system("make clean-test")
