"""Key management system for API tokens and rate limits.

The key_management module provides a flexible system for managing API keys, credentials, and 
rate limits for various language model services. It handles discovery, storage, and retrieval
of API keys from multiple sources including environment variables, configuration files, and
remote services.

Key components:
- KeyLookup: Dictionary-like container for service credentials and rate limits
- KeyLookupBuilder: Factory that builds KeyLookup objects by gathering credentials
- KeyLookupCollection: Singleton collection to avoid rebuilding KeyLookup objects
- Data models: Structured representations of API keys, rate limits, and credentials

This module supports multiple credential sources with configurable priority, allowing
EDSL to use different API keys in different environments while maintaining a consistent
interface for the rest of the system.

Typical usage:
```python
from edsl.key_management import KeyLookupBuilder
keys = KeyLookupBuilder().build()
openai_key = keys['openai'].api_token
```
"""

from .key_lookup import KeyLookup
from .key_lookup_collection import KeyLookupCollection
from .key_lookup_builder import KeyLookupBuilder

__all__ = ["KeyLookup", "KeyLookupCollection", "KeyLookupBuilder"]