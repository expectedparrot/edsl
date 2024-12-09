import pytest
from edsl import Model


def test_basic_operation():
    # from edsl.language_models.KeyLookup import KeyLookup

    from edsl.language_models.ServiceDataSources import KeyLookup, LanguageModelInput

    kl = KeyLookup({"openai": LanguageModelInput(api_token="poop", rpm=None, tpm=None)})
    kl2 = KeyLookup(
        {"openai": LanguageModelInput(api_token="poop2", rpm=None, tpm=None)}
    )

    # kl = KeyLookup.from_os_environ()
    # kl = KeyLookup({"OPENAI_API_KEY": "poop"})
    m = Model(key_lookup=kl)
    assert m.api_token == "poop"
    m.set_key_lookup(kl2)
    assert not hasattr(m, "_api_token")
    assert m.api_token == "poop2"
    # assert m.key_lookup == kl
