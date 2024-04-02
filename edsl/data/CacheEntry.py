import datetime
import time
import hashlib


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
        iteration: int = None,
        output: str,
        timestamp: int = None,
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
        Generate a key for the cache entry.

        >>> CacheEntry.gen_key(model = "gpt-3.5-turbo", parameters = "{'temperature': 0.5}", system_prompt = "The quick brown fox jumps over the lazy dog.", user_prompt = "What does the fox say?", iteration = 1)
        '55ce2e13d38aa7fb6ec848053285edb4'
        """
        long_key = f"{model}{parameters}{system_prompt}{user_prompt}{iteration}"
        return hashlib.md5(long_key.encode()).hexdigest()

    @property
    def key(self) -> str:
        """
        Return the key for the cache entry.

        >>> CacheEntry.example().key
        '55ce2e13d38aa7fb6ec848053285edb4'
        """
        d = {k: value for k, value in self.__dict__.items() if k in self.key_fields}
        return self.gen_key(**d)

    def __eq__(self, other_entry: "CacheEntry") -> bool:
        """Check if two cache entries are equal.

        :param other_entry: The other cache entry to compare to.

        >>> CacheEntry.example() == CacheEntry.example()
        True
        """
        for field in self.all_fields:
            if getattr(self, field) != getattr(other_entry, field):
                return False
        return True

    @classmethod
    def example_dict(cls) -> dict:
        """Return an example dictionary of cache entries."""
        entity = cls.example()
        key = entity.key
        return {key: entity}

    @classmethod
    def fetch_input_example(cls) -> dict:
        """
        Create an example input for a 'fetch' operation.
        """
        input = cls.example().to_dict()
        _ = input.pop("timestamp")
        _ = input.pop("output")
        return input

    @classmethod
    def store_input_example(cls) -> dict:
        """
        Create an example input for a 'store' operation.
        """
        input = cls.example().to_dict()
        _ = input.pop("timestamp")
        input["response"] = input.pop("output")
        return input

    def to_dict(self) -> dict:
        """Return a dictionary representation of the cache entry."""
        return {
            "model": self.model,
            "parameters": self.parameters,
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "output": self.output,
            "iteration": self.iteration,
            "timestamp": self.timestamp,
        }

    def __repr__(self) -> str:
        return f"CacheEntry(model={self.model}, parameters={self.parameters}, system_prompt={self.system_prompt}, user_prompt={self.user_prompt}, output={self.output}, iteration={self.iteration}, timestamp={self.timestamp})"

    @classmethod
    def from_dict(cls, data: dict) -> "CacheEntry":
        """Create a cache entry from a dictionary representation."""
        return cls(**data)

    @classmethod
    def example(cls) -> "CacheEntry":
        return CacheEntry(
            model="gpt-3.5-turbo",
            parameters={"temperature": 0.5},
            system_prompt="The quick brown fox jumps over the lazy dog.",
            user_prompt="What does the fox say?",
            output="The fox says 'hello'",
            iteration=1,
            timestamp=int(datetime.datetime.now(datetime.timezone.utc).timestamp()),
        )


def main():
    from edsl.data.CacheEntry import CacheEntry

    # an example of how a cache entry looks
    CacheEntry.example()
    # the key gives the hash of the cache entry
    CacheEntry.example().key
    # kind of a forward method, that will be used by Cache
    CacheEntry.example().example_dict()
    # to dict / from dict
    CacheEntry.example().to_dict()
    CacheEntry.from_dict(CacheEntry.example().to_dict())

    # equality through checking one by one
    CacheEntry.example() == CacheEntry.example()
    # but could also check the hash
    CacheEntry.example().key == CacheEntry.example().key


if __name__ == "__main__":
    import doctest

    doctest.testmod()
