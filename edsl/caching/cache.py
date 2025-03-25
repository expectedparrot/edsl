"""
Cache implementation for storing and retrieving language model responses.

This module provides the Cache class, which is the core component of EDSL's caching system.
The caching system stores language model responses to avoid redundant API calls,
reducing costs and latency while improving reproducibility of results.

The Cache class handles:
- Storage and retrieval of model responses via key-based lookups
- Persistence to and from disk using various formats (.jsonl, .db)
- Merging and comparing caches from different sources
- Integration with remote caching systems

The primary workflow involves:
1. Fetching responses from cache if they exist
2. Storing new responses when they don't
3. Persisting cache state to disk when needed

Cache objects can be used:
- Directly by the user for explicit cache management
- Implicitly by the CacheHandler which manages cache selection and migrations
- In conjunction with remote caching services

Implementation Notes:
- Cache uses CacheEntry objects as its values
- Keys are hash-based identifiers of the input parameters
- Multiple storage backends are supported (dict, SQLiteDict)
"""

from __future__ import annotations
import json
import os
import warnings
from typing import Optional, Union, TYPE_CHECKING

from ..base import Base
from ..utilities import remove_edsl_version, dict_hash
from .exceptions import CacheError
from .sql_dict import SQLiteDict

if TYPE_CHECKING:
    from .cache_entry import CacheEntry

class Cache(Base):
    """Cache for storing and retrieving language model responses.
    
    The Cache class manages a collection of CacheEntry objects, providing methods for
    storing, retrieving, and persisting language model responses. It serves as the core
    component of EDSL's caching infrastructure, helping to reduce redundant API calls,
    save costs, and ensure reproducibility.
    
    Cache can use different storage backends:
    - In-memory dictionary (default)
    - SQLite database via SQLiteDict
    - JSON lines file (.jsonl)
    
    The cache operates by generating deterministic keys based on the model, parameters,
    prompts, and iteration number. This allows for efficient lookup of cached responses
    when identical requests are made.
    
    Attributes:
        data (dict or SQLiteDict): The primary storage for cache entries
        new_entries (dict): Entries added in the current session
        fetched_data (dict): Entries retrieved in the current session
        filename (str, optional): Path for persistence if provided
        immediate_write (bool): Whether to update data immediately (True) or defer (False)
        
    Technical Notes:
        - Can be used as a context manager to automatically persist changes on exit
        - Supports serialization/deserialization via to_dict/from_dict methods
        - Implements set operations (addition, subtraction) for combining caches
        - Integrates with the broader EDSL caching infrastructure via CacheHandler
    """

    __documentation__ = "https://docs.expectedparrot.com/en/latest/caching.html"

    data = {}

    def __init__(
        self,
        *,
        filename: Optional[str] = None,
        data: Optional[Union["SQLiteDict", dict]] = None,
        immediate_write: bool = True,
        method=None,
        verbose=False,
    ):
        """Initialize a new Cache instance.
        
        Creates a new cache for storing language model responses. The cache can be initialized 
        with existing data or connected to a persistent storage file.
        
        Args:
            filename: Path to a persistent storage file (.jsonl or .db). If provided, the cache
                     will be initialized from this file and changes will be written back to it.
                     Cannot be used together with data parameter.
            data: Initial cache data as a dictionary or SQLiteDict. Cannot be used together 
                  with filename parameter.
            immediate_write: If True, new entries are immediately added to the main data store.
                            If False, they're kept separate until explicitly written.
            method: Deprecated. Legacy parameter for backward compatibility.
            verbose: If True, prints diagnostic information about cache hits and misses.
            
        Raises:
            CacheError: If both filename and data are provided, or if the filename has an 
                       invalid extension.
                       
        Implementation Notes:
            - The cache maintains separate dictionaries for tracking:
              * data: The main persistent storage
              * new_entries: Entries added in this session
              * fetched_data: Entries fetched in this session
              * new_entries_to_write_later: Entries to be written if immediate_write=False
            - If loading from a file, the appropriate loader method is called based on extension
        """

        # self.data_at_init = data or {}
        self.fetched_data = {}
        self.immediate_write = immediate_write
        self.method = method
        self.new_entries = {}
        self.new_entries_to_write_later = {}
        self.coop = None
        self.verbose = verbose

        self.filename = filename
        if filename and data:
            raise CacheError("Cannot provide both filename and data")
        if filename is None and data is None:
            data = {}
        if data is not None:
            self.data = data
        if filename is not None:
            self.data = {}
            if filename.endswith(".jsonl"):
                if os.path.exists(filename):
                    self.add_from_jsonl(filename)
                else:
                    print(
                        f"File {filename} not found, but will write to this location."
                    )
            elif filename.endswith(".db"):
                if os.path.exists(filename):
                    self.add_from_sqlite(filename)
            else:
                raise CacheError("Invalid file extension. Must be .jsonl or .db")

        self._perform_checks()

    def code(sefl):
        pass
        # raise NotImplementedError("This method is not implemented yet.")

    def keys(self):
        """Return a list of all cache keys.
        
        Retrieves all cache keys, which are the unique identifiers for each cache entry.
        
        Returns:
            list: A list of string keys in the cache
            
        Examples:
            >>> from edsl import Cache
            >>> Cache.example().keys()
            ['5513286eb6967abc0511211f0402587d']
        """
        return list(self.data.keys())

    def values(self):
        """Return a list of all cache entry values.
        
        Retrieves all CacheEntry objects stored in the cache.
        
        Returns:
            list: A list of CacheEntry objects
            
        Examples:
            >>> from edsl import Cache
            >>> entries = Cache.example().values()
            >>> len(entries)
            1
            >>> entries[0]  # doctest: +ELLIPSIS
            CacheEntry(model='gpt-3.5-turbo', parameters={'temperature': 0.5}, ...)
        """
        return list(self.data.values())

    def items(self):
        """Return an iterator of (key, value) pairs in the cache.
        
        Similar to dict.items(), provides an iterator over all key-value pairs
        in the cache for easy iteration.
        
        Returns:
            zip: An iterator of (key, CacheEntry) tuples
        """
        return zip(self.keys(), self.values())

    def new_entries_cache(self) -> Cache:
        """Return a new Cache object with the new entries."""
        return Cache(data={**self.new_entries, **self.fetched_data})

    def _perform_checks(self):
        """Perform checks on the cache."""
        from .cache_entry import CacheEntry

        if any(not isinstance(value, CacheEntry) for value in self.data.values()):
            raise CacheError("Not all values are CacheEntry instances")
        if self.method is not None:
            warnings.warn("Argument `method` is deprecated", DeprecationWarning)

    ####################
    # READ/WRITE
    ####################
    def fetch(
        self,
        *,
        model: str,
        parameters: dict,
        system_prompt: str,
        user_prompt: str,
        iteration: int,
    ) -> tuple(Union[None, str], str):
        """Retrieve a cached language model response if available.
        
        This method attempts to find a cached response matching the exact input parameters.
        The combination of model, parameters, prompts, and iteration creates a unique key
        that identifies a specific language model request.
        
        Args:
            model: Language model identifier (e.g., "gpt-3.5-turbo")
            parameters: Model configuration parameters (e.g., temperature, max_tokens)
            system_prompt: The system instructions given to the model
            user_prompt: The user query/prompt given to the model
            iteration: The iteration number for this specific request
            
        Returns:
            tuple: (response, key) where:
                - response: The cached model output as a string, or None if not found
                - key: The cache key string generated for this request
                
        Technical Notes:
            - Uses CacheEntry.gen_key() to generate a consistent hash-based key
            - Updates self.fetched_data when a hit occurs to track cache usage
            - Optionally logs cache hit/miss when verbose=True
            - The response is returned as a JSON string for consistency
            
        Examples:
            >>> c = Cache()
            >>> c.fetch(model="gpt-3", parameters="default", system_prompt="Hello", 
            ...         user_prompt="Hi", iteration=1)[0] is None
            True
        """
        from .cache_entry import CacheEntry

        key = CacheEntry.gen_key(
            model=model,
            parameters=parameters,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            iteration=iteration,
        )
        entry = self.data.get(key, None)
        if entry is not None:
            if self.verbose:
                print(f"Cache hit for key: {key}")
            self.fetched_data[key] = entry
        else:
            if self.verbose:
                print(f"Cache miss for key: {key}")
        return None if entry is None else entry.output, key

    def store(
        self,
        model: str,
        parameters: str,
        system_prompt: str,
        user_prompt: str,
        response: dict,
        iteration: int,
        service: str,
    ) -> str:
        """Store a new language model response in the cache.
        
        Creates a new CacheEntry from the provided parameters and response, then
        adds it to the cache using a deterministic key derived from the input parameters.
        
        Args:
            model: Language model identifier (e.g., "gpt-3.5-turbo")
            parameters: Model configuration parameters (e.g., temperature, max_tokens)
            system_prompt: The system instructions given to the model
            user_prompt: The user query/prompt given to the model
            response: The model's response as a dictionary
            iteration: The iteration number for this specific request
            service: The service provider (e.g., "openai", "anthropic")
            
        Returns:
            str: The cache key generated for this entry
            
        Technical Notes:
            - Creates a new CacheEntry object to encapsulate the response and metadata
            - Adds the entry to self.new_entries to track entries added in this session
            - Adds the entry to the main data store if immediate_write=True
            - Otherwise, stores in new_entries_to_write_later for deferred writing
            - The response is stored as a JSON string for consistency and compatibility
            
        Storage Behavior:
            The method's behavior depends on the immediate_write setting:
            - If True: Immediately writes to the main data store (self.data)
            - If False: Stores in a separate dict for writing later (e.g., at context exit)
            
        Examples:
            >>> from edsl import Cache, Model, Question
            >>> m = Model("test") 
            >>> c = Cache()
            >>> len(c)
            0
            >>> results = Question.example("free_text").by(m).run(cache=c, 
            ...         disable_remote_cache=True, disable_remote_inference=True)
            >>> len(c)
            1
        """
        from .cache_entry import CacheEntry

        entry = CacheEntry(
            model=model,
            parameters=parameters,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output=json.dumps(response),
            iteration=iteration,
            service=service,
        )
        key = entry.key
        self.new_entries[key] = entry
        if self.immediate_write:
            self.data[key] = entry
        else:
            self.new_entries_to_write_later[key] = entry
        return key

    def add_from_dict(
        self, new_data: dict[str, "CacheEntry"], write_now: Optional[bool] = True
    ) -> None:
        """
        Add entries to the cache from a dictionary.

        :param write_now: Whether to write to the cache immediately (similar to `immediate_write`).
        """
        from .cache_entry import CacheEntry

        for key, value in new_data.items():
            if key in self.data:
                if value != self.data[key]:
                    raise CacheError("Mismatch in values")
            if not isinstance(value, CacheEntry):
                raise CacheError(f"Wrong type - the observed type is {type(value)}")

        self.new_entries.update(new_data)
        if write_now:
            self.data.update(new_data)
        else:
            self.new_entries_to_write_later.update(new_data)

    def add_from_jsonl(self, filename: str, write_now: Optional[bool] = True) -> None:
        """
        Add entries to the cache from a JSONL.

        :param write_now: Whether to write to the cache immediately (similar to `immediate_write`).
        """
        from .cache_entry import CacheEntry

        with open(filename, "a+") as f:
            f.seek(0)
            lines = f.readlines()
        new_data = {}
        for line in lines:
            d = json.loads(line)
            key = list(d.keys())[0]
            value = list(d.values())[0]
            new_data[key] = CacheEntry(**value)
        self.add_from_dict(new_data=new_data, write_now=write_now)

    def add_from_sqlite(self, db_path: str, write_now: Optional[bool] = True):
        """
        Add entries to the cache from an SQLite database.

        :param write_now: Whether to write to the cache immediately (similar to `immediate_write`).
        """
        from .sql_dict import SQLiteDict
        from .cache_entry import CacheEntry

        db = SQLiteDict(db_path)
        new_data = {}
        for key, value in db.items():
            new_data[key] = CacheEntry(**value)
        self.add_from_dict(new_data=new_data, write_now=write_now)

    @classmethod
    def from_sqlite_db(cls, db_path: str) -> Cache:
        """Construct a Cache from a SQLite database."""
        from .sql_dict import SQLiteDict

        return cls(data=SQLiteDict(db_path))

    @classmethod
    def from_local_cache(cls) -> Cache:
        """Construct a Cache from a local cache file."""
        from ..config import CONFIG

        CACHE_PATH = CONFIG.get("EDSL_DATABASE_PATH")
        path = CACHE_PATH.replace("sqlite:///", "")
        # db_path = os.path.join(os.path.dirname(path), "data.db")
        return cls.from_sqlite_db(path)

    @classmethod
    def from_jsonl(cls, jsonlfile: str, db_path: Optional[str] = None) -> Cache:
        """
        Construct a Cache from a JSONL file.

        :param jsonlfile: The path to the JSONL file of cache entries.
        :param db_path: The path to the SQLite database used to store the cache.

        * If `db_path` is None, the cache will be stored in memory, as a dictionary.
        * If `db_path` is provided, the cache will be stored in an SQLite database.
        """
        # if a file doesn't exist at jsonfile, throw an error
        from .sql_dict import SQLiteDict
        from .exceptions import CacheFileNotFoundError

        if not os.path.exists(jsonlfile):
            raise CacheFileNotFoundError(f"File {jsonlfile} not found")

        if db_path is None:
            data = {}
        else:
            data = SQLiteDict(db_path)

        cache = Cache(data=data)
        cache.add_from_jsonl(jsonlfile)
        return cache

    def write_sqlite_db(self, db_path: str) -> None:
        """
        Write the cache to an SQLite database.
        """
        ## TODO: Check to make sure not over-writing (?)
        ## Should be added to SQLiteDict constructor (?)
        from .sql_dict import SQLiteDict

        new_data = SQLiteDict(db_path)
        for key, value in self.data.items():
            new_data[key] = value

    def write(self, filename: Optional[str] = None) -> None:
        """
        Write the cache to a file at the specified location.
        """
        if filename is None:
            filename = self.filename
        if filename.endswith(".jsonl"):
            self.write_jsonl(filename)
        elif filename.endswith(".db"):
            self.write_sqlite_db(filename)
        else:
            raise CacheError("Invalid file extension. Must be .jsonl or .db")

    def write_jsonl(self, filename: str) -> None:
        """
        Write the cache to a JSONL file.
        """
        path = os.path.join(os.getcwd(), filename)
        with open(path, "w") as f:
            for key, value in self.data.items():
                f.write(json.dumps({key: value.to_dict()}) + "\n")

    def to_scenario_list(self):
        from ..scenarios import ScenarioList, Scenario

        scenarios = []
        for key, value in self.data.items():
            new_d = value.to_dict()
            new_d["cache_key"] = key
            s = Scenario(new_d)
            scenarios.append(s)
        return ScenarioList(scenarios)

    def __floordiv__(self, other: "Cache") -> "Cache":
        """Subtract one cache from another, returning entries unique to this cache.
        
        This operator implements set difference between two caches, returning a new cache 
        containing only entries that exist in this cache but not in the other cache.
        The floor division operator (//) is used as an intuitive alternative to subtraction.
        
        Args:
            other: Another Cache object to subtract from this one
            
        Returns:
            Cache: A new Cache containing only entries unique to this cache
            
        Raises:
            CacheError: If the provided object is not a Cache instance
            
        Examples:
            >>> from edsl.caching import CacheEntry
            >>> ce1 = CacheEntry.example(randomize=True)
            >>> ce2 = CacheEntry.example(randomize=True)
            >>> c1 = Cache(data={ce1.key: ce1, ce2.key: ce2})
            >>> c2 = Cache(data={ce1.key: ce1})
            >>> c3 = c1 // c2  # Get entries in c1 that aren't in c2
            >>> len(c3)
            1
            >>> c3.data[ce2.key] == ce2
            True
            
        Technical Notes:
            - Comparison is based on cache keys, not the full entry contents
            - Returns a new Cache instance with the same immediate_write setting
            - Useful for identifying new entries or differences between caches
        """
        if not isinstance(other, Cache):
            raise CacheError("Can only compare two caches")

        diff_data = {k: v for k, v in self.data.items() if k not in other.data}
        return Cache(data=diff_data, immediate_write=self.immediate_write)

    @classmethod
    def from_url(cls, db_path=None) -> Cache:
        """
        Construct a Cache object from a remote.
        """
        # ...do something here
        # return Cache(data=db)
        pass

    def __enter__(self):
        """Set up the cache when used as a context manager.
        
        Enables usage of Cache in a with statement, e.g.:
        ```python
        with Cache(filename="my_cache.db") as cache:
            # Use cache...
        # Changes automatically saved when exiting the context
        ```
        
        Returns:
            Cache: The cache instance itself
        """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Clean up and persist cache when exiting the context.
        
        This method is called automatically when exiting a with block.
        It performs two key operations:
        1. Writes any deferred entries to the main data store
        2. Persists the cache to disk if a filename was provided
        
        Args:
            exc_type: Exception type if an exception was raised in the with block
            exc_value: Exception value if an exception was raised
            traceback: Traceback if an exception was raised
            
        Technical Notes:
            - Deferred entries (new_entries_to_write_later) are written to the main data store
            - If a filename was provided at initialization, cache is persisted to that file
            - Persistence format is determined by the filename extension (.jsonl or .db)
        """
        # Write any deferred entries to the main data store
        for key, entry in self.new_entries_to_write_later.items():
            self.data[key] = entry

        # Persist the cache to disk if a filename was provided
        if self.filename:
            self.write(self.filename)

    def __hash__(self):
        """Return the hash of the Cache."""

        return dict_hash(self.to_dict(add_edsl_version=False))

    def to_dict(self, add_edsl_version=True) -> dict:
        """Serialize the cache to a dictionary for storage or transmission.
        
        Converts the Cache object into a plain dictionary format that can be
        easily serialized to JSON or other formats. Each CacheEntry is also
        converted to a dictionary using its to_dict method.
        
        Args:
            add_edsl_version: If True, includes the EDSL version and class name
                              in the serialized output for compatibility tracking
                              
        Returns:
            dict: A dictionary representation of the cache with the structure:
                {
                    "key1": {cache_entry1_dict},
                    "key2": {cache_entry2_dict},
                    ...
                    "edsl_version": "x.x.x",  # if add_edsl_version=True
                    "edsl_class_name": "Cache"  # if add_edsl_version=True
                }
                
        Technical Notes:
            - Used by from_dict for deserialization
            - Used by __hash__ for cache comparison
            - The version info allows for proper handling of format changes
        """
        d = {k: v.to_dict() for k, v in self.data.items()}
        if add_edsl_version:
            from .. import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = "Cache"

        return d

    def _summary(self) -> dict:
        return {"EDSL Class": "Cache", "Number of entries": len(self.data)}

    def table(
        self,
        *fields,
        tablefmt: Optional[str] = None,
        pretty_labels: Optional[dict] = None,
    ) -> str:
        return self.to_dataset().table(
            *fields, tablefmt=tablefmt, pretty_labels=pretty_labels
        )

    def select(self, *fields):
        return self.to_dataset().select(*fields)

    def tree(self, node_list: Optional[list[str]] = None):
        return self.to_scenario_list().tree(node_list)

    def to_dataset(self):
        return self.to_scenario_list().to_dataset()

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data) -> Cache:
        """Construct a Cache from a dictionary."""
        from .cache_entry import CacheEntry

        newdata = {k: CacheEntry.from_dict(v) for k, v in data.items()}
        return cls(data=newdata)

    def __len__(self):
        """Return the number of CacheEntry objects in the Cache."""
        return len(self.data)

    # TODO: Same inputs could give different results and this could be useful
    # can't distinguish unless we do the ε trick or vary iterations
    def __eq__(self, other_cache: "Cache") -> bool:
        """
        Check if two Cache objects are equal.
        Does not verify their values are equal, only that they have the same keys.
        """
        if not isinstance(other_cache, Cache):
            return False
        return set(self.data.keys()) == set(other_cache.data.keys())

    def __add__(self, other: "Cache"):
        """Combine this cache with another, updating in-place.
        
        This operator implements a set union operation between two caches, adding all
        entries from the other cache into this one. The operation modifies this cache
        in-place rather than creating a new one.
        
        Args:
            other: Another Cache object to merge into this one
            
        Returns:
            Cache: Self, with entries from other added
            
        Raises:
            CacheError: If the provided object is not a Cache instance
            
        Technical Notes:
            - Modifies this cache in-place (unlike __floordiv__ which returns a new cache)
            - If both caches have the same key, this cache's entry will be overwritten
            - Useful for merging caches from different sources
            - No special handling for conflicting entries - last one wins
            
        Examples:
            >>> from edsl.caching import CacheEntry
            >>> ce1 = CacheEntry.example(randomize=True)
            >>> ce2 = CacheEntry.example(randomize=True)
            >>> c1 = Cache(data={ce1.key: ce1})
            >>> initial_len = len(c1)
            >>> c2 = Cache(data={ce2.key: ce2})
            >>> result = c1 + c2  # Add c2's entries to c1
            >>> len(c1) > initial_len  # Should have more entries now
            True
        """
        if not isinstance(other, Cache):
            raise CacheError("Can only add two caches together")
        self.data.update(other.data)
        return self

    def __repr__(self):
        """
        Return a string representation of the Cache object.
        """
        return (
            f"Cache(data = {repr(self.data)}, immediate_write={self.immediate_write})"
        )

    ####################
    # EXAMPLES
    ####################
    def fetch_input_example(self) -> dict:
        """
        Create an example input for a 'fetch' operation.
        """
        from .cache_entry import CacheEntry

        return CacheEntry.fetch_input_example()

    def to_html(self):
        # json_str = json.dumps(self.data, indent=4)
        d = {k: v.to_dict() for k, v in self.data.items()}
        for key, value in d.items():
            for k, v in value.items():
                if isinstance(v, dict):
                    d[key][k] = {kk: str(vv) for kk, vv in v.items()}
                else:
                    d[key][k] = str(v)

        json_str = json.dumps(d, indent=4)

        # HTML template with the JSON string embedded
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Display JSON</title>
        </head>
        <body>
            <pre id="jsonData"></pre>
            <script>
                var json = {json_str};

                // JSON.stringify with spacing to format
                document.getElementById('jsonData').textContent = JSON.stringify(json, null, 4);
            </script>
        </body>
        </html>
        """
        return html

    def subset(self, keys: list[str]) -> Cache:
        """
        Return a subset of the Cache with the specified keys.
        """
        new_data = {k: v for k, v in self.data.items() if k in keys}
        return Cache(data=new_data)

    def view(self) -> None:
        """View the Cache in a new browser tab."""
        import tempfile
        import webbrowser

        html_content = self.to_html()
        # Create a temporary file to hold the HTML
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".html") as tmpfile:
            tmpfile.write(html_content)
            # Get the path to the temporary file
            filepath = tmpfile.name

        # Open the HTML file in a new browser tab
        webbrowser.open("file://" + filepath)

    @classmethod
    def example(cls, randomize: bool = False) -> Cache:
        """Create an example Cache instance for testing and demonstration.
        
        Creates a Cache object pre-populated with example CacheEntry objects.
        This method is useful for documentation, testing, and demonstration purposes.
        
        Args:
            randomize: If True, creates CacheEntry objects with randomized content
                      for uniqueness. If False, uses consistent example entries.
                      
        Returns:
            Cache: A new Cache object containing example CacheEntry objects
            
        Technical Notes:
            - Uses CacheEntry.example() to create sample entries
            - When randomize=True, generates unique keys for each call
            - When randomize=False, produces consistent examples for doctests
            - Creates an in-memory cache (no persistent file)
            
        Examples:
            >>> cache = Cache.example()
            >>> len(cache) > 0
            True
            >>> from edsl.caching.cache_entry import CacheEntry
            >>> all(isinstance(entry, CacheEntry) for entry in cache.values())
            True
            
            >>> # Create examples with randomized content
            >>> cache1 = Cache.example(randomize=True)
            >>> cache2 = Cache.example(randomize=True)
            >>> # With randomization, keys should be different
            >>> len(cache1) > 0 and len(cache2) > 0
            True
        """
        from .cache_entry import CacheEntry

        # Maintain the original implementation exactly to preserve behavior
        return cls(
            data={
                CacheEntry.example(randomize).key: CacheEntry.example(),
                CacheEntry.example(randomize).key: CacheEntry.example(),
            }
        )


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
