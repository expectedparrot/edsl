import datetime
import hashlib
from typing import Optional

# TODO: deal better with types
# passing in
#    parameters = "{'temperature': 0.5}"
# vs
#    parameters = '{"temperature": 0.5}'
# yields different hashes

# TODO: equality includes timestamps. Is that what we want?


class CacheEntry:
    """Class to represent a cache entry."""

    key_fields = ["model", "parameters", "system_prompt", "user_prompt", "iteration"]
    all_fields = key_fields + ["timestamp", "output"]

    def __init__(
        self,
        *,
        model: str,
        parameters: str,
        system_prompt: str,
        user_prompt: str,
        output: str,
        iteration: Optional[int] = None,
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

    @classmethod
    def gen_key(
        self, *, model, parameters, system_prompt, user_prompt, iteration
    ) -> str:
        """
        Generates a key for the cache entry.

        >>> CacheEntry.gen_key(model = "gpt-3.5-turbo", parameters = "{'temperature': 0.5}", system_prompt = "The quick brown fox jumps over the lazy dog.", user_prompt = "What does the fox say?", iteration = 1)
        '55ce2e13d38aa7fb6ec848053285edb4'
        """
        long_key = f"{model}{parameters}{system_prompt}{user_prompt}{iteration}"
        return hashlib.md5(long_key.encode()).hexdigest()

    @property
    def key(self) -> str:
        """
        Returns the key for the cache entry.

        >>> CacheEntry.example().key
        '55ce2e13d38aa7fb6ec848053285edb4'
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

    @classmethod
    def from_dict(cls, data: dict) -> "CacheEntry":
        """
        Initializes a CacheEntry object from its dictionary representation.
        """
        return cls(**data)

    def __eq__(self, other: "CacheEntry") -> bool:
        """
        Checks if two CacheEntry objects are equal.
        - Includes timestamp in the comparison.
        """
        for field in self.all_fields:
            if getattr(self, field) != getattr(other, field):
                return False
        return True

    def __repr__(self) -> str:
        """
        Returns a string representation of a CacheEntry.
        """
        return f"CacheEntry(model={self.model}, parameters={self.parameters}, system_prompt={self.system_prompt}, user_prompt={self.user_prompt}, output={self.output}, iteration={self.iteration}, timestamp={self.timestamp})"

    @classmethod
    def example(cls) -> "CacheEntry":
        """
        Returns a CacheEntry example.
        """
        return CacheEntry(
            model="gpt-3.5-turbo",
            parameters={"temperature": 0.5},
            system_prompt="The quick brown fox jumps over the lazy dog.",
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
    # the key gives the hash of the cache entry
    cache_entry.key
    # kind of a forward method, that will be used by Cache
    cache_entry.example_dict()
    # to dict / from dict
    cache_entry.to_dict()
    CacheEntry.from_dict(cache_entry.to_dict())
    # TODO: this will be false because equality includes timestamp
    CacheEntry.from_dict(cache_entry.to_dict()) == CacheEntry.example()
    # equality through checking one by one
    CacheEntry.example() == CacheEntry.example()
    # but could also check the hash
    cache_entry.key == CacheEntry.example().key

    # not sure what these are useful for yet
    cache_entry.example_dict()
    cache_entry.fetch_input_example()
    cache_entry.store_input_example()


if __name__ == "__main__":
    import doctest

    doctest.testmod()
