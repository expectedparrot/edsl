import os
from getpass import getpass
import pytest
from unittest.mock import patch, mock_open
from edsl.config import Config, CONFIG_MAP
from edsl.exceptions import (
    InvalidEnvironmentVariableError,
    MissingEnvironmentVariableError,
)

# MOCK VARS
MOCK_ENV_VARS = {
    "EDSL_RUN_MODE": "development",
    "OPENAI_API_KEY": "some_key",
}
# FIXTURES
# capture the original get env before patching
original_getenv = os.getenv


# patch get_env
def mock_getenv(var_name, default=None):
    """Mocks os.getenv()."""
    return MOCK_ENV_VARS.get(var_name, original_getenv(var_name, default))


@pytest.fixture(scope="function")
def mock_env():
    """Mock os.getenv() for testing."""
    with patch("os.getenv", mock_getenv):
        yield


@pytest.fixture(scope="function")
def test_config(mock_env):
    """Yield a test config object to tests, with mock env var values."""
    config = Config()
    yield config


# TESTS


def test_config_store_and_load(test_config):
    """Config should store the & sets env vars."""
    test_config.show()
    # both in the object and in the env for optional vars that are given
    assert test_config.EDSL_RUN_MODE == MOCK_ENV_VARS["EDSL_RUN_MODE"]
    assert os.getenv("EDSL_RUN_MODE") == test_config.EDSL_RUN_MODE
    assert test_config.OPENAI_API_KEY == MOCK_ENV_VARS["OPENAI_API_KEY"]
    assert os.getenv("OPENAI_API_KEY") == test_config.OPENAI_API_KEY
    # both in the object and in the env for vars that are not given but have default
    assert test_config.EXPECTED_PARROT_API_KEY == CONFIG_MAP.get(
        "EXPECTED_PARROT_API_KEY"
    ).get("default")
    assert os.getenv("EXPECTED_PARROT_API_KEY") == test_config.EXPECTED_PARROT_API_KEY


def test_config_invalid_var(mock_env):
    """Test that Config() raises an error if a var value is not allowed."""
    with patch(
        "os.getenv",
        lambda var_name, default=None: (
            "invalid" if var_name == "EDSL_RUN_MODE" else mock_getenv(var_name)
        ),
    ):
        with pytest.raises(InvalidEnvironmentVariableError):
            Config()


def test_config_show_method(test_config, capsys):
    test_config.show()
    captured = capsys.readouterr()
    assert "Here are the current configuration settings:" in captured.out


# @patch("getpass.getpass")
# def test_config_set_env_var(getpass_mock, test_config, capsys):
#     # Set up the mock for  to return a specific value
#     user_input_value = "new_api_key"
#     masked_value = "ne********ey"
#     getpass_mock.return_value = user_input_value
#     # Set EDSL_RUN_MODE to production to avoid raising the exception
#     test_config.EDSL_RUN_MODE = "production"
#     # Call the method that prompts for user input and writes to the .env file
#     test_config._set_env_var("OPENAI_API_KEY", CONFIG_MAP.get("OPENAI_API_KEY"))
#     # Capture the printed output
#     captured = capsys.readouterr()
#     # Asserts to check the method behavior
#     assert "Enter the value below and press enter:" in captured.out
#     assert (
#         f"Environment variable OPENAI_API_KEY set successfully to {masked_value}."
#         in captured.out
#     )
#     # check if the environment variable was set correctly
#     assert os.environ["OPENAI_API_KEY"] == user_input_value


def test_config_get_method(test_config, capsys):
    assert test_config.get("EDSL_RUN_MODE") == test_config.EDSL_RUN_MODE
    assert test_config.get("EDSL_DATABASE_PATH") == test_config.EDSL_DATABASE_PATH
    assert test_config.get("OPENAI_API_KEY") == test_config.OPENAI_API_KEY
    with pytest.raises(InvalidEnvironmentVariableError):
        test_config.get("INVALID")
    # delete OPENAI_API_KEY from the object
    del test_config.OPENAI_API_KEY
    with pytest.raises(MissingEnvironmentVariableError):
        test_config.get("OPENAI_API_KEY")
