from edsl.caching import CacheEntry


def test_CacheEntry_equality():
    # timestamp doesn't matter for equality
    entry1 = CacheEntry.example()
    entry2 = CacheEntry.example()
    assert entry1 == entry2
    entry2.timestamp = entry2.timestamp + 1
    assert entry1 == entry2
    # can also compare keys
    assert entry1.key == entry2.key
    # from_dict -> to_dict yields an equal object
    assert entry1 == CacheEntry.from_dict(entry1.to_dict())
    # and repr is evalable
    assert eval(repr(entry1)) == entry1


def test_CacheEntry_example_dict():
    example_dict = CacheEntry.example_dict()
    assert len(example_dict) == 1
    key = list(example_dict.keys())[0]
    assert key == CacheEntry.example().key


def test_CacheEntry_fetch_input_example():
    fetch_input = CacheEntry.fetch_input_example()
    assert "timestamp" not in fetch_input
    assert "output" not in fetch_input
    assert all(field in fetch_input for field in CacheEntry.key_fields)


def test_CacheEntry_store_input_example():
    store_input = CacheEntry.store_input_example()
    assert "timestamp" not in store_input
    assert "response" in store_input
    assert "output" not in store_input
    assert all(field in store_input for field in CacheEntry.key_fields + ["response"])


def test_CacheEntry_gen_key():
    key = CacheEntry.gen_key(
        model="gpt-3.5-turbo",
        parameters="{'temperature': 0.5}",
        system_prompt="The quick brown fox jumps over the lazy dog.",
        user_prompt="What does the fox say?",
        iteration=1,
    )
    assert key == "5ee60636048b05b4f7b6995a0cf9b78e"


def test_CacheEntry_key_property():
    entry = CacheEntry.example()
    assert entry.key == "5513286eb6967abc0511211f0402587d"


def test_CacheEntry_to_dict():
    entry = CacheEntry.example()
    entry_dict = entry.to_dict()
    assert all(field in entry_dict for field in CacheEntry.all_fields)
    assert entry_dict["model"] == entry.model
    assert entry_dict["parameters"] == entry.parameters
    assert entry_dict["system_prompt"] == entry.system_prompt
    assert entry_dict["user_prompt"] == entry.user_prompt
    assert entry_dict["output"] == entry.output
    assert entry_dict["iteration"] == entry.iteration
    assert entry_dict["timestamp"] == entry.timestamp
    assert entry_dict["service"] == entry.service
    assert entry_dict["validated"] == entry.validated


def test_CacheEntry_from_dict():
    entry_dict = CacheEntry.example().to_dict()
    entry = CacheEntry.from_dict(entry_dict)
    assert isinstance(entry, CacheEntry)
    assert all(
        getattr(entry, field) == entry_dict[field] for field in CacheEntry.all_fields
    )


def test_CacheEntry_repr():
    entry = CacheEntry.example()
    expected_repr = f"CacheEntry(model={repr(entry.model)}, parameters={entry.parameters}, system_prompt={repr(entry.system_prompt)}, user_prompt={repr(entry.user_prompt)}, output={repr(entry.output)}, iteration={entry.iteration}, timestamp={entry.timestamp}, service={repr(entry.service)}, validated={entry.validated})"
    assert repr(entry) == expected_repr
