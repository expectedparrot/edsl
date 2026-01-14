"""Tests for GitMixin info management (git_set_info, git_get_info)."""

import pytest

from edsl.scenarios import Scenario, ScenarioList
from edsl.versioning.mixin import validate_alias
from edsl.versioning.exceptions import InvalidAliasError


class TestGitSetInfo:
    """Tests for git_set_info method."""

    def test_set_alias(self):
        """Test setting alias."""
        sl = ScenarioList([Scenario({"a": 1})])

        sl.git_set_info(alias="my-test")

        info = sl.git_get_info()
        assert info["alias"] == "my-test"

    def test_set_description(self):
        """Test setting description."""
        sl = ScenarioList([Scenario({"a": 1})])

        sl.git_set_info(description="A test scenario list")

        info = sl.git_get_info()
        assert info["description"] == "A test scenario list"

    def test_set_both(self):
        """Test setting alias and description together."""
        sl = ScenarioList([Scenario({"a": 1})])

        sl.git_set_info(alias="test-alias", description="Test description")

        info = sl.git_get_info()
        assert info["alias"] == "test-alias"
        assert info["description"] == "Test description"

    def test_set_info_includes_class_name(self):
        """Test that edsl_class_name is automatically included."""
        sl = ScenarioList([Scenario({"a": 1})])

        sl.git_set_info(alias="test")

        info = sl.git_get_info()
        assert info["edsl_class_name"] == "ScenarioList"

    def test_set_info_creates_staged_change(self):
        """Test that set_info creates a staged change."""
        sl = ScenarioList([Scenario({"a": 1})])

        assert not sl.has_staged

        sl.git_set_info(alias="test")

        assert sl.has_staged

    def test_set_info_returns_self(self):
        """Test that set_info returns self for chaining."""
        sl = ScenarioList([Scenario({"a": 1})])

        result = sl.git_set_info(alias="test")

        assert result is sl


class TestGitGetInfo:
    """Tests for git_get_info method."""

    def test_get_info_empty_initially(self):
        """Test info is empty on new object."""
        sl = ScenarioList([Scenario({"a": 1})])

        info = sl.git_get_info()

        assert info == {}

    def test_get_info_after_set(self):
        """Test info returns set values."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl.git_set_info(alias="test", description="desc")

        info = sl.git_get_info()

        assert info["alias"] == "test"
        assert info["description"] == "desc"

    def test_get_info_preserved_after_commit(self):
        """Test info is preserved after commit."""
        sl = ScenarioList([Scenario({"a": 1})])
        sl.git_set_info(alias="test")
        sl.git_commit("set info")

        info = sl.git_get_info()

        assert info["alias"] == "test"


class TestValidateAlias:
    """Tests for alias validation."""

    def test_valid_simple_alias(self):
        """Test valid simple alias passes."""
        assert validate_alias("my-test") == "my-test"

    def test_valid_with_numbers(self):
        """Test alias with numbers passes."""
        assert validate_alias("test-123") == "test-123"

    def test_valid_owner_name_format(self):
        """Test valid owner/name format passes."""
        assert validate_alias("john/my-test") == "john/my-test"

    def test_invalid_spaces(self):
        """Test spaces are rejected."""
        with pytest.raises(InvalidAliasError, match="spaces"):
            validate_alias("my test")

    def test_invalid_underscores(self):
        """Test underscores are rejected."""
        with pytest.raises(InvalidAliasError, match="underscores"):
            validate_alias("my_test")

    def test_invalid_uppercase(self):
        """Test uppercase is rejected."""
        with pytest.raises(InvalidAliasError, match="lowercase"):
            validate_alias("MyTest")

    def test_invalid_leading_dash(self):
        """Test leading dash is rejected."""
        with pytest.raises(InvalidAliasError):
            validate_alias("-test")

    def test_invalid_trailing_dash(self):
        """Test trailing dash is rejected."""
        with pytest.raises(InvalidAliasError):
            validate_alias("test-")

    def test_invalid_consecutive_dashes(self):
        """Test consecutive dashes are rejected."""
        with pytest.raises(InvalidAliasError, match="consecutive"):
            validate_alias("my--test")

    def test_invalid_empty(self):
        """Test empty alias is rejected."""
        with pytest.raises(InvalidAliasError, match="empty"):
            validate_alias("")

    def test_invalid_multiple_slashes(self):
        """Test multiple slashes are rejected."""
        with pytest.raises(InvalidAliasError, match="one"):
            validate_alias("a/b/c")

    def test_invalid_special_chars(self):
        """Test special characters are rejected."""
        with pytest.raises(InvalidAliasError):
            validate_alias("test@name")

        with pytest.raises(InvalidAliasError):
            validate_alias("test.name")

        with pytest.raises(InvalidAliasError):
            validate_alias("test#name")
