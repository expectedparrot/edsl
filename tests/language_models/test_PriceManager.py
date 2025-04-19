import pytest
from edsl.language_models.price_manager import PriceManager


class MockPriceManager(PriceManager):
    _instance = None  # Separate MockPriceManager from parent class

    def refresh_prices(self) -> None:
        """
        Override refresh_prices to use test data instead of calling Coop.fetch_prices().
        """
        self._price_lookup = {
            ("test", "test-model"): {
                "input": {
                    "service": "test",
                    "model": "test-model",
                    "mode": "regular",
                    "token_type": "input",
                    "service_stated_token_qty": 500_000,
                    "service_stated_token_price": 5,
                    "one_usd_buys": 100_000,
                },
                "output": {
                    "service": "test",
                    "model": "test-model",
                    "mode": "regular",
                    "token_type": "output",
                    "service_stated_token_qty": 200_000,
                    "service_stated_token_price": 5,
                    "one_usd_buys": 40_000,
                },
            },
            ("test", "test-model-beta"): {
                "input": {
                    "service": "test",
                    "model": "test-model-beta",
                    "mode": "regular",
                    "token_type": "input",
                    "service_stated_token_qty": 1_000_000,
                    "service_stated_token_price": 5,
                    "one_usd_buys": 200_000,
                },
                "output": {
                    "service": "test",
                    "model": "test-model",
                    "mode": "regular",
                    "token_type": "output",
                    "service_stated_token_qty": 100_000,
                    "service_stated_token_price": 5,
                    "one_usd_buys": 20_000,
                },
            },
        }


@pytest.fixture
def price_manager():
    return MockPriceManager()


def test_price_retrieval(price_manager):
    price = price_manager.get_price("test", "test-model")
    assert price["input"]["one_usd_buys"] == 100_000
    assert price["output"]["one_usd_buys"] == 40_000


def test_fallback_price_known_service(price_manager):
    # If service is in the price lookup, but model is not, the highest price per service should be used
    price = price_manager.get_price("test", "unknown-model")
    assert price["input"]["one_usd_buys"] == 100_000
    assert price["output"]["one_usd_buys"] == 20_000


def test_fallback_price_unknown_service(price_manager):
    # If service is not in the price lookup, the hardcoded fallback should be used
    price = price_manager.get_price("unknown-service", "random-model")
    assert price["input"]["one_usd_buys"] == 1_000_000
    assert price["output"]["one_usd_buys"] == 1_000_000


def test_cost_calculation(price_manager):
    cost = price_manager.calculate_cost(
        "test",
        "test-model",
        {"input_tokens": 1000, "output_tokens": 1000},
        "input_tokens",
        "output_tokens",
    )
    assert cost.input_tokens == 1000
    assert cost.output_tokens == 1000
    assert round(cost.total_cost, 3) == 0.035


def test_cost_calculation_known_service(price_manager):
    cost = price_manager.calculate_cost(
        "test",
        "unknown-model",
        {"input_tokens": 1000, "output_tokens": 1000},
        "input_tokens",
        "output_tokens",
    )
    assert cost.input_tokens == 1000
    assert cost.output_tokens == 1000
    assert round(cost.total_cost, 3) == 0.060


def test_cost_calculation_unknown_service(price_manager):
    cost = price_manager.calculate_cost(
        "unknown-service",
        "random-model",
        {"input_tokens": 1000, "output_tokens": 1000},
        "input_tokens",
        "output_tokens",
    )
    assert cost.input_tokens == 1000
    assert cost.output_tokens == 1000
    assert round(cost.total_cost, 3) == 0.002
