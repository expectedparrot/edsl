import pytest
from edsl.jobs.cost_estimation.cost_estimation_constants import (
    TokenAmount,
    TokenRatio,
    _resolve_token_spec,
)


class TestTokenAmount:
    """Fixed token count — value never changes regardless of input size."""

    def test_is_frozen(self):
        t = TokenAmount(50)
        with pytest.raises((AttributeError, TypeError)):
            t.value = 99  # type: ignore[misc]

    def test_equality(self):
        assert TokenAmount(50) == TokenAmount(50)
        assert TokenAmount(50) != TokenAmount(51)


class TestTokenRatio:
    """Token count as a fraction of input — scales with prompt length."""

    def test_is_frozen(self):
        t = TokenRatio(0.5)
        with pytest.raises((AttributeError, TypeError)):
            t.value = 0.9  # type: ignore[misc]

    def test_equality(self):
        assert TokenRatio(0.5) == TokenRatio(0.5)
        assert TokenRatio(0.5) != TokenRatio(1.0)


class TestResolveTokenSpec:
    """Resolves a TokenAmount or TokenRatio to an integer token count given input size."""

    def test_token_amount_ignores_input(self):
        """Fixed spec always returns its value, no matter the input size."""

        assert _resolve_token_spec(TokenAmount(50), 1000) == 50
        assert _resolve_token_spec(TokenAmount(50), 0) == 50
        assert _resolve_token_spec(TokenAmount(50), 999999) == 50

    def test_token_ratio_scales_with_input(self):
        """Ratio spec returns input * ratio, truncated to int."""

        assert _resolve_token_spec(TokenRatio(0.5), 1000) == 500
        assert _resolve_token_spec(TokenRatio(1.0), 1000) == 1000
        assert _resolve_token_spec(TokenRatio(0.25), 200) == 50

    def test_token_ratio_truncates(self):
        """Fractional results are truncated (int()), not rounded."""

        assert _resolve_token_spec(TokenRatio(0.333), 10) == 3

    def test_token_ratio_zero_input(self):
        """Zero input tokens yields zero output regardless of ratio."""

        assert _resolve_token_spec(TokenRatio(1.0), 0) == 0
        assert _resolve_token_spec(TokenRatio(0.5), 0) == 0

    def test_token_amount_zero(self):
        """TokenAmount(0) is valid and resolves to zero even with large input."""

        assert _resolve_token_spec(TokenAmount(0), 1000) == 0
