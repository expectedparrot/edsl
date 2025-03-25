"""
Module for retrieving and caching language model pricing information.

This module provides functionality to fetch current pricing information for various
language models from the Expected Parrot API. It uses a singleton pattern to ensure
that price information is only fetched once and then cached for efficiency.
"""

import requests
import os
from typing import Dict, Tuple, Any


class PriceFetcher:
    """
    A singleton class for fetching and caching language model pricing information.
    
    This class retrieves the current pricing for language models from the Expected
    Parrot API and caches it to avoid unnecessary network requests. It implements
    a singleton pattern to ensure that only one instance exists throughout the
    application.
    
    Attributes:
        _instance (PriceFetcher): The singleton instance of the class
        _cached_prices (Dict[Tuple[str, str], Dict]): Cached pricing information
            mapping (service, model) tuples to their pricing details
    """
    _instance = None
    
    def __new__(cls):
        """
        Create or return the singleton instance of PriceFetcher.
        
        This method ensures that only one instance of PriceFetcher exists.
        When called multiple times, it returns the same instance.
        
        Returns:
            PriceFetcher: The singleton instance
        """
        if cls._instance is None:
            cls._instance = super(PriceFetcher, cls).__new__(cls)
            cls._instance._cached_prices = None
        return cls._instance

    def fetch_prices(self) -> Dict[Tuple[str, str], Dict[str, Dict[str, Any]]]:
        """
        Fetch current pricing information for language models.
        
        This method retrieves the latest pricing information from the Expected Parrot API
        for all supported language models. It caches the results to avoid redundant API calls.
        
        Returns:
            Dict[Tuple[str, str], Dict[str, Dict[str, Any]]]: A dictionary mapping 
            (service, model) tuples to their pricing information for different token types.
            Structure example:
            {
                ('openai', 'gpt-4'): {
                    'input': {
                        'service': 'openai',
                        'model': 'gpt-4',
                        'token_type': 'input',
                        'usd_per_1M_tokens': 30.0,
                        ...
                    },
                    'output': {
                        'service': 'openai',
                        'model': 'gpt-4',
                        'token_type': 'output',
                        'usd_per_1M_tokens': 60.0,
                        ...
                    }
                },
                ...
            }
            
        Notes:
            - If the request fails, returns an empty dictionary
            - Uses caching to avoid redundant API calls
            - Pricing data includes both input and output token costs
            - This method is automatically called by the Coop.fetch_prices() method
        """
        # Return cached prices if available
        if self._cached_prices is not None:
            return self._cached_prices

        from ..config import CONFIG

        try:
            # Fetch the pricing data
            url = f"{CONFIG.EXPECTED_PARROT_URL}/api/v0/prices"
            api_key = os.getenv("EXPECTED_PARROT_API_KEY")
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            else:
                headers["Authorization"] = "Bearer None"

            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()  # Raise an exception for bad responses

            # Parse the data
            data = response.json()

            # Organize pricing data by (service, model) and token type
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
                        
            # Cache and return the results
            self._cached_prices = price_lookup
            return self._cached_prices

        except requests.RequestException:
            # Silently handle errors and return empty dict
            # print(f"An error occurred: {e}")
            return {}