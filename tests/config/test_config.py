import os
import pytest
from pathlib import Path
from edsl.config import Config, CONFIG
from edsl.config.config_class import InvalidEnvironmentVariableError, modify_settings


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


def test_config_valid_table_renderer(set_env_vars):
    """Config should accept valid table renderer values."""
    for renderer in ["pandas", "datatables", "rich"]:
        set_env_vars(EDSL_DEFAULT_TABLE_RENDERER=renderer)
        config = Config()
        assert config.EDSL_DEFAULT_TABLE_RENDERER == renderer


def test_config_invalid_table_renderer(set_env_vars):
    """Config should raise an error for invalid table renderer values."""
    set_env_vars(EDSL_DEFAULT_TABLE_RENDERER="invalid_renderer")
    with pytest.raises(InvalidEnvironmentVariableError) as exc_info:
        config = Config()
    assert "invalid_renderer" in str(exc_info.value)
    assert "pandas, datatables, rich" in str(exc_info.value)


def test_modify_settings_valid_renderer(tmp_path, monkeypatch):
    """modify_settings should accept valid table renderer values."""
    # Change to temp directory to avoid modifying actual .env
    monkeypatch.chdir(tmp_path)

    modify_settings(EDSL_DEFAULT_TABLE_RENDERER="datatables")

    # Check that .env was created with the setting
    env_file = tmp_path / ".env"
    assert env_file.exists()
    content = env_file.read_text()
    # set_key may add quotes, check for key and value separately
    assert "EDSL_DEFAULT_TABLE_RENDERER" in content
    assert "datatables" in content


def test_modify_settings_invalid_renderer(tmp_path, monkeypatch):
    """modify_settings should reject invalid table renderer values."""
    # Change to temp directory to avoid modifying actual .env
    monkeypatch.chdir(tmp_path)

    with pytest.raises(InvalidEnvironmentVariableError) as exc_info:
        modify_settings(EDSL_DEFAULT_TABLE_RENDERER="invalid_value")

    assert "invalid_value" in str(exc_info.value)
    assert "pandas, datatables, rich" in str(exc_info.value)

    # Ensure .env was not created since validation failed
    env_file = tmp_path / ".env"
    assert not env_file.exists()


def test_modify_settings_multiple_values(tmp_path, monkeypatch, capsys):
    """modify_settings should handle multiple settings at once."""
    # Change to temp directory to avoid modifying actual .env
    monkeypatch.chdir(tmp_path)

    modify_settings(
        EDSL_DEFAULT_TABLE_RENDERER="rich",
        EDSL_VERBOSE_MODE="True"
    )

    # Check that .env was created with both settings
    env_file = tmp_path / ".env"
    assert env_file.exists()
    content = env_file.read_text()
    # set_key may add quotes, check for keys and values separately
    assert "EDSL_DEFAULT_TABLE_RENDERER" in content and "rich" in content
    assert "EDSL_VERBOSE_MODE" in content and "True" in content

    # Check output message
    captured = capsys.readouterr()
    assert "Configuration updated successfully" in captured.out
    assert "EDSL_DEFAULT_TABLE_RENDERER = rich" in captured.out
    assert "EDSL_VERBOSE_MODE = True" in captured.out


def test_modify_settings_update_existing(tmp_path, monkeypatch):
    """modify_settings should update existing values in .env file."""
    # Change to temp directory
    monkeypatch.chdir(tmp_path)

    # Create initial .env with a value
    env_file = tmp_path / ".env"
    env_file.write_text("EDSL_DEFAULT_TABLE_RENDERER=pandas\nEDSL_VERBOSE_MODE=False\n")

    # Update one value
    modify_settings(EDSL_DEFAULT_TABLE_RENDERER="datatables")

    # Check that the value was updated and other values preserved
    content = env_file.read_text()
    # set_key may add quotes, check for key and value separately
    assert "EDSL_DEFAULT_TABLE_RENDERER" in content
    assert "datatables" in content
    assert "EDSL_VERBOSE_MODE" in content and "False" in content
    # Ensure old value is not present
    assert "pandas" not in content or content.count("EDSL_DEFAULT_TABLE_RENDERER") == 1


def test_config_to_dict():
    """Config.to_dict() should return a dictionary of all settings."""
    config = Config()
    config_dict = config.to_dict()

    assert isinstance(config_dict, dict)
    assert len(config_dict) > 0
    assert "EDSL_RUN_MODE" in config_dict


def test_config_modify_method(tmp_path, monkeypatch):
    """CONFIG.modify() should work the same as modify_settings()."""
    # Change to temp directory to avoid modifying actual .env
    monkeypatch.chdir(tmp_path)

    # Create a new Config instance for testing
    config = Config()

    # Test modifying a setting
    config.modify(EDSL_DEFAULT_TABLE_RENDERER="datatables")

    # Check that the setting was updated in memory
    assert config.EDSL_DEFAULT_TABLE_RENDERER == "datatables"

    # Check that .env was created
    env_file = tmp_path / ".env"
    assert env_file.exists()
    content = env_file.read_text()
    # set_key may add quotes, check for key and value separately
    assert "EDSL_DEFAULT_TABLE_RENDERER" in content
    assert "datatables" in content


def test_config_modify_invalid_key(tmp_path, monkeypatch):
    """CONFIG.modify() should reject invalid configuration keys."""
    monkeypatch.chdir(tmp_path)

    config = Config()

    with pytest.raises(InvalidEnvironmentVariableError) as exc_info:
        config.modify(INVALID_CONFIG_KEY="some_value")

    assert "INVALID_CONFIG_KEY" in str(exc_info.value)
    assert "not a valid configuration variable" in str(exc_info.value)


def test_config_modify_invalid_value(tmp_path, monkeypatch):
    """CONFIG.modify() should reject invalid values for constrained settings."""
    monkeypatch.chdir(tmp_path)

    config = Config()

    with pytest.raises(InvalidEnvironmentVariableError) as exc_info:
        config.modify(EDSL_DEFAULT_TABLE_RENDERER="invalid_renderer")

    assert "invalid_renderer" in str(exc_info.value)
    assert "pandas, datatables, rich" in str(exc_info.value)


def test_config_repr_methods():
    """Config should have _eval_repr_ and _summary_repr methods."""
    config = Config()

    # Test _eval_repr_
    eval_repr = config._eval_repr_()
    assert "Config(" in eval_repr
    assert isinstance(eval_repr, str)

    # Test _summary_repr
    summary_repr = config._summary_repr()
    assert "Config(" in summary_repr
    assert "num_settings=" in summary_repr
    assert isinstance(summary_repr, str)


def test_config_repr_with_doctest_env(monkeypatch):
    """Config.__repr__ should use _eval_repr_ when EDSL_RUNNING_DOCTESTS is True."""
    config = Config()

    # Test with EDSL_RUNNING_DOCTESTS=True
    monkeypatch.setenv("EDSL_RUNNING_DOCTESTS", "True")
    repr_output = repr(config)
    assert "Config(" in repr_output
    # eval_repr should be simpler than summary_repr

    # Test with EDSL_RUNNING_DOCTESTS not set
    monkeypatch.delenv("EDSL_RUNNING_DOCTESTS", raising=False)
    repr_output = repr(config)
    assert "Config(" in repr_output
    assert "num_settings=" in repr_output  # Should show full rich display


def test_config_to_scenario_list():
    """Config.to_scenario_list() should convert config to a ScenarioList."""
    config = Config()
    scenario_list = config.to_scenario_list()

    # Check it returns a ScenarioList
    from edsl.scenarios import ScenarioList
    assert isinstance(scenario_list, ScenarioList)

    # Check it has the right number of scenarios
    assert len(scenario_list) == len(config.to_dict())

    # Check each scenario has the expected keys
    for scenario in scenario_list:
        assert "setting" in scenario
        assert "value" in scenario
        assert "description" in scenario

    # Check the data is correct
    first_scenario = scenario_list[0]
    setting_name = first_scenario["setting"]
    assert hasattr(config, setting_name)
    assert first_scenario["value"] == str(getattr(config, setting_name))
