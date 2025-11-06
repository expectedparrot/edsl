import os
import pytest
from pathlib import Path
from edsl.config import Config
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
    assert "EDSL_DEFAULT_TABLE_RENDERER=datatables" in content


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
    assert "EDSL_DEFAULT_TABLE_RENDERER=rich" in content
    assert "EDSL_VERBOSE_MODE=True" in content

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
    assert "EDSL_DEFAULT_TABLE_RENDERER=datatables" in content
    assert "EDSL_VERBOSE_MODE=False" in content
    # Ensure old value is not present
    lines = content.strip().split('\n')
    renderer_lines = [l for l in lines if l.startswith("EDSL_DEFAULT_TABLE_RENDERER=")]
    assert len(renderer_lines) == 1  # Should only appear once
