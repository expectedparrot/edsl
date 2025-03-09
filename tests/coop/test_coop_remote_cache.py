import datetime
import pytest
import unittest
from unittest.mock import patch, PropertyMock

from edsl.data import Cache
from edsl.coop import Coop
from edsl.surveys import Survey
from edsl.data import CacheEntry
from edsl.questions import QuestionMultipleChoice
from edsl.language_models import LanguageModel

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
    coop.legacy_remote_cache_clear()
    assert coop.legacy_remote_cache_get() == []
    # create one remote cache entry
    cache_entry = CacheEntry.example()
    cache_entry.to_dict()
    # coop.remote_cache_create(cache_entry)
    # create many remote cache entries
    cache_entries = [CacheEntry.example(randomize=True) for _ in range(10)]
    # coop.remote_cache_create_many(cache_entries)
    # get all remote cache entries
    coop.legacy_remote_cache_get()
    coop.legacy_remote_cache_get(exclude_keys=[])
    coop.legacy_remote_cache_get(exclude_keys=["a"])
    exclude_keys = [cache_entry.key for cache_entry in cache_entries]
    coop.legacy_remote_cache_get(exclude_keys)
    # clear
    coop.legacy_remote_cache_clear()
    coop.legacy_remote_cache_get()


@pytest.mark.coop
class TestRemoteCacheWithJobs(unittest.TestCase):

    def setUp(self):

        sky_model = LanguageModel.example(test_model=True, canned_response="blue")
        grass_model = LanguageModel.example(test_model=True, canned_response="green")

        self.sky_model = sky_model
        self.grass_model = grass_model

    @patch(
        "edsl.Coop.edsl_settings",
        new_callable=PropertyMock,
        return_value={
            "remote_caching": True,
            "remote_inference": False,
            "remote_logging": False,
        },
    )
    def test_coop_remote_cache_description(self, mock_edsl_settings):
        return

        def get_descriptions(coop: Coop):
            response = coop._send_server_request(
                uri="api/v0/remote-cache/get-many",
                method="POST",
                payload={"keys": []},
            )
            coop._resolve_server_response(response)
            descriptions = [
                entry.get("description") or "No description provided"
                for entry in response.json()
            ]
            return descriptions

        coop = Coop(api_key="b")
        coop.remote_cache_clear()
        assert coop.remote_cache_get() == []

        # Entry without description
        entry = CacheEntry.example()
        coop.remote_cache_create(entry)
        descriptions = get_descriptions(coop)
        assert descriptions == ["No description provided"]

        # Entries with descriptions
        entry = CacheEntry.example(randomize=True)
        coop.remote_cache_create(entry, description="Example entry")
        coop.remote_cache_create_many(
            example_cache_entries, description="More examples"
        )
        descriptions = get_descriptions(coop)
        assert sorted(descriptions) == [
            "Example entry",
            "More examples",
            "More examples",
            "No description provided",
        ]

        # run a test job
        q_1 = QuestionMultipleChoice(
            question_name="sky_color",
            question_text="What is the color of the sky?",
            question_options=["red", "green", "blue"],
        )
        q_2 = QuestionMultipleChoice(
            question_name="grass_color",
            question_text="What is the color of the grass?",
            question_options=["red", "green", "blue"],
        )

        model = self.sky_model
        survey = Survey(questions=[q_1])
        survey.by(model).run(cache=Cache(), remote_cache_description="Example survey")

        model = self.grass_model
        survey = Survey(questions=[q_2])
        survey.by(model).run(cache=Cache(), remote_cache_description="Example survey")

        descriptions = get_descriptions(coop)
        assert sorted(descriptions) == [
            "Example entry",
            "Example survey",
            "Example survey",
            "More examples",
            "More examples",
            "No description provided",
        ]

    @patch(
        "edsl.Coop.edsl_settings",
        new_callable=PropertyMock,
        return_value={
            "remote_caching": False,
            "remote_inference": False,
            "remote_logging": False,
        },
    )
    def test_coop_no_remote_cache_with_jobs(self, mock_edsl_settings):
        return
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
        q_2 = QuestionMultipleChoice(
            question_name="grass_color",
            question_text="What is the color of the grass?",
            question_options=["red", "green", "blue"],
        )
        model = self.sky_model
        survey = Survey(questions=[q_1])
        survey.by(model).run(cache=local_cache)

        model = self.grass_model
        survey = Survey(questions=[q_2])
        survey.by(model).run(cache=local_cache)

        # Local cache should not have synced with remote cache
        remote_cache_keys = [entry.key for entry in coop.remote_cache_get()]
        local_cache_keys = local_cache.keys()
        assert len(remote_cache_keys) == 1
        assert len(local_cache_keys) == 4

    @patch(
        "edsl.Coop.edsl_settings",
        new_callable=PropertyMock,
        return_value={
            "remote_caching": True,
            "remote_inference": False,
            "remote_logging": False,
        },
    )
    def test_coop_remote_cache_with_jobs(self, mock_edsl_settings):
        return
        coop = Coop(api_key="b")
        coop.remote_cache_clear_log()
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
        model = self.sky_model
        q_1.by(model).run(cache=local_cache)

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
        model = self.grass_model
        q_2.by(model).run(cache=local_cache)

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


if __name__ == "__main__":
    unittest.main()
