"""
Module for retrieving and caching language model pricing information.

This module provides functionality to fetch current pricing information for various
language models from the Expected Parrot API. It uses a singleton pattern to ensure
that price information is only fetched once and then cached for efficiency.

Pricing data is also persisted to disk so that subsequent sessions can avoid a
network round-trip when the cached data is still fresh (controlled by
``EDSL_PRICE_CACHE_TTL_SECONDS``, default 24 h).
"""

import datetime
import json
import requests
import os
from typing import Dict, Tuple, Any

import platformdirs

# Disk-cache TTL in seconds (default 24 h). Override via env var.
_PRICE_CACHE_TTL_SECONDS = int(
    os.environ.get("EDSL_PRICE_CACHE_TTL_SECONDS", "86400")
)


def _price_cache_path() -> str:
    """Return the path to the on-disk price cache file."""
    cache_dir = platformdirs.user_cache_dir("edsl")
    return os.path.join(cache_dir, "price_cache.json")


class PriceFetcher:
    """
    A singleton class for fetching and caching language model pricing information.

    Attributes:
        _instance (PriceFetcher): The singleton instance of the class
        _cached_prices (Dict[Tuple[str, str], Dict]): Cached pricing information
            mapping (service, model) tuples to their pricing details
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PriceFetcher, cls).__new__(cls)
            cls._instance._cached_prices = None
        return cls._instance

    # ------------------------------------------------------------------
    # Disk-cache helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _read_disk_cache() -> Dict[Tuple[str, str], Dict[str, Dict[str, Any]]]:
        """Read price data from the on-disk cache if it exists and is fresh."""
        path = _price_cache_path()
        if not os.path.exists(path):
            raise FileNotFoundError(path)

        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        # Check TTL
        created_at_str = raw.get("created_at")
        if created_at_str:
            created_at = datetime.datetime.fromisoformat(created_at_str)
            age = (datetime.datetime.now() - created_at).total_seconds()
            if age > _PRICE_CACHE_TTL_SECONDS:
                raise ValueError(f"Price cache is stale ({age:.0f}s old)")

        # Reconstruct the lookup with tuple keys
        price_lookup: Dict[Tuple[str, str], Dict] = {}
        for key_str, value in raw.get("data", {}).items():
            service, model = key_str.split("|", 1)
            price_lookup[(service, model)] = value

        return price_lookup

    @staticmethod
    def _write_disk_cache(
        price_lookup: Dict[Tuple[str, str], Dict[str, Dict[str, Any]]]
    ) -> None:
        """Persist price data to disk."""
        path = _price_cache_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)

        # Serialize tuple keys as "service|model" strings for JSON
        serializable: Dict[str, Any] = {}
        for (service, model), value in price_lookup.items():
            serializable[f"{service}|{model}"] = value

        payload = {
            "created_at": datetime.datetime.now().isoformat(),
            "data": serializable,
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)

    # ------------------------------------------------------------------
    # Main fetch
    # ------------------------------------------------------------------
    def fetch_prices(self) -> Dict[Tuple[str, str], Dict[str, Dict[str, Any]]]:
        """
        Fetch current pricing information for language models.

        Checks (in order): in-memory cache, disk cache, then network.
        """
        # 1. In-memory cache
        if self._cached_prices is not None:
            return self._cached_prices

        # 2. Disk cache
        try:
            self._cached_prices = self._read_disk_cache()
            return self._cached_prices
        except Exception:
            pass  # stale, missing, or corrupt — fall through to network

        # 3. Network fetch
        from ..config import CONFIG

        try:
            url = f"{CONFIG.EXPECTED_PARROT_URL}/api/v0/prices"
            api_key = os.getenv("EXPECTED_PARROT_API_KEY")
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            else:
                headers["Authorization"] = "Bearer None"

            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()

            data = response.json()

            price_lookup: Dict[Tuple[str, str], Dict] = {}
            for entry in data:
                service = entry.get("service", None)
                model = entry.get("model", None)
                if service and model:
                    token_type = entry.get("token_type", None)
                    if (service, model) in price_lookup:
                        price_lookup[(service, model)].update({token_type: entry})
                    else:
                        price_lookup[(service, model)] = {token_type: entry}

            # Persist to disk for future sessions
            try:
                self._write_disk_cache(price_lookup)
            except Exception:
                pass  # non-fatal

            self._cached_prices = price_lookup
            return self._cached_prices

        except requests.RequestException:
            return {}
