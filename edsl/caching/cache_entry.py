"""
CacheEntry implementation for the EDSL data caching system.

This module provides the CacheEntry class, which represents a single cached
language model response along with its associated metadata. Cache entries are
uniquely identified by a hash of their key fields, making it efficient to
store and retrieve responses for identical prompts.
"""

from __future__ import annotations
import json
import datetime
import hashlib
from typing import Optional, Dict, List, Any
from uuid import uuid4

from ..base import RepresentationMixin
from .exceptions import CacheError


class CacheEntry(RepresentationMixin):
    """
    Represents a single cached language model response with associated metadata.
    
    CacheEntry objects store language model responses along with the prompts and
    parameters that generated them. Each entry is uniquely identified by a hash
    of its key fields (model, parameters, prompts, and iteration), making it 
    possible to efficiently retrieve cached responses for identical inputs.
    
    Attributes:
        model (str): The language model identifier (e.g., "gpt-3.5-turbo")
        parameters (dict): Model parameters used for generation (e.g., temperature)
        system_prompt (str): The system prompt provided to the model
        user_prompt (str): The user prompt provided to the model
        output (str): The generated response from the language model
        iteration (int): Iteration number, for when multiple outputs are generated
                         with the same prompts (defaults to 0)
        timestamp (int): Unix timestamp when the entry was created
        service (str, optional): The service provider for the model (e.g., "openai")
        
    Class Attributes:
        key_fields (List[str]): Fields used to generate the unique hash key
        all_fields (List[str]): All fields stored in the cache entry
    """

    key_fields = ["model", "parameters", "system_prompt", "user_prompt", "iteration"]
    all_fields = key_fields + ["timestamp", "output", "service"]

    def __init__(
        self,
        *,
        model: str,
        parameters: dict,
        system_prompt: str,
        user_prompt: str,
        iteration: Optional[int] = None,
        output: str,
        timestamp: Optional[int] = None,
        service: Optional[str] = None,
    ):
        self.model = model
        self.parameters = parameters
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.output = output
        self.iteration = iteration or 0
        self.timestamp = timestamp or int(
            datetime.datetime.now(datetime.timezone.utc).timestamp()
        )
        self.service = service
        self._check_types()

    def _check_types(self) -> None:
        """
        Validates that all attributes have the correct types.
        
        This method is called during initialization to ensure that all
        attributes have the expected types, raising TypeError exceptions
        with descriptive messages when validation fails.
        
        Raises:
            TypeError: If any attribute has an incorrect type
        """
        if not isinstance(self.model, str):
            raise CacheError("`model` should be a string.")
        if not isinstance(self.parameters, dict):
            raise CacheError("`parameters` should be a dictionary.")
        if not isinstance(self.system_prompt, str):
            raise CacheError("`system_prompt` should be a string.")
        if not isinstance(self.user_prompt, str):
            raise CacheError("`user_prompt` should be a string")
        if not isinstance(self.output, str):
            raise CacheError("`output` should be a string")
        if not isinstance(self.iteration, int):
            raise CacheError("`iteration` should be an integer")
        # Note: timestamp is stored as int for compatibility, but could be float in future
        if not isinstance(self.timestamp, int):
            raise CacheError("`timestamp` should be an integer")
        if self.service is not None and not isinstance(self.service, str):
            raise CacheError("`service` should be either a string or None")

    @classmethod
    def gen_key(
        cls, *, model: str, parameters: Dict[str, Any], 
        system_prompt: str, user_prompt: str, iteration: int
    ) -> str:
        """
        Generates a unique key hash for the cache entry based on input parameters.
        
        This method creates a deterministic hash key by concatenating the model name,
        parameters (sorted to ensure consistency), system prompt, user prompt, and
        iteration number. The hash enables efficient lookup of cache entries with
        identical inputs.
        
        Args:
            model: The language model identifier
            parameters: Dictionary of model parameters (will be sorted for consistency)
            system_prompt: The system prompt provided to the model
            user_prompt: The user prompt provided to the model
            iteration: Iteration number for this combination of inputs
            
        Returns:
            A hex-encoded MD5 hash string that uniquely identifies this combination
            of inputs
            
        Note:
            - The hash treats single and double quotes as equivalent
            - Parameters are sorted to ensure consistent hashing regardless of order
        """
        long_key = f"{model}{json.dumps(parameters, sort_keys=True)}{system_prompt}{user_prompt}{iteration}"
        return hashlib.md5(long_key.encode()).hexdigest()

    @property
    def key(self) -> str:
        """
        Returns the unique hash key for this cache entry.
        
        This property extracts the key fields from the instance and generates
        a hash key using the gen_key classmethod. The key uniquely identifies
        this combination of model, parameters, prompts, and iteration.
        
        Returns:
            A hex-encoded MD5 hash string that uniquely identifies this cache entry
        """
        d = {k: value for k, value in self.__dict__.items() if k in self.key_fields}
        return self.gen_key(**d)

    def to_dict(self, add_edsl_version: bool = True) -> Dict[str, Any]:
        """
        Converts the cache entry to a dictionary representation.
        
        This method creates a dictionary containing all fields of the cache entry,
        making it suitable for serialization or storage.
        
        Args:
            add_edsl_version: If True, adds EDSL version information to the dict
                              (Currently disabled pending implementation)
                              
        Returns:
            A dictionary representation of the cache entry with all fields
        
        Note:
            The edsl_version feature is currently disabled in the implementation
        """
        d = {
            "model": self.model,
            "parameters": self.parameters,
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "output": self.output,
            "iteration": self.iteration,
            "timestamp": self.timestamp,
            "service": self.service,
        }
        # Feature for adding version information (currently disabled)
        # if add_edsl_version:
        #     from edsl import __version__
        #     d["edsl_version"] = __version__
        #     d["edsl_class_name"] = self.__class__.__name__
        return d

    def keys(self) -> List[str]:
        """
        Returns a list of field names in this cache entry.
        
        This method enables dict-like access to cache entry field names.
        
        Returns:
            List of field names from the dictionary representation
        """
        return list(self.to_dict().keys())

    def values(self) -> List[Any]:
        """
        Returns a list of values for all fields in this cache entry.
        
        This method enables dict-like access to cache entry values.
        
        Returns:
            List of values from the dictionary representation
        """
        return list(self.to_dict().values())

    def __getitem__(self, key: str) -> Any:
        """
        Enables dictionary-style access to cache entry attributes.
        
        This method allows accessing cache entry attributes using dictionary
        syntax (e.g., entry["model"] instead of entry.model).
        
        Args:
            key: The name of the attribute to access
            
        Returns:
            The value of the specified attribute
            
        Raises:
            AttributeError: If the specified attribute doesn't exist
        """
        return getattr(self, key)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CacheEntry:
        """
        Creates a CacheEntry object from a dictionary representation.
        
        This factory method enables reconstruction of CacheEntry objects
        from serialized dictionary representations, such as those produced
        by the to_dict method.
        
        Args:
            data: Dictionary containing required CacheEntry fields
            
        Returns:
            A new CacheEntry instance with fields populated from the dictionary
            
        Raises:
            TypeError: If data contains fields with incorrect types
            KeyError: If required fields are missing from data
        """
        return cls(**data)

    def __eq__(self, other: Any) -> bool:
        """
        Compares this cache entry with another for equality.
        
        This method checks if all fields except timestamp are equal between
        this cache entry and another. The timestamp is excluded from the 
        comparison because it's typically not relevant for determining if
        two entries represent the same cached response.
        
        Args:
            other: Another object to compare with this cache entry
            
        Returns:
            True if all fields except timestamp are equal, False otherwise
            
        Note:
            Returns False if other is not a CacheEntry instance
        """
        if not isinstance(other, CacheEntry):
            return False
        for field in self.all_fields:
            if getattr(self, field) != getattr(other, field) and field != "timestamp":
                return False
        return True

    def __repr__(self) -> str:
        """
        Returns a string representation of this cache entry.
        
        This method creates a string representation that displays all fields
        of the cache entry in a format that can be evaluated to recreate
        the object.
        
        Returns:
            A string representation that can be passed to eval() to recreate
            this cache entry
        """
        return (
            f"CacheEntry(model={repr(self.model)}, "
            f"parameters={self.parameters}, "
            f"system_prompt={repr(self.system_prompt)}, "
            f"user_prompt={repr(self.user_prompt)}, "
            f"output={repr(self.output)}, "
            f"iteration={self.iteration}, "
            f"timestamp={self.timestamp}, "
            f"service={repr(self.service)})"
        )

    @classmethod
    def example(cls, randomize: bool = False) -> CacheEntry:
        """
        Creates an example CacheEntry instance for testing and demonstration.
        
        This factory method generates a pre-populated CacheEntry with example
        values, useful for testing, documentation, and examples.
        
        Args:
            randomize: If True, adds a random UUID to the system prompt to make
                      the entry unique and generate a different hash key
                      
        Returns:
            A fully populated example CacheEntry instance
            
        Example:
            >>> entry = CacheEntry.example()
            >>> isinstance(entry, CacheEntry)
            True
            >>> entry.model
            'gpt-3.5-turbo'
        """
        addition = "" if not randomize else str(uuid4())
        return CacheEntry(
            model="gpt-3.5-turbo",
            parameters={"temperature": 0.5},
            system_prompt=f"The quick brown fox jumps over the lazy dog.{addition}",
            user_prompt="What does the fox say?",
            output="The fox says 'hello'",
            iteration=1,
            timestamp=int(datetime.datetime.now(datetime.timezone.utc).timestamp()),
            service="openai",
        )

    @classmethod
    def example_dict(cls) -> Dict[str, CacheEntry]:
        """
        Creates an example dictionary mapping a key to a CacheEntry.
        
        This method demonstrates how CacheEntry objects are typically stored
        in a cache, with their hash keys as dictionary keys.
        
        Returns:
            A dictionary with a single entry mapping the example entry's key
            to the example entry
            
        Note:
            This is particularly useful for testing and demonstrating the
            Cache class functionality
        """
        cache_entry = cls.example()
        return {cache_entry.key: cache_entry}

    @classmethod
    def fetch_input_example(cls) -> Dict[str, Any]:
        """
        Creates an example input dictionary for a 'fetch' operation.
        
        This method generates a dictionary containing the fields needed to
        look up a cache entry (everything except the response/output fields).
        
        Returns:
            A dictionary with fields needed to generate a cache key for lookup
            
        Note:
            This is used by the Cache class to demonstrate fetch operations
        """
        input = cls.example().to_dict()
        _ = input.pop("timestamp")
        _ = input.pop("output")
        _ = input.pop("service")
        return input

    @classmethod
    def store_input_example(cls) -> Dict[str, Any]:
        """
        Creates an example input dictionary for a 'store' operation.
        
        This method generates a dictionary containing the fields needed to
        store a new cache entry, with 'output' renamed to 'response' to match
        the API of the Cache.store method.
        
        Returns:
            A dictionary with fields needed to store a new cache entry
            
        Note:
            This is used by the Cache class to demonstrate store operations
        """
        input = cls.example().to_dict()
        _ = input.pop("timestamp")
        input["response"] = input.pop("output")
        return input


def main() -> None:
    """
    Demonstration of CacheEntry functionality for interactive testing.
    
    This function demonstrates the key features of the CacheEntry class,
    including creating entries, calculating hash keys, converting to/from
    dictionaries, and comparing entries.
    
    Note:
        This function is intended to be run in an interactive Python session
        for exploration and testing, not as part of normal code execution.
    """
    from .cache_entry import CacheEntry

    # Create an example cache entry
    cache_entry = CacheEntry.example()
    print(f"Example cache entry: {cache_entry}")

    # Demonstrate key generation
    print(f"Cache key: {cache_entry.key}")
    
    # Demonstrate serialization and deserialization
    entry_dict = cache_entry.to_dict()
    print(f"Dictionary representation: {entry_dict}")
    reconstructed = CacheEntry.from_dict(entry_dict)
    print(f"Reconstructed from dict: {reconstructed}")
    
    # Demonstrate equality comparisons
    print(f"Same content equals: {cache_entry == CacheEntry.example()}")
    print(f"Same key equals: {cache_entry.key == CacheEntry.example().key}")
    
    # Demonstrate repr evaluation
    print(f"Repr can be evaluated: {eval(repr(cache_entry)) == cache_entry}")
    
    # Demonstrate utility methods
    print(f"Example dict: {CacheEntry.example_dict()}")
    print(f"Fetch input example: {CacheEntry.fetch_input_example()}")
    print(f"Store input example: {CacheEntry.store_input_example()}")


if __name__ == "__main__":
    import doctest

    doctest.testmod()
