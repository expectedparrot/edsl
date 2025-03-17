from collections import UserDict

# Import for doctest and type hints
from .key_lookup_builder import KeyLookupBuilder
from .key_lookup import KeyLookup

class KeyLookupCollection(UserDict):
    """Singleton collection for caching and reusing KeyLookup objects.
    
    KeyLookupCollection implements the singleton pattern to provide a global registry
    of KeyLookup objects. It avoids rebuilding KeyLookup objects with the same 
    fetch_order by storing and reusing previously created instances.
    
    This collection serves several purposes:
    - Reduces overhead by avoiding redundant API key discovery
    - Ensures consistency by reusing the same credentials throughout an application
    - Provides a central access point for credential configuration
    
    The collection uses fetch_order tuples as keys and KeyLookup objects as values,
    creating a new KeyLookup only when a new fetch_order is requested.
    
    Singleton behavior:
        >>> collection = KeyLookupCollection()
        >>> collection2 = KeyLookupCollection()
        >>> collection is collection2  # Same instance
        True
        
    Basic usage:
        >>> from edsl.key_management import KeyLookup
        >>> collection = KeyLookupCollection()
        >>> collection.add_key_lookup(("config", "env"))
        >>> lookup = collection[("config", "env")]  # Get the stored KeyLookup
        >>> isinstance(lookup, KeyLookup)
        True
        >>> ("config", "env") in collection
        True
        
    Technical Notes:
        - Uses __new__ to implement the singleton pattern
        - Lazily creates KeyLookup objects only when requested
        - Default fetch_order is ("config", "env") if not specified
    """

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
        """Add a KeyLookup to the collection with the specified fetch order.
        
        Creates a new KeyLookup using the KeyLookupBuilder with the given fetch_order,
        or uses a default fetch_order of ("config", "env") if none is provided.
        
        The created KeyLookup is stored in the collection using the fetch_order as the key.
        If a KeyLookup with the same fetch_order already exists, this method does nothing.
        
        Args:
            fetch_order: Tuple specifying the order of sources to fetch credentials from.
                        Later sources override earlier ones. If None, uses ("config", "env").
                        
        Examples:
            >>> collection = KeyLookupCollection()
            >>> collection.add_key_lookup(("config", "env", "coop"))
            >>> ("config", "env", "coop") in collection
            True
            
        Technical Notes:
            - KeyLookup objects are created lazily only when needed
            - Sources can include: "config", "env", "coop"
            - The fetch_order determines credential priority
        """
        if fetch_order is None:
            fetch_order = ("config", "env")
        if fetch_order not in self.data:
            self.data[fetch_order] = KeyLookupBuilder(fetch_order=fetch_order).build()
