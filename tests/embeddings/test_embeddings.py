from edsl import Dataset, EmbeddingCache, EmbeddingModel, EmbeddingResult, ScenarioList


class PartialEmbeddingService:
    async def async_embed(self, *, model, inputs, parameters):
        return [[1.0], None], None


def test_test_embedding_model_embed_list():
    model = EmbeddingModel("test", service_name="test")

    result = model.embed(["a", "abcd"])

    assert isinstance(result, EmbeddingResult)
    assert result.embeddings == [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
    assert result.model == "test"
    assert result.service_name == "test"
    assert result.dimensions == 3


def test_embedding_cache_reuses_entries():
    model = EmbeddingModel("test", service_name="test")
    cache = EmbeddingCache()

    first = model.embed(["hello"], cache=cache)
    second = model.embed(["hello"], cache=cache)

    assert first.cache_used == [False]
    assert second.cache_used == [True]
    assert first.embeddings == second.embeddings
    assert len(cache) == 1


def test_embedding_cache_jsonl_roundtrip(tmp_path):
    cache_path = tmp_path / "embeddings.jsonl"
    model = EmbeddingModel("test", service_name="test")

    cache = EmbeddingCache(filename=str(cache_path))
    result = model.embed(["hello"], cache=cache)
    reloaded = EmbeddingCache(filename=str(cache_path))
    cached = model.embed(["hello"], cache=reloaded)

    assert cached.cache_used == [True]
    assert cached.embeddings == result.embeddings


def test_embedding_cache_deferred_write_fetches_and_flushes(tmp_path):
    cache_path = tmp_path / "embeddings.jsonl"
    model = EmbeddingModel("test", service_name="test")
    cache = EmbeddingCache(filename=str(cache_path), immediate_write=False)

    result = model.embed(["hello"], cache=cache)
    cached = model.embed(["hello"], cache=cache)

    assert cached.cache_used == [True]
    assert cached.embeddings == result.embeddings
    assert not cache_path.exists()

    cache.flush()
    reloaded = EmbeddingCache(filename=str(cache_path))
    cached_after_reload = model.embed(["hello"], cache=reloaded)

    assert cached_after_reload.cache_used == [True]
    assert cached_after_reload.embeddings == result.embeddings


def test_embedding_model_rejects_missing_embedding(monkeypatch):
    import edsl.embeddings.embedding_model as embedding_model

    monkeypatch.setattr(
        embedding_model,
        "get_embedding_service",
        lambda *args, **kwargs: PartialEmbeddingService(),
    )
    model = EmbeddingModel("test", service_name="test")

    try:
        model.embed(["a", "b"])
    except ValueError as e:
        assert "missing embedding" in str(e)
    else:
        raise AssertionError("Expected missing embedding to raise ValueError")


def test_embedding_result_conversions():
    result = EmbeddingResult(
        embeddings=[[1.0, 2.0]],
        input=["hello"],
        model="test",
        service_name="test",
        dimensions=2,
    )

    dataset = result.to_dataset()
    scenario_list = result.to_scenario_list()

    assert dataset.keys() == [
        "input",
        "embedding",
        "model",
        "service_name",
        "dimensions",
        "cache_key",
        "cache_used",
    ]
    assert scenario_list[0]["embedding"] == [1.0, 2.0]


def test_scenario_list_embed_adds_embedding_field():
    model = EmbeddingModel("test", service_name="test")
    scenario_list = ScenarioList.from_list("text", ["a", "bb"])

    embedded = scenario_list.embed("text", model=model)

    assert embedded[0]["embedding"] == [1.0, 2.0, 3.0]
    assert embedded[1]["embedding"] == [2.0, 3.0, 4.0]


def test_dataset_embed_adds_embedding_column():
    model = EmbeddingModel("test", service_name="test")
    dataset = Dataset([{"text": ["a", "bb"]}])

    embedded = dataset.embed("text", model=model)

    assert embedded.to_scenario_list()[0]["embedding"] == [1.0, 2.0, 3.0]


def test_sentence_transformers_dimensions_guard_does_not_import_dependency():
    model = EmbeddingModel(
        "all-MiniLM-L6-v2", service_name="sentence-transformers", dimensions=10
    )

    try:
        model.embed(["hello"])
    except ValueError as e:
        assert "dimensions" in str(e)
    else:
        raise AssertionError("Expected dimensions guard to raise ValueError")
