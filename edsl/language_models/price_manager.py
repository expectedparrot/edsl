from dataclasses import dataclass
from typing import Dict, Literal, Tuple, Union
from collections import namedtuple


@dataclass
class ResponseCost:
    """
    Class for storing the cost and token usage of a language model response.

    If an error occurs when computing the cost, the total_cost will contain a string with the error message.
    All other fields will be None.
    """

    input_tokens: Union[int, None] = None
    output_tokens: Union[int, None] = None
    input_price_per_million_tokens: Union[float, None] = None
    output_price_per_million_tokens: Union[float, None] = None
    total_cost: Union[float, str, None] = None


class PriceRetriever:
    DEFAULT_INPUT_PRICE_PER_MILLION_TOKENS = 1.0
    DEFAULT_OUTPUT_PRICE_PER_MILLION_TOKENS = 1.0

    def __init__(self, price_lookup: Dict[Tuple[str, str], Dict]):
        self._price_lookup = price_lookup

    def get_price(self, inference_service: str, model: str) -> Dict:
        """Get the price information for a specific service and model."""
        key = (inference_service, model)
        return self._price_lookup.get(key) or self._get_fallback_price(
            inference_service
        )

    def _get_fallback_price(self, inference_service: str) -> Dict:
        """
        Get fallback prices for a service.
        - First fallback: The highest input and output prices for that service from the price lookup.
        - Second fallback: $1.00 per million tokens (for both input and output).

        Args:
            inference_service (str): The inference service name

        Returns:
            Dict: Price information
        """
        PriceEntry = namedtuple("PriceEntry", ["tokens_per_usd", "price_info"])

        service_prices = [
            prices
            for (service, _), prices in self._price_lookup.items()
            if service == inference_service
        ]

        default_input_price_info = {
            "one_usd_buys": 1_000_000,
            "service_stated_token_qty": 1_000_000,
            "service_stated_token_price": self.DEFAULT_INPUT_PRICE_PER_MILLION_TOKENS,
        }

        default_output_price_info = {
            "one_usd_buys": 1_000_000,
            "service_stated_token_qty": 1_000_000,
            "service_stated_token_price": self.DEFAULT_OUTPUT_PRICE_PER_MILLION_TOKENS,
        }

        # Find the most expensive price entries (lowest tokens per USD)
        input_price_info = default_input_price_info
        output_price_info = default_output_price_info

        input_prices = [
            PriceEntry(float(p["input"]["one_usd_buys"]), p["input"])
            for p in service_prices
            if "input" in p
        ]
        if input_prices:
            input_price_info = min(
                input_prices, key=lambda price: price.tokens_per_usd
            ).price_info

        output_prices = [
            PriceEntry(float(p["output"]["one_usd_buys"]), p["output"])
            for p in service_prices
            if "output" in p
        ]
        if output_prices:
            output_price_info = min(
                output_prices, key=lambda price: price.tokens_per_usd
            ).price_info

        return {
            "input": input_price_info,
            "output": output_price_info,
        }

    def get_price_per_million_tokens(
        self,
        relevant_prices: Dict,
        token_type: Literal["input", "output"],
    ) -> Dict:
        """
        Get the price per million tokens for a specific service, model, and token type.
        """
        service_price = relevant_prices[token_type]["service_stated_token_price"]
        service_qty = relevant_prices[token_type]["service_stated_token_qty"]

        if service_qty == 1_000_000:
            price_per_million_tokens = service_price
        elif service_qty == 1_000:
            price_per_million_tokens = service_price * 1_000
        else:
            price_per_token = service_price / service_qty
            price_per_million_tokens = round(price_per_token * 1_000_000, 10)
        return price_per_million_tokens


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
        except Exception:
            pass  # Ignore any cleanup errors

    @property
    def price_retriever(self):
        return PriceRetriever(self._price_lookup)

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
        return self.price_retriever.get_price(inference_service, model)

    def get_all_prices(self) -> Dict[Tuple[str, str], Dict]:
        """Get the complete price lookup dictionary."""
        return self._price_lookup.copy()

    def get_price_per_million_tokens(
        self,
        relevant_prices: Dict,
        token_type: Literal["input", "output"],
    ) -> Dict:
        """
        Get the price per million tokens for a specific service, model, and token type.
        """
        return self.price_retriever.get_price_per_million_tokens(
            relevant_prices, token_type
        )

    def _calculate_total_cost(
        self,
        relevant_prices: Dict,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """
        Calculate the total cost for a model usage based on input and output tokens.

        Returns:
            float: Total cost
        """
        # Extract price information
        try:
            inverse_output_price = relevant_prices["output"]["one_usd_buys"]
            inverse_input_price = relevant_prices["input"]["one_usd_buys"]
        except Exception as e:
            if "output" not in relevant_prices:
                raise KeyError(
                    f"Could not fetch prices from {relevant_prices} - {e}; Missing 'output' key."
                )
            if "input" not in relevant_prices:
                raise KeyError(
                    f"Could not fetch prices from {relevant_prices} - {e}; Missing 'input' key."
                )
            raise Exception(f"Could not fetch prices from {relevant_prices} - {e}")

        # Calculate input cost
        if inverse_input_price == "infinity":
            input_cost = 0
        else:
            try:
                input_cost = input_tokens / float(inverse_input_price)
            except Exception as e:
                raise Exception(f"Could not compute input price - {e}")

        # Calculate output cost
        if inverse_output_price == "infinity":
            output_cost = 0
        else:
            try:
                output_cost = output_tokens / float(inverse_output_price)
            except Exception as e:
                raise Exception(f"Could not compute output price - {e}")

        return input_cost + output_cost

    def calculate_cost(
        self,
        inference_service: str,
        model: str,
        usage: Dict[str, Union[str, int]],
        input_token_name: str,
        output_token_name: str,
    ) -> ResponseCost:
        """
        Calculate the cost and token usage for a model response.

        Args:
            inference_service (str): The inference service identifier
            model (str): The model identifier
            usage (Dict[str, Union[str, int]]): Dictionary containing token usage information
            input_token_name (str): Key name for input tokens in the usage dict
            output_token_name (str): Key name for output tokens in the usage dict

        Returns:
            ResponseCost: Object containing token counts and total cost
        """
        try:
            input_tokens = int(usage[input_token_name])
            output_tokens = int(usage[output_token_name])
        except Exception as e:
            return ResponseCost(
                total_cost=f"Could not fetch tokens from model response: {e}",
            )

        try:
            relevant_prices = self.get_price(inference_service, model)
        except Exception as e:
            return ResponseCost(
                total_cost=f"Could not fetch prices from {inference_service} - {model}: {e}",
            )

        try:
            input_price_per_million_tokens = self.get_price_per_million_tokens(
                relevant_prices, "input"
            )
            output_price_per_million_tokens = self.get_price_per_million_tokens(
                relevant_prices, "output"
            )
        except Exception as e:
            return ResponseCost(
                total_cost=f"Could not compute price per million tokens: {e}",
            )

        try:
            total_cost = self._calculate_total_cost(
                relevant_prices, input_tokens, output_tokens
            )
        except Exception as e:
            return ResponseCost(total_cost=f"{e}")

        return ResponseCost(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_price_per_million_tokens=input_price_per_million_tokens,
            output_price_per_million_tokens=output_price_per_million_tokens,
            total_cost=total_cost,
        )

    @property
    def is_initialized(self) -> bool:
        """Check if the PriceManager has been initialized."""
        return self._is_initialized
