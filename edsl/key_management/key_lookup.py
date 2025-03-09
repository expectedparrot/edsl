from collections import UserDict
from dataclasses import asdict

from edsl.enums import service_to_api_keyname

from .models import LanguageModelInput


class KeyLookup(UserDict):
    """A class for looking up API keys and related configuration.

    >>> from edsl.language_models.key_management.models import LanguageModelInput
    >>> lookup = KeyLookup()
    >>> lm_input = LanguageModelInput.example()
    >>> lookup['test'] = lm_input
    >>> lookup.to_dict()['test']['api_token']
    'sk-abcd123'
    >>> restored = KeyLookup.from_dict(lookup.to_dict())
    >>> restored['test'].api_token
    'sk-abcd123'
    """

    def to_dict(self):
        """
        >>> kl = KeyLookup.example()
        >>> kl2 = KeyLookup.from_dict(kl.to_dict())
        >>> kl2 == kl
        True
        >>> kl2 is kl
        False
        """
        return {k: asdict(v) for k, v in self.data.items()}

    @classmethod
    def from_dict(cls, d):
        return cls({k: LanguageModelInput(**v) for k, v in d.items()})

    @classmethod
    def example(cls):
        return cls(
            {
                "test": LanguageModelInput.example(),
                "openai": LanguageModelInput.example(),
            }
        )

    def to_dot_env(self):
        """Return a string representation of the key lookup collection for a .env file."""
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
