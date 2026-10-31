"""Excursion diagnostics must use executed prices and respect no-trade gaps."""

from examples.asset_market.paper_followup_report import excursion_diagnostics


def tape(prices):
    return [{"period": t, "price": price} for t, price in enumerate(prices, 1)]


def test_no_trades_does_not_create_peak_or_crash():
    result = excursion_diagnostics(tape([None, None, None]))
    assert result["peak_price"] is None
    assert result["post_peak_drawdown"] is None
    assert not result["excursion_then_20pct_fall"]


def test_sustained_excursion_followed_by_crash():
    result = excursion_diagnostics(tape([14, 17.5, 20, None, 15]))
    assert result["peak_period"] == 3
    assert result["longest_consecutive_high_periods"] == 2
    assert result["post_peak_drawdown"] == .25
    assert result["excursion_then_20pct_fall"]


def test_missing_period_breaks_duration_and_redemption_is_not_imputed():
    result = excursion_diagnostics(tape([17.5, None, 20, None]))
    assert result["excursion"]
    assert not result["sustained_excursion"]
    assert result["post_peak_drawdown"] is None
    assert not result["excursion_then_20pct_fall"]


def test_small_deviation_is_not_threshold_excursion():
    result = excursion_diagnostics(tape([None, 14.25, 14, None]))
    assert result["peak_price"] == 14.25
    assert not result["excursion"]
