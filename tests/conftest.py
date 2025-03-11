import asyncio
import os
import pytest
import time
import subprocess
import sys
import requests
import signal

from typing import Any

from edsl.config import CONFIG
from edsl.caching.sql_dict import SQLiteDict
from edsl.enums import InferenceServiceType
from edsl.language_models import LanguageModel


import socket


def is_port_in_use(port):
    """Check if a port is in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", port))
            return False
        except OSError:
            return True


def pytest_sessionstart(session):
    """
    Pytest fixture to start a FastAPI server for token bucket testing.
    """
    # Check if port is already in use
    import os

    if is_port_in_use(8001):
        print("Warning: Port is already in use. Attempting to clean up...")
        if os.name != "nt":  # Unix-like systems
            try:
                subprocess.run(["pkill", "-f", "TokenBucketAPI.py"], check=False)
                time.sleep(2)  # Give the system time to release the port
            except Exception as e:
                print(f"Failed to kill existing process: {e}")
        else:  # Windows
            try:
                subprocess.run(
                    ["taskkill", "/F", "/FI", "IMAGENAME eq python.exe"], check=False
                )
                time.sleep(2)
            except Exception as e:
                print(f"Failed to kill existing process: {e}")

        # Check again after cleanup attempt
        if is_port_in_use(8002):
            raise RuntimeError(
                "Port 8002 is still in use. Please manually kill the process using it."
            )
    print("Session starting")
    config = session.config

    if not hasattr(config, "token_bucket_enabled"):
        print("Token bucket testing is not enabled")
        return

    if not config.token_bucket_enabled:
        return

    try:
        # Start the FastAPI server in a subprocess
        server_cmd = [sys.executable, "edsl/jobs/buckets/TokenBucketAPI.py"]
        print("Running server command:", server_cmd)

        # Store the process in the session for cleanup
        session.server_process = subprocess.Popen(
            server_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=(
                os.setsid if os.name != "nt" else None
            ),  # Handle Windows compatibility
            text=True,  # Use text mode for readable output
            bufsize=1,  # Line buffered
        )

        # Start threads to continuously read output
        def print_output(pipe, prefix):
            for line in iter(pipe.readline, ""):
                print(f"{prefix}: {line.strip()}")

        import threading

        stdout_thread = threading.Thread(
            target=print_output,
            args=(session.server_process.stdout, "SERVER STDOUT"),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=print_output,
            args=(session.server_process.stderr, "SERVER STDERR"),
            daemon=True,
        )
        stdout_thread.start()
        stderr_thread.start()

        # Wait until the server is ready
        import os

        server_url = os.environ.get(
            "EDSL_REMOTE_TOKEN_BUCKET_URL", "http://localhost:8001"
        )
        # server_url = "http://localhost:8001"  # Updated port to match the server
        timeout = time.time() + 30

        while True:
            try:
                r = requests.get(server_url)
                # Accept both 200 and 404 as valid responses - 404 means server is running but endpoint doesn't exist
                if r.status_code in (200, 404):
                    print(
                        "Token Bucket Server is up and running! (Response code: {})".format(
                            r.status_code
                        )
                    )
                    break
            except requests.ConnectionError:
                if time.time() > timeout:
                    raise RuntimeError("Server didn't start in time")
                print("Waiting for server to start...")
                time.sleep(1)
                continue
            except Exception as e:
                print(f"Unexpected error while connecting to server: {e}")
                raise

    except Exception as e:
        print(f"Error starting token bucket server: {e}")
        if hasattr(session, "server_process"):
            try:
                # Capture any final output before terminating
                stdout, stderr = session.server_process.communicate(timeout=5)
                print("Final server output before termination:")
                if stdout:
                    print("STDOUT:", stdout)
                if stderr:
                    print("STDERR:", stderr)

                # Terminate the process
                if os.name != "nt":
                    os.killpg(os.getpgid(session.server_process.pid), signal.SIGTERM)
                else:
                    session.server_process.terminate()
            except Exception as cleanup_error:
                print(f"Error during cleanup: {cleanup_error}")
        raise


def pytest_sessionfinish(session, exitstatus):
    config = session.config
    if getattr(config, "token_bucket_enabled", False):
        # Shut down the server
        print("Shutting down the Token Bucket Server...")
        os.killpg(os.getpgid(session.server_process.pid), signal.SIGTERM)
        session.server_process.wait(timeout=5)
        print("Token Bucket Server has been shut down.")


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
    parser.addoption(
        "--token-bucket", action="store_true", help="Run using remote token bucket"
    )


def pytest_configure(config):
    """
    Defines custom pytest markers
    """
    config.addinivalue_line("markers", "coop: Requires running coop")
    config.coop_enabled = config.getoption("--coop")
    config.addinivalue_line(
        "markers", "linux_only: Requires running linux - test will not pass on windows"
    )
    if config.getoption("--token-bucket"):
        # config.setini("EDSL_REMOTE_TOKEN_BUCKET_URL", "http://localhost:8001")
        os.environ["EDSL_REMOTE_TOKEN_BUCKET_URL"] = "http://localhost:8001"
        config.token_bucket_enabled = True
    else:
        config.token_bucket_enabled = False


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


def pytest_sessionfinish(session, exitstatus):
    config = session.config
    if getattr(config, "token_bucket_enabled", False):
        # Shut down the server
        print("Shutting down the Token Bucket Server...")
        os.killpg(os.getpgid(session.server_process.pid), signal.SIGTERM)
        session.server_process.wait(timeout=5)
        print("Token Bucket Server has been shut down.")


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
    print(CONFIG.get("EDSL_DATABASE_PATH"))
    yield SQLiteDict(db_path=CONFIG.get("EDSL_DATABASE_PATH"))
    os.remove(CONFIG.get("EDSL_DATABASE_PATH").replace("sqlite:///", ""))


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
