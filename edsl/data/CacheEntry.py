from __future__ import annotations
import json
import datetime
import hashlib
import random
from typing import Optional


# TODO: Timestamp should probably be float?


class CacheEntry:
    """
    A Class to represent a cache entry.
    """

    key_fields = ["model", "parameters", "system_prompt", "user_prompt", "iteration"]
    all_fields = key_fields + ["timestamp", "output"]

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
        self._check_types()

    def _check_types(self):
        """
        Checks if the types of the fields are correct.
        """
        if not isinstance(self.model, str):
            raise TypeError("`model` should be a string.")
        if not isinstance(self.parameters, dict):
            raise TypeError("`parameters` should be a dictionary.")
        if not isinstance(self.system_prompt, str):
            raise TypeError("`system_prompt` should be a string.")
        if not isinstance(self.user_prompt, str):
            raise TypeError("`user_prompt` should be a string")
        if not isinstance(self.output, str):
            raise TypeError("`output` should be a string")
        if not isinstance(self.iteration, int):
            raise TypeError("`iteration` should be an integer")
        # TODO: should probably be float
        if not isinstance(self.timestamp, int):
            raise TypeError(f"`timestamp` should be an integer")

    @classmethod
    def gen_key(
        self, *, model, parameters, system_prompt, user_prompt, iteration
    ) -> str:
        """
        Generates a key for the cache entry.
        - Treats single and double quotes as the same.

        TODO: add more robustness.
        """
        long_key = f"{model}{json.dumps(parameters, sort_keys=True)}{system_prompt}{user_prompt}{iteration}"
        return hashlib.md5(long_key.encode()).hexdigest()

    @property
    def key(self) -> str:
        """
        Returns the key for the cache entry.
        - The key is a hash of the key fields.
        """
        d = {k: value for k, value in self.__dict__.items() if k in self.key_fields}
        return self.gen_key(**d)

    def to_dict(self) -> dict:
        """
        Returns a dictionary representation of a CacheEntry.
        """
        return {
            "model": self.model,
            "parameters": self.parameters,
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "output": self.output,
            "iteration": self.iteration,
            "timestamp": self.timestamp,
        }

    def _repr_html_(self) -> str:
        """
        Returns an HTML representation of a CacheEntry.
        """
        from edsl.utilities.utilities import data_to_html

        return data_to_html(self.to_dict())

    def keys(self):
        return list(self.to_dict().keys())

    def values(self):
        return list(self.to_dict().values())

    def __getitem__(self, key):
        """
        Returns the value of a field.
        """
        return getattr(self, key)

    @classmethod
    def from_dict(cls, data: dict) -> CacheEntry:
        """
        Initializes a CacheEntry object from its dictionary representation.
        """
        return cls(**data)

    def __eq__(self, other: CacheEntry) -> bool:
        """
        Checks if two CacheEntry objects are equal.
        - Does not include timestamp in the comparison.
        """
        if not isinstance(other, CacheEntry):
            return False
        for field in self.all_fields:
            if getattr(self, field) != getattr(other, field) and field != "timestamp":
                return False
        return True

    def __repr__(self) -> str:
        """
        Returns a string representation of a CacheEntry.
        """
        return (
            f"CacheEntry(model={repr(self.model)}, "
            f"parameters={self.parameters}, "
            f"system_prompt={repr(self.system_prompt)}, "
            f"user_prompt={repr(self.user_prompt)}, "
            f"output={repr(self.output)}, "
            f"iteration={self.iteration}, "
            f"timestamp={self.timestamp})"
        )

    @classmethod
    def example(cls, randomize: bool = False) -> CacheEntry:
        """
        Returns a CacheEntry example.
        """
        # if random, create a random number for 0-100
        addition = "" if not randomize else str(random.randint(0, 1000))
        return CacheEntry(
            model="gpt-3.5-turbo",
            parameters={"temperature": 0.5},
            system_prompt=f"The quick brown fox jumps over the lazy dog.{addition}",
            user_prompt="What does the fox say?",
            output="The fox says 'hello'",
            iteration=1,
            timestamp=int(datetime.datetime.now(datetime.timezone.utc).timestamp()),
        )

    @classmethod
    def example_dict(cls) -> dict:
        """
        Returns an example dictionary with a single CacheEntry.
        - This will be useful one level up, in the Cache class.
        """
        cache_entry = cls.example()
        return {cache_entry.key: cache_entry}

    @classmethod
    def fetch_input_example(cls) -> dict:
        """
        Creates an example input for a 'fetch' operation.
        - This will be useful one level up, in the Cache class.
        """
        input = cls.example().to_dict()
        _ = input.pop("timestamp")
        _ = input.pop("output")
        return input

    @classmethod
    def store_input_example(cls) -> dict:
        """
        Creates an example input for a 'store' operation.
        - This will be useful one level up, in the Cache class.
        """
        input = cls.example().to_dict()
        _ = input.pop("timestamp")
        input["response"] = input.pop("output")
        return input


def main():
    from edsl.data.CacheEntry import CacheEntry

    # an example of how a cache entry looks
    cache_entry = CacheEntry.example()
    cache_entry

    # .key property returns the hash of the cache entry
    cache_entry.key
    # to dict / from dict
    cache_entry.to_dict()
    CacheEntry.from_dict(cache_entry.to_dict())
    # TODO: this will be false because equality includes timestamp
    CacheEntry.from_dict(cache_entry.to_dict()) == CacheEntry.example()
    # equality by checking values
    cache_entry == CacheEntry.example()
    # equality by checking keys
    cache_entry.key == CacheEntry.example().key
    # evalable repr
    eval(repr(cache_entry)) == cache_entry
    # not sure what these are useful for yet
    cache_entry.example_dict()
    cache_entry.fetch_input_example()
    cache_entry.store_input_example()


if __name__ == "__main__":
    import doctest

    doctest.testmod()
