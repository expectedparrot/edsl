import datetime
import pytest
from edsl import Cache, Coop
from edsl.data import CacheEntry
from edsl.questions import QuestionMultipleChoice

example_cache_entries = [
    CacheEntry(
        model="gpt-4o",
        parameters={"temperature": 0.5},
        system_prompt=f"The quick brown fox jumps over the lazy dog.",
        user_prompt="What does the fox say?",
        output="The fox says 'hello'",
        iteration=1,
        timestamp=int(datetime.datetime.now(datetime.timezone.utc).timestamp()),
    ),
    CacheEntry(
        model="gpt-4-1106-preview",
        parameters={"temperature": 0.5},
        system_prompt=f"The quick brown fox jumps over the lazy dog.",
        user_prompt="What does the fox say?",
        output="The fox says 'hello'",
        iteration=1,
        timestamp=int(datetime.datetime.now(datetime.timezone.utc).timestamp()),
    ),
]


@pytest.mark.coop
def test_coop_remote_cache():
    coop = Coop(api_key="b")
    coop.remote_cache_clear()
    assert coop.remote_cache_get() == []
    # create one remote cache entry
    cache_entry = CacheEntry.example()
    cache_entry.to_dict()
    coop.remote_cache_create(cache_entry)
    # create many remote cache entries
    cache_entries = [CacheEntry.example(randomize=True) for _ in range(10)]
    coop.remote_cache_create_many(cache_entries)
    # get all remote cache entries
    coop.remote_cache_get()
    coop.remote_cache_get(exclude_keys=[])
    coop.remote_cache_get(exclude_keys=["a"])
    exclude_keys = [cache_entry.key for cache_entry in cache_entries]
    coop.remote_cache_get(exclude_keys)
    # clear
    coop.remote_cache_clear()
    coop.remote_cache_get()


@pytest.mark.coop
def test_coop_remote_cache_with_jobs():
    import asyncio
    import json
    from typing import Any
    from edsl.enums import InferenceServiceType
    from edsl.language_models.LanguageModel import LanguageModel

    class CacheTestLanguageModel(LanguageModel):
        use_cache = False
        _model_ = "cache-test-model"
        _parameters_ = {"temperature": 0.5}
        _inference_service_ = InferenceServiceType.TEST.value

        async def async_execute_model_call(
            self, user_prompt: str, system_prompt: str
        ) -> dict[str, Any]:
            await asyncio.sleep(0.1)
            if "What is the color of the sky?" in user_prompt:
                return {"message": """{"answer": "blue"}"""}
            else:
                return {"message": """{"answer": "green"}"""}

        def parse_response(self, raw_response: dict[str, Any]) -> str:
            answer = json.loads(raw_response["message"]).get("answer")
            return answer

    coop = Coop(api_key="b")
    coop.remote_cache_clear()
    assert coop.remote_cache_get() == []

    # create one remote cache entry
    cache_entry = CacheEntry.example()
    coop.remote_cache_create(cache_entry)
    remote_cache_keys = [entry.key for entry in coop.remote_cache_get()]
    expected_remote_cache_keys = [cache_entry.key]
    assert remote_cache_keys == expected_remote_cache_keys

    # create two local cache entries
    local_cache = Cache()
    cache_entry_dict = {c.key: c for c in example_cache_entries}
    local_cache.add_from_dict(cache_entry_dict)
    expected_local_cache_keys = [entry.key for entry in example_cache_entries]
    assert sorted(local_cache.keys()) == sorted(expected_local_cache_keys)

    # run a test job
    q_1 = QuestionMultipleChoice(
        question_name="sky_color",
        question_text="What is the color of the sky?",
        question_options=["red", "green", "blue"],
    )
    m = CacheTestLanguageModel()
    q_1.by(m).run(cache=local_cache, remote_cache=True)

    # Local cache should have synced with remote cache
    remote_cache_keys = [entry.key for entry in coop.remote_cache_get()]
    local_cache_keys = local_cache.keys()
    assert len(remote_cache_keys) == 4
    assert len(local_cache_keys) == 4
    assert sorted(remote_cache_keys) == sorted(local_cache_keys)

    q_2 = QuestionMultipleChoice(
        question_name="grass_color",
        question_text="What is the color of the grass?",
        question_options=["red", "green", "blue"],
    )
    q_2.by(m).run(cache=local_cache, remote_cache=True)

    # Local cache should have synced with remote cache
    remote_cache_keys = [entry.key for entry in coop.remote_cache_get()]
    local_cache_keys = local_cache.keys()
    assert len(remote_cache_keys) == 5
    assert len(local_cache_keys) == 5
    assert sorted(remote_cache_keys) == sorted(local_cache_keys)

    # This entry already exists with the same hash params - shouldn't affect cache
    cache_entry = CacheEntry.example()
    coop.remote_cache_create(cache_entry)
    remote_cache_keys = [entry.key for entry in coop.remote_cache_get()]
    assert len(remote_cache_keys) == 5
    assert sorted(remote_cache_keys) == sorted(local_cache_keys)
