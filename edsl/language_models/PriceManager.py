from typing import Dict, Tuple, Optional, Union


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

    def get_price(self, inference_service: str, model: str) -> Optional[Dict]:
        """
        Get the price information for a specific service and model combination.

        Args:
            inference_service (str): The name of the inference service
            model (str): The model identifier

        Returns:
            Optional[Dict]: Price information if found, None otherwise
        """
        key = (inference_service, model)
        return self._price_lookup.get(key)

    def get_all_prices(self) -> Dict[Tuple[str, str], Dict]:
        """
        Get the complete price lookup dictionary.

        Returns:
            Dict[Tuple[str, str], Dict]: The complete price lookup dictionary
        """
        return self._price_lookup.copy()

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
        if relevant_prices is None:
            return f"Could not find price for model {model} in the price lookup."

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
