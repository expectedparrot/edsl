import pytest
from unittest.mock import patch
from edsl.key_management.models import (
    APIKeyEntry,
    LimitEntry,
    APIIDEntry,
    LanguageModelInput,
)

from edsl.key_management import KeyLookupBuilder
from edsl.key_management.exceptions import KeyManagementValueError, KeyManagementDuplicateError

from edsl.exceptions.general import MissingAPIKeyError


@pytest.fixture
def mock_env_vars():
    return {
        "OPENAI_API_KEY": "test-openai-key",
        "ANTHROPIC_API_KEY": "test-anthropic-key",
        "EDSL_SERVICE_RPM_OPENAI": "20",
        "EDSL_SERVICE_TPM_OPENAI": "3000000",
        "AWS_ACCESS_KEY_ID": "test-aws-id",
        "AWS_SECRET_ACCESS_KEY": "test-aws-key",
    }


@pytest.fixture
def builder():
    return KeyLookupBuilder(fetch_order=("env",))


def test_initialization():
    """Test KeyLookupBuilder initialization"""
    builder = KeyLookupBuilder()
    assert builder.fetch_order == ("config", "env")
    assert isinstance(builder.limit_data, dict)
    assert isinstance(builder.key_data, dict)
    assert isinstance(builder.id_data, dict)


def test_invalid_fetch_order():
    """Test that invalid fetch order raises KeyManagementValueError"""
    with pytest.raises(KeyManagementValueError):
        KeyLookupBuilder(fetch_order=["env"])  # Should be tuple


@pytest.mark.parametrize(
    "key,expected_type",
    [
        ("EDSL_SERVICE_RPM_OPENAI", "limit"),
        ("OPENAI_API_KEY", "api_key"),
        ("AWS_ACCESS_KEY_ID", "api_id"),
        ("UNKNOWN_KEY", "unknown"),
    ],
)
def test_entry_type_detection(builder, key, expected_type):
    """Test correct detection of entry types"""
    entry_type = builder._entry_type(key)
    assert entry_type == expected_type


@patch.dict("os.environ", {}, clear=True)
def test_os_env_key_value_pairs(mock_env_vars):
    """Test fetching key-value pairs from environment"""
    with patch.dict("os.environ", mock_env_vars):
        builder = KeyLookupBuilder(fetch_order=("env",))
        pairs = builder._os_env_key_value_pairs()

        assert isinstance(pairs, dict)
        assert "OPENAI_API_KEY" in pairs
        assert pairs["OPENAI_API_KEY"] == "test-openai-key"


def test_process_key_value_pairs(builder, mock_env_vars):
    """Test processing of key-value pairs"""
    with patch.dict("os.environ", mock_env_vars, clear=True):
        builder.process_key_value_pairs()

        # Check API keys were processed
        assert "openai" in builder.key_data
        assert isinstance(builder.key_data["openai"][0], APIKeyEntry)

        # Check limits were processed
        assert "openai" in builder.limit_data
        assert isinstance(builder.limit_data["openai"], LimitEntry)

        # Check API IDs were processed
        assert "bedrock" in builder.id_data
        assert isinstance(builder.id_data["bedrock"], APIIDEntry)


def test_get_language_model_input(builder):
    """Test getting LanguageModelInput for a service"""
    # Setup test data
    builder.key_data = {
        "test": [
            APIKeyEntry(
                service="test", name="TEST_KEY", value="test-value", source="env"
            )
        ]
    }
    builder.limit_data = {
        "test": LimitEntry(
            service="test", rpm=10, tpm=2000000, rpm_source="env", tpm_source="env"
        )
    }
    builder.id_data = {
        "test": APIIDEntry(
            service="test", name="TEST_ID", value="test-id", source="env"
        )
    }

    result = builder.get_language_model_input("test")

    assert isinstance(result, LanguageModelInput)
    assert result.api_token == "test-value"
    assert result.rpm == 10
    assert result.tpm == 2000000
    assert result.api_id == "test-id"


def test_missing_api_key():
    """Test handling of missing API key"""
    builder = KeyLookupBuilder()
    with pytest.raises(MissingAPIKeyError):
        builder.get_language_model_input("nonexistent-service")


def test_default_limits():
    """Test that default limits are applied when not specified"""
    builder = KeyLookupBuilder()
    builder.key_data = {
        "test": [
            APIKeyEntry(
                service="test", name="TEST_KEY", value="test-value", source="env"
            )
        ]
    }

    result = builder.get_language_model_input("test")

    assert float(result.rpm) == float(builder.DEFAULT_RPM)
    assert float(result.tpm) == float(builder.DEFAULT_TPM)


def test_build_method():
    """Test the build method creates proper KeyLookup"""
    builder = KeyLookupBuilder()
    # Add test data
    builder.key_data = {
        "test": [
            APIKeyEntry(
                service="test", name="TEST_KEY", value="test-value", source="env"
            )
        ]
    }

    result = builder.build()

    assert "test" in result
    assert isinstance(result["test"], LanguageModelInput)
    assert "test" in result  # Default test service should always be present


def test_update_from_dict(mock_env_vars):
    """Test fetching key-value pairs from environment"""
    with patch.dict("os.environ", mock_env_vars, clear=True):
        builder = KeyLookupBuilder(fetch_order=("env",))

        assert builder.key_data["openai"][-1].value == "test-openai-key"
        assert builder.key_data["openai"][-1].source == "env"

        assert builder.limit_data["openai"].rpm == "20"
        assert builder.limit_data["openai"].rpm_source == "env"

        builder.update_from_dict(
            {
                "OPENAI_API_KEY": ("sk-1234", "custodial_keys"),
                "EDSL_SERVICE_RPM_OPENAI": ("40", "custodial_keys"),
            }
        )

        assert builder.key_data["openai"][-1].value == "sk-1234"
        assert builder.key_data["openai"][-1].source == "custodial_keys"

        assert builder.limit_data["openai"].rpm == "40"
        assert builder.limit_data["openai"].rpm_source == "custodial_keys"


def test_duplicate_id_handling():
    """Test handling of duplicate API IDs"""
    builder = KeyLookupBuilder()
    builder._add_id("AWS_ACCESS_KEY_ID", "test-id-1", "env")

    with pytest.raises(KeyManagementDuplicateError, match="Duplicate ID for service bedrock"):
        builder._add_id("AWS_ACCESS_KEY_ID", "test-id-2", "env")
