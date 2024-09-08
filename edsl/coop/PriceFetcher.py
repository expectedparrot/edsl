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

        import requests
        import csv
        from io import StringIO

        sheet_id = "1SAO3Bhntefl0XQHJv27rMxpvu6uzKDWNXFHRa7jrUDs"

        # Construct the URL to fetch the CSV
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"

        try:
            # Fetch the CSV data
            response = requests.get(url)
            response.raise_for_status()  # Raise an exception for bad responses

            # Parse the CSV data
            csv_data = StringIO(response.text)
            reader = csv.reader(csv_data)

            # Convert to list of dictionaries
            headers = next(reader)
            data = [dict(zip(headers, row)) for row in reader]

            # self._cached_prices = data
            # return data
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
            print(f"An error occurred: {e}")
            return None
