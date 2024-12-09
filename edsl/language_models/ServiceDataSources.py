from typing import Optional, List
from collections import UserDict
import os
from datetime import datetime, timedelta
from functools import lru_cache
from dataclasses import dataclass, asdict

from edsl.enums import service_to_api_keyname
from edsl.exceptions import MissingAPIKeyError


@dataclass
class APIKeyEntry:
    service: str
    name: str
    value: str
    source: Optional[str] = None


@dataclass
class LimitEntry:
    service: str
    rpm: int
    tpm: int
    source: Optional[str] = None


@dataclass
class APIIDEntry:
    service: str
    name: str
    value: str
    source: Optional[str] = None


@dataclass
class LanguageModelInput:
    api_token: str
    rpm: int
    tpm: int
    api_id: Optional[str] = None

    token_source: Optional[str] = None
    limit_source: Optional[str] = None
    id_source: Optional[str] = None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


service_to_api_keyname["bedrock"] = "AWS_SECRET_ACCESS_KEY"
service_to_api_id = {"bedrock": "AWS_ACCESS_KEY_ID"}

api_keyname_to_service = {}

for service, key in service_to_api_keyname.items():
    if isinstance(key, list):
        for k in key:
            api_keyname_to_service[k] = service
    else:
        api_keyname_to_service[key] = service

api_id_to_service = {"AWS_ACCESS_KEY_ID": "bedrock"}


class KeyLookupCollection(UserDict):
    """This is a singleton class that stores key-lookup objects."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, *args, **kwargs):
        if not hasattr(self, "_initialized"):
            self.data = {}
            self._initialized = True
            super().__init__(*args, **kwargs)

    def add_key_lookup(self, fetch_order=None):
        if fetch_order is None:
            fetch_order = ("config", "env")
        if fetch_order not in self.data:
            self.data[fetch_order] = KeyLookupBuilder(fetch_order=fetch_order).build()


class KeyLookup(UserDict):

    def to_dict(self):
        return {k: asdict(v) for k, v in self.data.items()}

    @classmethod
    def from_dict(cls, d):
        return cls({k: LanguageModelInput(**v) for k, v in d.items()})


class KeyLookupBuilder:
    """
    Builds KeyLookup options.
    """

    DEFAULT_RPM = 10
    DEFAULT_TPM = 2000000

    def __init__(self, fetch_order: Optional[tuple[str]] = None):
        """The default is to reach from the config file, then the .env, which could over-write config values."""
        if fetch_order is None:
            self.fetch_order = ("config", "env")
        else:
            self.fetch_order = fetch_order

        if not isinstance(self.fetch_order, tuple):
            raise ValueError("fetch_order must be a tuple")

        # These dictionaries are where we still information about keys, limits and identifiers.
        self.limit_data = {}
        self.key_data = {}
        self.id_data = {}
        self.process_key_value_pairs()  # fetch the data from the source & populate

    @property
    def known_services(self):
        return set(self.key_data.keys()) | set(self.limit_data.keys())

    @lru_cache
    def build(self) -> "KeyLookup":
        d = {}
        for service in self.known_services:
            try:
                d[service] = self.get_language_model_input(service)
            except MissingAPIKeyError:
                pass

        d.update({"test": LanguageModelInput(api_token="test", rpm=10, tpm=2000000)})
        return KeyLookup(d)

    def get_language_model_input(self, service: str) -> LanguageModelInput:
        """Get the language model input for a given service."""
        if (key_entries := self.key_data.get(service)) is None:
            raise MissingAPIKeyError(f"No key found for service '{service}'")

        if len(key_entries) == 1:
            api_key_entry = key_entries[0]

        id_entry = self.id_data.get(service)
        id_source = id_entry.source if id_entry is not None else None
        api_id = id_entry.value if id_entry is not None else None

        if (limit_entry := self.limit_data.get(service)) is None:
            limit_entry = LimitEntry(
                service=service,
                rpm=self.DEFAULT_RPM,
                tpm=self.DEFAULT_TPM,
                source="default",
            )

        if limit_entry.rpm is None:
            limit_entry.rpm = self.DEFAULT_RPM
        if limit_entry.tpm is None:
            limit_entry.tpm = self.DEFAULT_TPM

        return LanguageModelInput(
            api_token=api_key_entry.value,
            rpm=int(limit_entry.rpm),
            tpm=int(limit_entry.tpm),
            api_id=api_id,
            token_source=api_key_entry.source,
            limit_source=limit_entry.source,
            id_source=id_source,
        )

    def __repr__(self):
        return f"DataSource(key_data={self.key_data}, limit_data={self.limit_data}, id_data={self.id_data})"

    def _os_env_key_value_pairs(self):
        return dict(list(os.environ.items()))

    def _coop_key_value_pairs(self):
        from edsl.coop import Coop

        c = Coop()

        return dict(list(c.fetch_rate_limit_config_vars().items()))

    def _config_key_value_pairs(self):
        from edsl import CONFIG

        return dict(list(CONFIG.items()))

    @staticmethod
    def extract_service(key: str) -> str:
        """Extract the service and limit type from the key"""
        limit_type, service_raw = key.replace("EDSL_SERVICE_", "").split("_")
        return service_raw.lower(), limit_type.lower()

    def get_key_value_pairs(self) -> dict:
        fetching_functions = {
            "env": self._os_env_key_value_pairs,
            "coop": self._coop_key_value_pairs,
            "config": self._config_key_value_pairs,
        }
        d = {}
        for source in self.fetch_order:
            f = fetching_functions[source]
            new_data = f()
            for k, v in new_data.items():
                d[k] = (v, source)
        return d

    def _entry_type(self, key, value) -> str:
        if key.startswith("EDSL_SERVICE_"):
            return "limit"
        elif key in api_keyname_to_service:
            return "api_key"
        elif key in api_id_to_service:
            return "api_id"
        return "unknown"

    def _add_id(self, key: str, value: str, source: str) -> None:
        """Add an api key to the key_data dictionary"""
        service = api_id_to_service[key]
        if service not in self.id_data:
            self.id_data[service] = APIIDEntry(
                service=service, name=key, value=value, source=source
            )
        else:
            raise ValueError(f"Duplicate ID for service {service}")

    def _add_limit(self, key: str, value: str, source: str) -> None:
        """Add a limit to the limit_data dictionary"""
        service, limit_type = self.extract_service(key)
        if service in self.limit_data:
            setattr(self.limit_data[service], limit_type.lower(), value)
        else:
            new_limit_entry = LimitEntry(
                service=service, rpm=None, tpm=None, source=source
            )
            setattr(new_limit_entry, limit_type.lower(), value)
            self.limit_data[service] = new_limit_entry

    def _add_api_key(self, key: str, value: str, source: str) -> None:
        """Add an api key to the key_data dictionary"""
        service = api_keyname_to_service[key]
        new_entry = APIKeyEntry(service=service, name=key, value=value, source=source)
        if service not in self.key_data:
            self.key_data[service] = [new_entry]
        else:
            self.key_data[service].append(new_entry)

    def process_key_value_pairs(self) -> tuple[dict, dict]:
        """Fetch the data from the source"""
        # print("fetching key value pairs")
        for key, value_pair in self.get_key_value_pairs().items():
            value, source = value_pair
            if (entry_type := self._entry_type(key, value)) == "limit":
                self._add_limit(key, value, source)
            elif entry_type == "api_key":
                self._add_api_key(key, value, source)
            elif entry_type == "api_id":
                self._add_id(key, value, source)


if __name__ == "__main__":
    import doctest

    doctest.testmod()

    combined = KeyLookupBuilder()
    d = combined.service_lookup()

    print(d["openai"])
