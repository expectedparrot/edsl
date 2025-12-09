import pytest
from edsl.coop import Coop
from edsl.coop.exceptions import CoopValueError
from edsl.scenarios import Scenario


class TestCoopAliasValidation:
    """Test cases for Coop alias validation."""

    def test_valid_alias_letters_only(self):
        """Test that aliases with only letters are valid."""
        coop = Coop()
        # Should not raise an exception
        coop._validate_alias("myalias")
        coop._validate_alias("MyAlias")
        coop._validate_alias("MYALIAS")

    def test_valid_alias_numbers_only(self):
        """Test that aliases with only numbers are valid."""
        coop = Coop()
        # Should not raise an exception
        coop._validate_alias("12345")

    def test_valid_alias_hyphens_only(self):
        """Test that aliases with only hyphens are valid."""
        coop = Coop()
        # Should not raise an exception
        coop._validate_alias("---")

    def test_valid_alias_mixed(self):
        """Test that aliases with letters, numbers, and hyphens are valid."""
        coop = Coop()
        # Should not raise an exception
        coop._validate_alias("my-valid-alias123")
        coop._validate_alias("test-123-alias")
        coop._validate_alias("2024-survey-v2")
        coop._validate_alias("alias-with-many-hyphens-123")

    def test_none_alias_is_valid(self):
        """Test that None alias is valid (no alias provided)."""
        coop = Coop()
        # Should not raise an exception
        coop._validate_alias(None)

    def test_invalid_alias_with_spaces(self):
        """Test that aliases with spaces are invalid."""
        coop = Coop()
        with pytest.raises(CoopValueError) as exc_info:
            coop._validate_alias("invalid alias")

        assert "Invalid alias" in str(exc_info.value)
        assert "invalid alias" in str(exc_info.value)
        assert "only letters, numbers, and hyphens" in str(exc_info.value)

    def test_invalid_alias_with_special_characters(self):
        """Test that aliases with special characters are invalid."""
        coop = Coop()

        invalid_aliases = [
            "alias!",
            "alias@name",
            "alias#tag",
            "alias$price",
            "alias%percent",
            "alias&and",
            "alias*star",
            "alias(paren",
            "alias)",
            "alias[bracket",
            "alias]",
            "alias{brace",
            "alias}",
            "alias|pipe",
            "alias\\backslash",
            "alias/slash",
            "alias:colon",
            "alias;semicolon",
            "alias'quote",
            'alias"doublequote',
            "alias<less",
            "alias>greater",
            "alias?question",
            "alias.period",
            "alias,comma",
            "alias~tilde",
            "alias`backtick",
            "alias+plus",
            "alias=equals",
        ]

        for invalid_alias in invalid_aliases:
            with pytest.raises(CoopValueError) as exc_info:
                coop._validate_alias(invalid_alias)

            assert "Invalid alias" in str(exc_info.value)
            assert invalid_alias in str(exc_info.value)
            assert "only letters, numbers, and hyphens" in str(exc_info.value)

    def test_invalid_alias_with_unicode(self):
        """Test that aliases with unicode characters are invalid."""
        coop = Coop()

        with pytest.raises(CoopValueError):
            coop._validate_alias("aliás")

        with pytest.raises(CoopValueError):
            coop._validate_alias("alias™")

        with pytest.raises(CoopValueError):
            coop._validate_alias("🔥alias")

    def test_push_with_invalid_alias(self):
        """Test that push method validates alias."""
        coop = Coop()
        scenario = Scenario.example()

        # This should raise CoopValueError before making any API call
        with pytest.raises(CoopValueError) as exc_info:
            coop.push(scenario, alias="invalid alias!")

        assert "Invalid alias" in str(exc_info.value)
        assert "only letters, numbers, and hyphens" in str(exc_info.value)

    def test_patch_with_invalid_alias(self):
        """Test that patch method validates alias."""
        coop = Coop()

        # This should raise CoopValueError before making any API call
        with pytest.raises(CoopValueError) as exc_info:
            coop.patch("some-uuid", alias="invalid alias!")

        assert "Invalid alias" in str(exc_info.value)
        assert "only letters, numbers, and hyphens" in str(exc_info.value)
