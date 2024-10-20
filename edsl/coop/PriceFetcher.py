import requests
import csv
from io import StringIO


class PriceFetcher:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PriceFetcher, cls).__new__(cls)
            cls._instance._cached_prices = None
        return cls._instance

    def fetch_prices(self):
        if self._cached_prices is not None:
            return self._cached_prices

        import os
        import requests
        from edsl import CONFIG

        try:
            # Fetch the pricing data
            url = f"{CONFIG.EXPECTED_PARROT_URL}/api/v0/prices"
            api_key = os.getenv("EXPECTED_PARROT_API_KEY")
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            else:
                headers["Authorization"] = f"Bearer None"

            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()  # Raise an exception for bad responses

            # Parse the data
            data = response.json()

            price_lookup = {}
            for entry in data:
                service = entry.get("service", None)
                model = entry.get("model", None)
                if service and model:
                    token_type = entry.get("token_type", None)
                    if (service, model) in price_lookup:
                        price_lookup[(service, model)].update({token_type: entry})
                    else:
                        price_lookup[(service, model)] = {token_type: entry}
            self._cached_prices = price_lookup
            return self._cached_prices

        except requests.RequestException as e:
            # print(f"An error occurred: {e}")
            return {}
