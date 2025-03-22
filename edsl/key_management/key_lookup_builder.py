from typing import Optional, TYPE_CHECKING
import os
from functools import lru_cache
import textwrap

if TYPE_CHECKING:
    from ..coop import Coop

from ..enums import service_to_api_keyname
from ..base import BaseException

class MissingAPIKeyError(BaseException):
    def __init__(self, full_message=None, model_name=None, inference_service=None, silent=False):
        if model_name and inference_service:
            full_message = textwrap.dedent(
                f"""
                An API Key for model `{model_name}` is missing from the .env file.
                This key is associated with the inference service `{inference_service}`.
                Please see https://docs.expectedparrot.com/en/latest/api_keys.html for more information.
                """
            )
        super().__init__(full_message, show_docs=False, silent=silent)

from .key_lookup import KeyLookup
from .models import (
    APIKeyEntry,
    LimitEntry,
    APIIDEntry,
    LanguageModelInput,
)

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


class KeyLookupBuilder:
    """Factory class for building KeyLookup objects by gathering credentials from multiple sources.
    
    >>> from edsl.key_management.exceptions import KeyManagementValueError
    
    KeyLookupBuilder is responsible for discovering, organizing, and consolidating API keys
    and rate limits from various sources. It can pull credentials from:
    
    - Environment variables (env)
    - Configuration files (config) 
    - Remote services (coop)
    
    The builder handles the complexities of:
    - Finding API keys with different naming conventions
    - Merging rate limits from different sources
    - Processing additional credentials like API IDs
    - Prioritizing sources based on a configurable order
    
    Basic usage:
        >>> builder = KeyLookupBuilder()
        >>> keys = builder.build()
        >>> # Now use keys to access service credentials
        >>> keys['test'].api_token
        'test'
    
    Customizing priorities:
        >>> builder = KeyLookupBuilder(fetch_order=("config", "env"))
        >>> builder.fetch_order
        ('config', 'env')
        >>> # 'env' has higher priority than 'config'
    
    Configuration parameters:
        >>> builder = KeyLookupBuilder()
        >>> builder.DEFAULT_RPM  # Default API calls per minute
        100
        >>> builder.DEFAULT_TPM  # Default tokens per minute
        2000000
    
    Validation examples:
        >>> try:
        ...     KeyLookupBuilder(fetch_order=["config", "env"])  # Should be tuple
        ... except KeyManagementValueError as e:
        ...     "fetch_order must be a tuple" in str(e)
        True
        
        >>> builder = KeyLookupBuilder()
        >>> builder.extract_service("EDSL_SERVICE_RPM_OPENAI")
        ('openai', 'rpm')
    
    Technical Notes:
        - The fetch_order parameter controls priority (later sources override earlier ones)
        - Default rate limits are applied when not explicitly provided
        - Maintains tracking of where each value came from for debugging
    """

    # DEFAULT_RPM = 10
    # DEFAULT_TPM = 2000000
    from ..config import CONFIG

    DEFAULT_RPM = int(CONFIG.get("EDSL_SERVICE_RPM_BASELINE"))
    DEFAULT_TPM = int(CONFIG.get("EDSL_SERVICE_TPM_BASELINE"))

    def __init__(
        self,
        fetch_order: Optional[tuple[str]] = None,
        coop: Optional["Coop"] = None,
    ):
        # Import here to avoid circular import issues
        from ..coop import Coop  # Import Coop type for type hinting

        # Fetch order goes from lowest priority to highest priority
        if fetch_order is None:
            self.fetch_order = ("config", "env")
        else:
            self.fetch_order = fetch_order

        if not isinstance(self.fetch_order, tuple):
            from edsl.key_management.exceptions import KeyManagementValueError
            raise KeyManagementValueError("fetch_order must be a tuple")

        if coop is None:
            self.coop = Coop()
        else:
            self.coop = coop

        self.limit_data = {}
        self.key_data = {}
        self.id_data = {}
        self.process_key_value_pairs()

    @property
    def known_services(self):
        """Get the set of known services.

        >>> builder = KeyLookupBuilder()
        >>> isinstance(builder.known_services, set)
        True
        """
        return set(self.key_data.keys()) | set(self.limit_data.keys())

    @lru_cache
    def build(self) -> "KeyLookup":
        """Build a KeyLookup instance with all discovered credentials.
        
        Processes all discovered API keys and rate limits from the configured sources
        and builds a KeyLookup instance containing LanguageModelInput objects for
        each valid service. This method is cached, so subsequent calls will return
        the same instance unless the builder state changes.
        
        Returns:
            KeyLookup: A populated KeyLookup instance with service credentials
            
        Examples:
            >>> builder = KeyLookupBuilder()
            >>> lookup = builder.build()
            >>> isinstance(lookup, KeyLookup)
            True
            >>> lookup['test'].api_token == 'test'  # Test service should always exist
            True
            
        Technical Notes:
            - Skips services with missing API keys
            - Always includes a 'test' service for internal testing
            - Uses lru_cache to avoid rebuilding unless necessary
            - Each valid service gets a complete LanguageModelInput with
              API token, rate limits, and optional API ID
        """
        d = {}
        # Create entries for all discovered services
        for service in self.known_services:
            try:
                d[service] = self.get_language_model_input(service)
            except MissingAPIKeyError:
                pass  # Skip services with missing API keys

        # Always include a test service
        d.update({"test": LanguageModelInput(api_token="test", rpm=10, tpm=2000000)})
        return KeyLookup(d)

    def get_language_model_input(self, service: str) -> LanguageModelInput:
        """Construct a LanguageModelInput object for the specified service.
        
        Creates a complete LanguageModelInput object for the requested service by
        combining the API key, rate limits, and optional API ID from the various 
        data sources. This method assembles the disparate pieces of information
        into a single configuration object.
        
        Args:
            service: Name of the service to retrieve configuration for (e.g., 'openai')
            
        Returns:
            LanguageModelInput: A configuration object with the service's credentials
            
        Raises:
            MissingAPIKeyError: If the required API key for the service is not found
            
        Examples:
            >>> builder = KeyLookupBuilder()
            >>> try:
            ...     builder.get_language_model_input("nonexistent_service")
            ... except MissingAPIKeyError as e:
            ...     str(e)
            "No key found for service 'nonexistent_service'"
            
        Technical Notes:
            - Uses default rate limits if none are specified
            - Preserves information about where each value came from
            - Supports services that require both API key and API ID
        """
        if (key_entries := self.key_data.get(service)) is None:
            raise MissingAPIKeyError(f"No key found for service '{service}'", silent=True)

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
                rpm_source="default",
                tpm_source="default",
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
            rpm_source=limit_entry.rpm_source,
            tpm_source=limit_entry.tpm_source,
            id_source=id_source,
        )

    def __repr__(self):
        return f"DataSource(key_data={self.key_data}, limit_data={self.limit_data}, id_data={self.id_data})"

    def _os_env_key_value_pairs(self):
        return dict(list(os.environ.items()))

    def _coop_key_value_pairs(self):
        return dict(list(self.coop.fetch_rate_limit_config_vars().items()))

    def _config_key_value_pairs(self):
        from ..config import CONFIG

        return dict(list(CONFIG.items()))

    @staticmethod
    def extract_service(key: str) -> str:
        """Extract the service and limit type from the key"""
        limit_type, service_raw = key.replace("EDSL_SERVICE_", "").split("_", 1)
        return service_raw.lower(), limit_type.lower()

    def get_key_value_pairs(self) -> dict:
        """Get key-value pairs from configured sources."""
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

    def _entry_type(self, key: str) -> str:
        """Determine the type of entry from a key.

        >>> builder = KeyLookupBuilder()
        >>> builder._entry_type("EDSL_SERVICE_RPM_OPENAI")
        'limit'
        >>> builder._entry_type("OPENAI_API_KEY")
        'api_key'
        >>> builder._entry_type("AWS_ACCESS_KEY_ID")
        'api_id'
        >>> builder._entry_type("UNKNOWN_KEY")
        'unknown'
        """
        if key.startswith("EDSL_SERVICE_"):
            return "limit"
        elif key in api_keyname_to_service:
            return "api_key"
        elif key in api_id_to_service:
            return "api_id"
        return "unknown"

    def _add_id(self, key: str, value: str, source: str) -> None:
        """Add an API ID to the id_data dictionary.
        
        >>> from edsl.key_management.exceptions import KeyManagementDuplicateError

        >>> builder = KeyLookupBuilder()
        >>> builder._add_id("AWS_ACCESS_KEY_ID", "AKIA1234", "env")
        >>> builder.id_data["bedrock"].value
        'AKIA1234'
        >>> try:
        ...     builder._add_id("AWS_ACCESS_KEY_ID", "AKIA5678", "env")
        ... except KeyManagementDuplicateError as e:
        ...     "Duplicate ID for service bedrock" in str(e)
        True
        """
        service = api_id_to_service[key]
        if service not in self.id_data:
            self.id_data[service] = APIIDEntry(
                service=service, name=key, value=value, source=source
            )
        else:
            from edsl.key_management.exceptions import KeyManagementDuplicateError
            raise KeyManagementDuplicateError(f"Duplicate ID for service {service}")

    def _add_limit(self, key: str, value: str, source: str) -> None:
        """Add a rate limit entry to the limit_data dictionary.

        >>> builder = KeyLookupBuilder()
        >>> builder._add_limit("EDSL_SERVICE_RPM_OPENAI", "60", "config")
        >>> builder.limit_data["openai"].rpm
        '60'
        >>> builder._add_limit("EDSL_SERVICE_TPM_OPENAI", "100000", "config")
        >>> builder.limit_data["openai"].tpm
        '100000'
        """
        service, limit_type = self.extract_service(key)
        if service in self.limit_data:
            setattr(self.limit_data[service], limit_type.lower(), value)
            setattr(self.limit_data[service], f"{limit_type}_source", source)
        else:
            new_limit_entry = LimitEntry(
                service=service, rpm=None, tpm=None, rpm_source=None, tpm_source=None
            )
            setattr(new_limit_entry, limit_type.lower(), value)
            setattr(new_limit_entry, f"{limit_type}_source", source)
            self.limit_data[service] = new_limit_entry

    def _add_api_key(self, key: str, value: str, source: str) -> None:
        """Add an API key entry to the key_data dictionary.

        >>> builder = KeyLookupBuilder()
        >>> builder._add_api_key("OPENAI_API_KEY", "sk-1234", "env")
        >>> 'sk-1234' == builder.key_data["openai"][-1].value
        True
        """
        service = api_keyname_to_service[key]
        new_entry = APIKeyEntry(service=service, name=key, value=value, source=source)
        if service not in self.key_data:
            self.key_data[service] = [new_entry]
        else:
            self.key_data[service].append(new_entry)

    def update_from_dict(self, d: dict) -> None:
        """
        Update data from a dictionary of key-value pairs.
        Each key is a key name, and each value is a tuple of (value, source).

        >>> builder = KeyLookupBuilder()
        >>> builder.update_from_dict({"OPENAI_API_KEY": ("sk-1234", "custodial_keys")})
        >>> 'sk-1234' == builder.key_data["openai"][-1].value
        True
        >>> 'custodial_keys' == builder.key_data["openai"][-1].source
        True
        """
        for key, value_pair in d.items():
            value, source = value_pair
            if self._entry_type(key) == "limit":
                self._add_limit(key, value, source)
            elif self._entry_type(key) == "api_key":
                self._add_api_key(key, value, source)
            elif self._entry_type(key) == "api_id":
                self._add_id(key, value, source)

    def process_key_value_pairs(self) -> None:
        """Process all key-value pairs from the configured sources."""
        self.update_from_dict(self.get_key_value_pairs())


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
