from edsl import QuestionFreeText
from edsl.data.Cache import Cache, main


def test_Cache_main():
    main()


def test_caching(language_model_good):
    m = language_model_good
    c = Cache()
    results = QuestionFreeText.example().by(m).run(cache=c)
    assert not results.select(
        "raw_model_response.how_are_you_raw_model_response"
    ).first()["cached_response"]
    results = QuestionFreeText.example().by(m).run(cache=c)
    assert results.select("raw_model_response.how_are_you_raw_model_response").first()[
        "cached_response"
    ]
