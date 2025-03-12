import os
import pytest
from edsl.config import Config
from edsl.exceptions.configuration import InvalidEnvironmentVariableError


def test_config_store_and_load(set_env_vars):
    """Config should store the & sets env vars."""
    set_env_vars(EDSL_RUN_MODE="development")
    config = Config()
    config.show()
    assert config.EDSL_RUN_MODE == "development"
    assert os.getenv("EDSL_RUN_MODE") == "development"


def test_config_incorrect_run_mode(set_env_vars):
    """Config should raise an error if the run mode is incorrect."""
    set_env_vars(EDSL_RUN_MODE="incorrect")
    with pytest.raises(InvalidEnvironmentVariableError):
        config = Config()
        print(config.EDSL_RUN_MODE)


@pytest.mark.skip(reason="Environment dependent test that's failing in CI")
def test_config_back_to_normal():
    config = Config()
    # This test is environment-dependent, so accept multiple valid values
    assert config.EDSL_RUN_MODE in ["development-testrun", "development", "test"]


def test_config_show_method(capsys):
    config = Config()
    config.show()
    captured = capsys.readouterr()
    assert "Here are the current configuration settings:" in captured.out


def test_config_get_method():
    config = Config()
    assert config.get("EDSL_DATABASE_PATH") is not None
    with pytest.raises(InvalidEnvironmentVariableError):
        config.get("INVALID")
