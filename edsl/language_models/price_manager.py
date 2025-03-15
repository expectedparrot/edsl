from typing import Dict, Tuple, Union


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

    def calculate_cost(
        self,
        inference_service: str,
        model: str,
        usage: Dict[str, Union[str, int]],
        input_token_name: str,
        output_token_name: str,
    ) -> Union[float, str]:
        """
        Calculate the total cost for a model usage based on input and output tokens.

        Args:
            inference_service (str): The inference service identifier
            model (str): The model identifier
            usage (Dict[str, Union[str, int]]): Dictionary containing token usage information
            input_token_name (str): Key name for input tokens in the usage dict
            output_token_name (str): Key name for output tokens in the usage dict

        Returns:
            Union[float, str]: Total cost if calculation successful, error message string if not
        """
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
        if inverse_input_price == "infinity":
            input_cost = 0
        else:
            try:
                input_cost = input_tokens / float(inverse_input_price)
            except Exception as e:
                return f"Could not compute input price - {e}."

        # Calculate output cost
        if inverse_output_price == "infinity":
            output_cost = 0
        else:
            try:
                output_cost = output_tokens / float(inverse_output_price)
            except Exception as e:
                return f"Could not compute output price - {e}"

        return input_cost + output_cost

    @property
    def is_initialized(self) -> bool:
        """
        Check if the PriceManager has been initialized.

        Returns:
            bool: True if initialized, False otherwise
        """
        return self._is_initialized
