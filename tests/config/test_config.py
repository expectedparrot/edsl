import os
import pytest
from edsl.config import Config
from edsl.config.config_class import InvalidEnvironmentVariableError


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


def test_config_back_to_normal():
    config = Config()
    assert config.EDSL_RUN_MODE == "development-testrun"


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
