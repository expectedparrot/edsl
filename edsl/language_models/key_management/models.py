from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class APIKeyEntry:
    """A class representing an API key entry.

    >>> entry = APIKeyEntry.example()
    >>> entry.service
    'openai'
    >>> entry.name
    'OPENAI_API_KEY'
    >>> entry.value
    'sk-abcd1234'
    >>> entry.source
    'env'
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
    """A class representing rate limit entries for a service.

    >>> limit = LimitEntry.example()
    >>> limit.service
    'openai'
    >>> limit.rpm
    60
    >>> limit.tpm
    100000
    >>> limit.source
    'config'
    """

    service: str
    rpm: int
    tpm: int
    source: Optional[str] = None

    @classmethod
    def example(cls):
        return LimitEntry(service="openai", rpm=60, tpm=100000, source="config")


@dataclass
class APIIDEntry:
    """A class representing an API ID entry.

    >>> id_entry = APIIDEntry.example()
    >>> id_entry.service
    'bedrock'
    >>> id_entry.name
    'AWS_ACCESS_KEY_ID'
    >>> id_entry.value
    'AKIA1234'
    >>> id_entry.source
    'env'
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
    """A class representing input configuration for a language model service.

    >>> lm_input = LanguageModelInput.example()
    >>> lm_input.api_token
    'sk-abcd123'
    >>> lm_input.rpm
    60
    >>> lm_input.tpm
    100000
    >>> lm_input.api_id


    Test dictionary conversion:
    >>> d = lm_input.to_dict()
    >>> isinstance(d, dict)
    True
    >>> LanguageModelInput.from_dict(d).api_token == lm_input.api_token
    True
    """

    api_token: str
    rpm: int
    tpm: int
    api_id: Optional[str] = None
    token_source: Optional[str] = None
    limit_source: Optional[str] = None
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
