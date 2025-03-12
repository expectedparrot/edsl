from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class APIKeyEntry:
    """Data structure for storing API key information with metadata.
    
    APIKeyEntry encapsulates an API key along with metadata about its service, 
    environment variable name, and the source it was retrieved from. This structure
    allows for tracking and debugging the origin of API keys.
    
    Attributes:
        service: The service identifier (e.g., 'openai', 'anthropic')
        name: The environment variable name (e.g., 'OPENAI_API_KEY')
        value: The actual API key value
        source: Where the key was obtained from (e.g., 'env', 'config')
        
    Examples:
        >>> entry = APIKeyEntry.example()
        >>> entry.service
        'openai'
        >>> entry.name
        'OPENAI_API_KEY'
        >>> entry.value
        'sk-abcd1234'
        >>> entry.source
        'env'
        
    Technical Notes:
        - Source values typically include: 'env', 'config', 'coop'
        - Names follow the convention of the service's API documentation
    """

    service: str
    name: str
    value: str
    source: Optional[str] = None

    @classmethod
    def example(cls):
        return APIKeyEntry(
            service="openai", name="OPENAI_API_KEY", value="sk-abcd1234", source="env"
        )


@dataclass
class LimitEntry:
    """Data structure for storing service rate limits with metadata.
    
    LimitEntry encapsulates rate limit information for a service, including
    requests per minute (rpm) and tokens per minute (tpm) limits. It also 
    tracks the source of each limit value to aid in debugging and understanding
    configuration priority.
    
    Attributes:
        service: The service identifier (e.g., 'openai', 'anthropic')
        rpm: Requests per minute limit
        tpm: Tokens per minute limit 
        rpm_source: Where the rpm value was obtained from
        tpm_source: Where the tpm value was obtained from
        
    Examples:
        >>> limit = LimitEntry.example()
        >>> limit.service
        'openai'
        >>> limit.rpm  # Requests per minute
        60
        >>> limit.tpm  # Tokens per minute
        100000
        >>> limit.rpm_source  # Source of the RPM value
        'config'
        >>> limit.tpm_source  # Source of the TPM value
        'env'
        
    Technical Notes:
        - Source values typically include: 'env', 'config', 'coop', 'default'
        - rpm and tpm can come from different sources
        - Default values are applied when specific limits aren't found
    """

    service: str
    rpm: int
    tpm: int
    rpm_source: Optional[str] = None
    tpm_source: Optional[str] = None

    @classmethod
    def example(cls):
        return LimitEntry(
            service="openai", rpm=60, tpm=100000, rpm_source="config", tpm_source="env"
        )


@dataclass
class APIIDEntry:
    """Data structure for storing API ID information with metadata.
    
    APIIDEntry encapsulates an API ID (like AWS Access Key ID) along with
    metadata about its service, environment variable name, and source. Some
    services like AWS Bedrock require both an API key and an API ID.
    
    Attributes:
        service: The service identifier (e.g., 'bedrock' for AWS)
        name: The environment variable name (e.g., 'AWS_ACCESS_KEY_ID')
        value: The actual API ID value
        source: Where the ID was obtained from (e.g., 'env', 'config')
        
    Examples:
        >>> id_entry = APIIDEntry.example()
        >>> id_entry.service
        'bedrock'
        >>> id_entry.name
        'AWS_ACCESS_KEY_ID'
        >>> id_entry.value
        'AKIA1234'
        >>> id_entry.source
        'env'
        
    Technical Notes:
        - Currently primarily used for AWS Bedrock integration
        - Follows the same pattern as APIKeyEntry for consistency
        - Source tracking helps with debugging configuration issues
    """

    service: str
    name: str
    value: str
    source: Optional[str] = None

    @classmethod
    def example(cls):
        return APIIDEntry(
            service="bedrock", name="AWS_ACCESS_KEY_ID", value="AKIA1234", source="env"
        )


@dataclass
class LanguageModelInput:
    """Comprehensive configuration for a language model service.
    
    LanguageModelInput brings together all the configuration needed to interact with
    a language model service, including authentication credentials and rate limits.
    This is the primary data structure used by the language_models module to access
    service credentials in a unified way.
    
    The class combines:
    - API token for authentication
    - Rate limits (rpm, tpm)
    - Optional API ID for services that require it
    - Source tracking for all values
    
    Attributes:
        api_token: The API key/token for authentication
        rpm: Requests per minute limit
        tpm: Tokens per minute limit
        api_id: Optional secondary ID (e.g., AWS Access Key ID)
        token_source: Where the API token was obtained from
        rpm_source: Where the rpm value was obtained from
        tpm_source: Where the tpm value was obtained from
        id_source: Where the api_id was obtained from
        
    Basic usage:
        >>> lm_input = LanguageModelInput(api_token='sk-key123', rpm=60, tpm=100000)
        >>> lm_input.api_token
        'sk-key123'
        
    Example instance:
        >>> lm_input = LanguageModelInput.example()
        >>> lm_input.api_token
        'sk-abcd123'
        >>> lm_input.rpm
        60
        >>> lm_input.tpm
        100000
        >>> lm_input.api_id  # None for most services
        
    Serialization:
        >>> d = lm_input.to_dict()
        >>> isinstance(d, dict)
        True
        >>> LanguageModelInput.from_dict(d).api_token == lm_input.api_token
        True
        
    Technical Notes:
        - Used as values in the KeyLookup dictionary
        - Centralizes all service configuration in one object
        - Supports serialization for storage and transmission
        - Preserves metadata about configuration sources
    """

    api_token: str
    rpm: int
    tpm: int
    api_id: Optional[str] = None
    token_source: Optional[str] = None
    rpm_source: Optional[str] = None
    tpm_source: Optional[str] = None
    id_source: Optional[str] = None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)

    @classmethod
    def example(cls):
        return LanguageModelInput(
            api_token="sk-abcd123", tpm=100000, rpm=60, api_id=None
        )


if __name__ == "__main__":
    import doctest

    doctest.testmod()
