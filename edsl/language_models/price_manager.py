from typing import Dict, Tuple, Union


class PriceManager:
    _instance = None
    _price_lookup: Dict[Tuple[str, str], Dict] = {}
    _is_initialized = False

    def __new__(cls):
        if cls._instance is None:
            instance = super(PriceManager, cls).__new__(cls)
            instance._price_lookup = {}  # Instance-specific attribute
            instance._is_initialized = False
            cls._instance = instance  # Store the instance directly
            return instance
        return cls._instance

    def __init__(self):
        """Initialize the singleton instance only once."""
        if not self._is_initialized:
            self._is_initialized = True
            print("Price manager initialized.")
            self.refresh_prices()

    @classmethod
    def get_instance(cls):
        """Get the singleton instance, creating it if necessary."""
        if cls._instance is None:
            cls()  # Create the instance if it doesn't exist
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset the singleton instance to clean up resources."""
        cls._instance = None
        cls._is_initialized = False
        cls._price_lookup = {}

    def __del__(self):
        """Ensure proper cleanup when the instance is garbage collected."""
        try:
            self._price_lookup = {}  # Clean up resources
        except:
            pass  # Ignore any cleanup errors

    def refresh_prices(self) -> None:
        """Fetch fresh prices and update the internal price lookup."""
        from edsl.coop import Coop

        c = Coop()
        try:
            self._price_lookup = c.fetch_prices()
        except Exception as e:
            print(f"Error fetching prices: {str(e)}")

    def get_price(self, inference_service: str, model: str) -> Dict:
        """Get the price information for a specific service and model."""
        key = (inference_service, model)
        return self._price_lookup.get(key) or self._get_fallback_price(
            inference_service
        )

    def get_all_prices(self) -> Dict[Tuple[str, str], Dict]:
        """Get the complete price lookup dictionary."""
        return self._price_lookup.copy()

    def _get_fallback_price(self, inference_service: str) -> Dict:
        """Get fallback prices for a service."""
        service_prices = [
            prices
            for (service, _), prices in self._price_lookup.items()
            if service == inference_service
        ]

        input_tokens_per_usd = [
            float(p["input"]["one_usd_buys"]) for p in service_prices if "input" in p
        ]
        min_input_tokens = min(input_tokens_per_usd, default=1_000_000)

        output_tokens_per_usd = [
            float(p["output"]["one_usd_buys"]) for p in service_prices if "output" in p
        ]
        min_output_tokens = min(output_tokens_per_usd, default=1_000_000)

        return {
            "input": {"one_usd_buys": min_input_tokens},
            "output": {"one_usd_buys": min_output_tokens},
        }

    def calculate_cost(
        self,
        inference_service: str,
        model: str,
        usage: Dict[str, Union[str, int]],
        input_token_name: str,
        output_token_name: str,
    ) -> Union[float, str]:
        """Calculate the total cost for a model usage."""
        relevant_prices = self.get_price(inference_service, model)

        # Extract token counts
        try:
            input_tokens = int(usage[input_token_name])
            output_tokens = int(usage[output_token_name])
        except Exception as e:
            return f"Could not fetch tokens from model response: {e}"

        # Extract price information
        try:
            inverse_output_price = relevant_prices["output"]["one_usd_buys"]
            inverse_input_price = relevant_prices["input"]["one_usd_buys"]
        except Exception as e:
            if "output" not in relevant_prices:
                return f"Could not fetch prices from {relevant_prices} - {e}; Missing 'output' key."
            if "input" not in relevant_prices:
                return f"Could not fetch prices from {relevant_prices} - {e}; Missing 'input' key."
            return f"Could not fetch prices from {relevant_prices} - {e}"

        # Calculate input cost
        input_cost = (
            0
            if inverse_input_price == "infinity"
            else input_tokens / float(inverse_input_price)
        )

        # Calculate output cost
        output_cost = (
            0
            if inverse_output_price == "infinity"
            else output_tokens / float(inverse_output_price)
        )

        return input_cost + output_cost

    @property
    def is_initialized(self) -> bool:
        """Check if the PriceManager has been initialized."""
        return self._is_initialized
