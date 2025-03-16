from collections import UserDict
from dataclasses import asdict

from ..enums import service_to_api_keyname

from .models import LanguageModelInput

class KeyLookup(UserDict):
    """Dictionary-like container for storing and accessing language model service credentials.
    
    KeyLookup provides a centralized store for API keys, rate limits, and other configuration
    needed to authenticate with various language model services. It inherits from UserDict,
    using service names as keys (e.g., 'openai', 'anthropic') and LanguageModelInput objects
    as values.
    
    The class provides convenient methods for:
    - Serializing to and from dictionaries for storage
    - Generating .env files for environment configuration
    - Creating example instances for testing
    
    Typical usage:
        >>> from .models import LanguageModelInput  # Import for doctest
        >>> lookup = KeyLookup()
        >>> lookup['openai'] = LanguageModelInput(api_token='sk-key123', rpm=60, tpm=100000)
        >>> openai_config = lookup['openai']
        >>> openai_config.api_token
        'sk-key123'
    
    Serialization example:
        >>> lookup = KeyLookup()
        >>> lm_input = LanguageModelInput.example()
        >>> lookup['test'] = lm_input
        >>> lookup.to_dict()['test']['api_token']
        'sk-abcd123'
        >>> restored = KeyLookup.from_dict(lookup.to_dict())
        >>> restored['test'].api_token
        'sk-abcd123'
        
    Technical Notes:
        - Uses LanguageModelInput dataclass for structured storage
        - Preserves source information for debugging and transparency
        - Supports conversion to environment variable format
    """

    def to_dict(self):
        """Convert the KeyLookup to a serializable dictionary.
        
        Converts each LanguageModelInput value to a dictionary using dataclasses.asdict,
        producing a nested dictionary structure suitable for JSON serialization.
        
        Returns:
            dict: A dictionary with service names as keys and serialized LanguageModelInput
                 objects as values
        
        Examples:
            >>> kl = KeyLookup.example()
            >>> serialized = kl.to_dict()
            >>> 'test' in serialized
            True
            >>> 'api_token' in serialized['test']
            True
            
            >>> kl2 = KeyLookup.from_dict(kl.to_dict())
            >>> kl2 == kl  # Equal content
            True
            >>> kl2 is kl  # But different objects
            False
        """
        return {k: asdict(v) for k, v in self.data.items()}

    @classmethod
    def from_dict(cls, d):
        """Create a KeyLookup instance from a dictionary representation.
        
        Converts a dictionary produced by to_dict() back into a KeyLookup instance,
        reconstructing LanguageModelInput objects from their serialized form.
        
        Args:
            d (dict): Dictionary with service names as keys and serialized 
                     LanguageModelInput objects as values
                     
        Returns:
            KeyLookup: A new KeyLookup instance populated with the deserialized data
            
        Examples:
            >>> data = {
            ...     'openai': {
            ...         'api_token': 'sk-test', 
            ...         'rpm': 60, 
            ...         'tpm': 100000
            ...     }
            ... }
            >>> lookup = KeyLookup.from_dict(data)
            >>> lookup['openai'].api_token
            'sk-test'
        """
        return cls({k: LanguageModelInput(**v) for k, v in d.items()})

    @classmethod
    def example(cls):
        """Create an example KeyLookup instance for testing and documentation.
        
        Returns:
            KeyLookup: A new KeyLookup instance with example services and credentials
            
        Examples:
            >>> example = KeyLookup.example()
            >>> 'test' in example
            True
            >>> 'openai' in example
            True
        """
        return cls(
            {
                "test": LanguageModelInput.example(),
                "openai": LanguageModelInput.example(),
            }
        )

    def to_dot_env(self):
        """Generate environment variable definitions for a .env file.
        
        Creates a string with environment variable definitions suitable for a .env file,
        containing service API keys and rate limits in the standard format expected
        by the key_management system.
        
        Returns:
            str: A string with newline-separated environment variable definitions
            
        Examples:
            >>> lookup = KeyLookup({
            ...     'test': LanguageModelInput(api_token='test', rpm=10, tpm=20000),
            ...     'openai': LanguageModelInput(api_token='sk-1234', rpm=60, tpm=100000)
            ... })
            >>> env_str = lookup.to_dot_env()
            >>> 'EDSL_SERVICE_RPM_OPENAI=60' in env_str
            True
            >>> 'OPENAI_API_KEY=sk-1234' in env_str
            True
            
        Technical Notes:
            - Skips the 'test' service which is for internal testing
            - Handles special cases for service names that don't match their API key names
            - Includes API IDs for services that require them (e.g., AWS Bedrock)
        """
        lines = []
        for service, lm_input in self.items():
            if service != "test":
                lines.append(f"EDSL_SERVICE_RPM_{service.upper()}={lm_input.rpm}")
                lines.append(f"EDSL_SERVICE_TPM_{service.upper()}={lm_input.tpm}")
                key_name = service_to_api_keyname.get(service, service)
                lines.append(f"{key_name.upper()}={lm_input.api_token}")
                if lm_input.api_id is not None:
                    lines.append(f"{service.upper()}_API_ID={lm_input.api_id}")
        return "\n".join([f"{line}" for line in lines])


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
