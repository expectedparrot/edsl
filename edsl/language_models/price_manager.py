from dataclasses import dataclass
from typing import Dict, Tuple, Union


@dataclass
class ResponseCost:
    """
    Class for storing the cost and token usage of a language model response.

    If an error occurs when computing the cost, the total_cost will contain a string with the error message.
    All other fields will be None.
    """

    input_tokens: int | None = None
    output_tokens: int | None = None
    input_cost: float | None = None
    output_cost: float | None = None
    total_cost: float | str | None = None


class PriceManager:
    _instance = None
    _price_lookup: Dict[Tuple[str, str], Dict] = {}
    _is_initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PriceManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Only initialize once, even if __init__ is called multiple times
        if not self._is_initialized:
            self._is_initialized = True
            self.refresh_prices()

    def refresh_prices(self) -> None:
        """
        Fetch fresh prices from the Coop service and update the internal price lookup.

        """
        from edsl.coop import Coop

        c = Coop()
        try:
            self._price_lookup = c.fetch_prices()
        except Exception as e:
            print(f"Error fetching prices: {str(e)}")

    def get_price(self, inference_service: str, model: str) -> Dict:
        """
        Get the price information for a specific service and model combination.
        If no specific price is found, returns a fallback price.

        Args:
            inference_service (str): The name of the inference service
            model (str): The model identifier

        Returns:
            Dict: Price information (either actual or fallback prices)
        """
        key = (inference_service, model)
        return self._price_lookup.get(key) or self._get_fallback_price(
            inference_service
        )

    def get_all_prices(self) -> Dict[Tuple[str, str], Dict]:
        """
        Get the complete price lookup dictionary.

        Returns:
            Dict[Tuple[str, str], Dict]: The complete price lookup dictionary
        """
        return self._price_lookup.copy()

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
        service_prices = [
            prices
            for (service, _), prices in self._price_lookup.items()
            if service == inference_service
        ]

        input_tokens_per_usd = [
            float(p["input"]["one_usd_buys"]) for p in service_prices if "input" in p
        ]
        if input_tokens_per_usd:
            min_input_tokens = min(input_tokens_per_usd)
        else:
            min_input_tokens = 1_000_000

        output_tokens_per_usd = [
            float(p["output"]["one_usd_buys"]) for p in service_prices if "output" in p
        ]
        if output_tokens_per_usd:
            min_output_tokens = min(output_tokens_per_usd)
        else:
            min_output_tokens = 1_000_000

        return {
            "input": {"one_usd_buys": min_input_tokens},
            "output": {"one_usd_buys": min_output_tokens},
        }

    def _calculate_total_cost(
        self,
        inference_service: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> Tuple[float, float, float]:
        """
        Calculate the total cost for a model usage based on input and output tokens.

        Returns:
            float: Total cost
        """
        relevant_prices = self.get_price(inference_service, model)

        # Extract price information
        try:
            inverse_output_price = relevant_prices["output"]["one_usd_buys"]
            inverse_input_price = relevant_prices["input"]["one_usd_buys"]
            input_price = 1.0 / inverse_input_price
            output_price = 1.0 / inverse_output_price
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

        return input_cost + output_cost, input_cost, output_cost

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
            total_cost, input_cost, output_cost = self._calculate_total_cost(
                inference_service, model, input_tokens, output_tokens
            )
        except Exception as e:
            return ResponseCost(total_cost=f"{e}")

        return ResponseCost(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=total_cost,
        )

    @property
    def is_initialized(self) -> bool:
        """
        Check if the PriceManager has been initialized.

        Returns:
            bool: True if initialized, False otherwise
        """
        return self._is_initialized
