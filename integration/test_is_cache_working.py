import pytest
from edsl.caching import Cache
from edsl import QuestionFreeText

cache = Cache()


def test_cache_working():
    # empty cache so should not be cached
    results = QuestionFreeText.example().run(cache=cache)
    assert not results.select("raw_model_response.*").first()["cached_response"]
    # using same cache; should be cached
    results = QuestionFreeText.example().run(cache=cache)
    assert results.select("raw_model_response.*").first()["cached_response"]
