from collections import UserDict

from .KeyLookupBuilder import KeyLookupBuilder

class KeyLookupCollection(UserDict):
    """A singleton class that stores key-lookup objects.

    This is because once a KeyLook is created once, we do not
    need to keep re-creating it.

    >>> collection = KeyLookupCollection()
    >>> collection2 = KeyLookupCollection()
    >>> collection is collection2  # Test singleton pattern
    True
    >>> collection.add_key_lookup(("config", "env"))
    >>> ("config", "env") in collection.data
    True
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
        if fetch_order is None:
            fetch_order = ("config", "env")
        if fetch_order not in self.data:
            self.data[fetch_order] = KeyLookupBuilder(fetch_order=fetch_order).build()
