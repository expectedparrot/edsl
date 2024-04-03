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


def test_config_show_method(test_config, capsys):
    test_config.show()
    captured = capsys.readouterr()
    assert "Here are the current configuration settings:" in captured.out


def test_config_get_method(test_config, capsys):
    assert test_config.get("EDSL_RUN_MODE") == test_config.EDSL_RUN_MODE
    assert test_config.get("EDSL_DATABASE_PATH") == test_config.EDSL_DATABASE_PATH
    with pytest.raises(InvalidEnvironmentVariableError):
        test_config.get("INVALID")
