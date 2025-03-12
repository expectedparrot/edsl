from typing import Any, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .language_model import LanguageModel

class ComputeCost:
    """Computes the dollar cost of a raw response.
    
    # TODO: Add doctests
    >>> True
    True
    
    """
    def __init__(self, language_model: "LanguageModel"):
        self.language_model = language_model
        self._price_lookup = None

    @property
    def price_lookup(self):
        if self._price_lookup is None:
            from ..coop import Coop

            c = Coop()
            self._price_lookup = c.fetch_prices()
        return self._price_lookup

    def cost(self, raw_response: dict[str, Any]) -> Union[float, str]:
        """Return the dollar cost of a raw response."""

        usage = self.get_usage_dict(raw_response)
        from ..coop import Coop

        c = Coop()
        price_lookup = c.fetch_prices()
        key = (self._inference_service_, self.model)
        if key not in price_lookup:
            return f"Could not find price for model {self.model} in the price lookup."

        relevant_prices = price_lookup[key]
        try:
            input_tokens = int(usage[self.input_token_name])
            output_tokens = int(usage[self.output_token_name])
        except Exception as e:
            return f"Could not fetch tokens from model response: {e}"

        try:
            inverse_output_price = relevant_prices["output"]["one_usd_buys"]
            inverse_input_price = relevant_prices["input"]["one_usd_buys"]
        except Exception as e:
            if "output" not in relevant_prices:
                return f"Could not fetch prices from {relevant_prices} - {e}; Missing 'output' key."
            if "input" not in relevant_prices:
                return f"Could not fetch prices from {relevant_prices} - {e}; Missing 'input' key."
            return f"Could not fetch prices from {relevant_prices} - {e}"

        if inverse_input_price == "infinity":
            input_cost = 0
        else:
            try:
                input_cost = input_tokens / float(inverse_input_price)
            except Exception as e:
                return f"Could not compute input price - {e}."

        if inverse_output_price == "infinity":
            output_cost = 0
        else:
            try:
                output_cost = output_tokens / float(inverse_output_price)
            except Exception as e:
                return f"Could not compute output price - {e}"

        return input_cost + output_cost



if __name__ == "__main__":
    import doctest
    doctest.testmod()
