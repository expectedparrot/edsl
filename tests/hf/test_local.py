"""Offline format contract and interoperability with plain datasets."""

import base64
import io
import wave
from pathlib import Path

import pytest

hf = pytest.importorskip("datasets")
pa = pytest.importorskip("pyarrow")
import pyarrow.parquet as pq

from edsl import Agent, AgentList, FileStore, Scenario, ScenarioList
from edsl.hf import HFClassMismatchError, HFFormatVersionError, HFSchemaError
from edsl.hf.card import read_card, write_card


def make_list(cls, rows):
    return cls((Agent(row) if cls is AgentList else Scenario(row)) for row in rows)


@pytest.mark.parametrize("cls", [AgentList, ScenarioList])
@pytest.mark.parametrize(
    "rows",
    [
        [],
        [{}, {}],
        [{"a": None}, {}, {"a": 4}],
        [{"a": [], "b": True}, {"a": [1, None, 3], "b": False}],
        [{"a": {"nested": [1, "é", None]}}, {"a": {}}],
        [{"a": [1, "two"]}, {"a": []}],
        [{"a": 2**60 + 1}, {"a": 2.5}, {"a": 3.0}],
        [{"a": {"__edsl_hf_value__": "filestore", "value": "user data"}}],
    ],
)
def test_roundtrip(cls, rows, tmp_path):
    obj = make_list(cls, rows)
    assert obj.save_hf(tmp_path) == tmp_path
    restored = cls.load_hf(tmp_path)
    assert restored == obj
    actual = [dict(a.traits) if cls is AgentList else dict(a) for a in restored]
    assert actual == rows
    for before, after in zip(rows, actual):
        for key in before:
            assert type(before[key]) is type(after[key])


def test_unusual_keys_and_scenario_names(tmp_path):
    obj = ScenarioList(
        [
            Scenario(
                {"a.b": 1, "with space": "é", "_x": False, "日本語": None}, name="first"
            )
        ]
    )
    obj.save_hf(tmp_path)
    restored = ScenarioList.load_hf(tmp_path)
    assert restored == obj
    assert restored[0].name == "first"
    card, _ = read_card(tmp_path / "README.md")
    assert (
        card["edsl"]["objects"]["scenarios"]["columns"]["a.b"]["original_key"] == "a.b"
    )


@pytest.mark.parametrize("cls", [AgentList, ScenarioList])
def test_empty_parquet_and_hf_streaming(cls, tmp_path):
    cls([]).save_hf(tmp_path)
    shard = next(tmp_path.glob("*/*.parquet"))
    assert pq.read_table(shard).num_rows == 0
    assert (
        list(
            hf.load_dataset(
                str(tmp_path),
                split="train",
                streaming=True,
                cache_dir=str(tmp_path / "cache"),
            )
        )
        == []
    )


@pytest.mark.parametrize("coerce", ["string", "json"])
@pytest.mark.parametrize("cls", [AgentList, ScenarioList])
def test_coercion(cls, coerce, tmp_path):
    values = [30, "unknown", 2.5, True, "True", [1, "x"], {"x": [False]}, None, 2**80]
    obj = make_list(cls, [{"mixed": value} for value in values] + [{}])
    obj.save_hf(tmp_path, coerce=coerce)
    restored = cls.load_hf(tmp_path)
    assert restored == obj
    actual = [a.traits for a in restored] if cls is AgentList else list(restored)
    assert [type(r["mixed"]) for r in actual[:-1]] == [type(v) for v in values]
    table = pq.read_table(next(tmp_path.glob("*/*.parquet"))).to_pylist()
    assert table[0]["mixed"] == "30"
    assert table[1]["mixed"] == ('"unknown"' if coerce == "json" else "unknown")


def test_schema_errors_and_failed_overwrite_preserves_data(tmp_path):
    original = ScenarioList([Scenario({"x": 1})])
    original.save_hf(tmp_path)
    with pytest.raises(HFSchemaError, match="'x'.*row 0.*int.*row 1.*str"):
        ScenarioList([Scenario({"x": 30}), Scenario({"x": "unknown"})]).save_hf(
            tmp_path
        )
    assert ScenarioList.load_hf(tmp_path) == original
    with pytest.raises(HFSchemaError, match="_edsl_"):
        ScenarioList([Scenario({"_edsl_name": "bad"})]).save_hf(tmp_path)
    with pytest.raises(ValueError, match="coerce"):
        original.save_hf(tmp_path, coerce="guess")
    with pytest.raises(HFSchemaError, match="config_name"):
        original.save_hf(tmp_path, config_name="../escape")


def test_other_python_objects(tmp_path):
    value = Path("example.txt")
    obj = ScenarioList([Scenario({"x": value, "nested": {"value": value}})])
    with pytest.raises(HFSchemaError):
        obj.save_hf(tmp_path)
    for coerce in ("string", "json"):
        obj.save_hf(tmp_path, coerce=coerce)
        restored = ScenarioList.load_hf(tmp_path)[0]
        assert restored["x"] == "example.txt"
        assert restored["nested"] == {"value": "example.txt"}


def test_agent_settings_shared_and_varying(tmp_path):
    agents = AgentList(
        [
            Agent(
                {"age": 30},
                name="Alice",
                instruction="Be brief",
                codebook={"age": "Age in years"},
                traits_presentation_template="Age: {{age}}",
                trait_categories={"personal": ["age"]},
            ),
            Agent(
                {"age": 40},
                name="Bob",
                instruction="Explain",
                codebook={"age": "Years old"},
            ),
            Agent({}),
        ]
    )
    agents.save_hf(tmp_path)
    assert AgentList.load_hf(tmp_path) == agents
    table = pq.read_table(next(tmp_path.glob("agents/*.parquet")))
    for name in (
        "instruction",
        "codebook",
        "trait_categories",
        "traits_presentation_template",
    ):
        assert "_edsl_" + name in table.column_names
    shared = AgentList([agents[0], agents[0]])
    shared.save_hf(tmp_path / "shared")
    assert AgentList.load_hf(tmp_path / "shared") == shared
    card, prose = read_card(tmp_path / "shared" / "README.md")
    metadata = card["edsl"]["objects"]["agents"]
    assert metadata["instruction"] == "Be brief"
    assert metadata["trait_categories"] == {"personal": ["age"]}
    assert "| age | Age in years |" in prose


def test_subclasses_and_functions(tmp_path, caplog, monkeypatch):
    from edsl.base import RegisterSubclassesMeta

    # Defining an Agent subclass registers it globally. Keep this test-only
    # class out of subsequent serialization-coverage and registry tests.
    monkeypatch.setattr(
        RegisterSubclassesMeta, "_registry", RegisterSubclassesMeta._registry.copy()
    )
    caplog.set_level("WARNING", logger="edsl.hf.io")

    class ResearchAgent(Agent):
        pass

    agent = ResearchAgent({"x": 1})
    agent.answer_question_directly = lambda **kwargs: "not serialized"
    agent.dynamic_traits_function = lambda: {"x": 2}
    AgentList([agent]).save_hf(tmp_path)
    assert "1 agent(s)" in caplog.text
    restored = AgentList.load_hf(tmp_path)
    assert type(restored[0]) is Agent
    assert restored[0].traits == {"x": 1}
    assert restored[0].dynamic_traits_function is None
    assert not hasattr(restored[0], "answer_question_directly")
    card, _ = read_card(tmp_path / "README.md")
    assert card["edsl"]["objects"]["agents"]["agent_subclasses"] == ["ResearchAgent"]


def test_multiconfig_and_plain_datasets(tmp_path):
    agents = AgentList([Agent({"age": 30})])
    scenarios = ScenarioList([Scenario({"text": "hello"})], codebook={"text": "Prompt"})
    agents.save_hf(tmp_path)
    card, _ = read_card(tmp_path / "README.md")
    card["license"] = "mit"
    write_card(tmp_path / "README.md", card, "\nMy edited prose.\n")
    scenarios.save_hf(tmp_path)
    assert AgentList.load_hf(tmp_path) == agents
    assert ScenarioList.load_hf(tmp_path).codebook == scenarios.codebook
    card, prose = read_card(tmp_path / "README.md")
    assert card["license"] == "mit"
    assert prose == "\nMy edited prose.\n"
    for config, column, expected in [
        ("agents", "age", 30),
        ("scenarios", "text", "hello"),
    ]:
        dataset = hf.load_dataset(
            str(tmp_path), name=config, split="train", cache_dir=str(tmp_path / "cache")
        )
        assert dataset[0][column] == expected


def test_version_class_and_row_count_errors(tmp_path):
    AgentList([Agent({"x": 1})]).save_hf(tmp_path)
    with pytest.raises(HFClassMismatchError, match="AgentList.*ScenarioList"):
        ScenarioList.load_hf(tmp_path)
    with pytest.raises(HFClassMismatchError):
        ScenarioList.load_hf(tmp_path, config_name="agents")
    card, prose = read_card(tmp_path / "README.md")
    card["edsl"]["objects"]["agents"]["n"] = 9
    write_card(tmp_path / "README.md", card, prose)
    with pytest.raises(HFSchemaError, match="declares 9 rows, found 1"):
        AgentList.load_hf(tmp_path)
    card["edsl"]["format_version"] = 999
    write_card(tmp_path / "README.md", card, prose)
    with pytest.raises(HFFormatVersionError, match="Upgrade EDSL"):
        AgentList.load_hf(tmp_path)
    with pytest.raises(HFFormatVersionError):
        AgentList([]).save_hf(tmp_path)


def test_sharding_and_replacement(tmp_path, monkeypatch):
    import edsl.hf.io as hf_io

    monkeypatch.setattr(hf_io, "SHARD_BYTES", 30)
    obj = ScenarioList([Scenario({"text": str(i) * 20}) for i in range(9)])
    obj.save_hf(tmp_path)
    assert len(list(tmp_path.glob("scenarios/*.parquet"))) > 1
    assert [r["text"] for r in ScenarioList.load_hf(tmp_path)] == [
        r["text"] for r in obj
    ]
    ScenarioList([Scenario({"text": "replacement"})]).save_hf(tmp_path)
    assert len(list(tmp_path.glob("scenarios/*.parquet"))) == 1
    assert ScenarioList.load_hf(tmp_path)[0]["text"] == "replacement"


@pytest.fixture
def attachments():
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="
    )
    wav = io.BytesIO()
    with wave.open(wav, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8000)
        stream.writeframes(b"\x00\x00" * 16)
    return [
        FileStore(
            path=f"missing.{suffix}",
            mime_type=mime,
            suffix=suffix,
            binary=True,
            base64_string=base64.b64encode(raw).decode(),
            extracted_text="fixture",
            external_locations={"gcs": {"uri": "gs://not-followed/file"}},
        )
        for suffix, mime, raw in [
            ("png", "image/png", png),
            ("wav", "audio/wav", wav.getvalue()),
            ("pdf", "application/pdf", b"%PDF-1.4\nfixture\n%%EOF"),
        ]
    ]


@pytest.mark.parametrize("cls", [AgentList, ScenarioList])
def test_media_features_and_bytes(cls, attachments, tmp_path):
    image, audio, pdf = attachments
    rows = [
        {"image": image, "audio": audio, "pdf": pdf, "mixed": image},
        {"image": None, "mixed": pdf},
        {},
    ]
    obj = make_list(cls, rows)
    obj.save_hf(tmp_path)
    restored = cls.load_hf(tmp_path)
    assert restored == obj
    actual = restored[0].traits if cls is AgentList else restored[0]
    for key in ("image", "audio", "pdf", "mixed"):
        assert isinstance(actual[key], FileStore)
        assert dict(actual[key]) == dict(rows[0][key])
    dataset = hf.load_dataset(
        str(tmp_path), split="train", cache_dir=str(tmp_path / "cache")
    )
    assert isinstance(dataset.features["image"], hf.Image)
    assert isinstance(dataset.features["audio"], hf.Audio)
    assert dataset.features["audio"].decode is False
    assert isinstance(dataset.features["mixed"], dict)
    dataset = dataset.cast_column("image", hf.Image(decode=False))
    assert dataset[0]["image"]["bytes"] == base64.b64decode(image.base64_string)
    assert dataset[0]["audio"]["bytes"] == base64.b64decode(audio.base64_string)


def test_file_limits_nested_and_collisions(attachments, tmp_path, caplog):
    caplog.set_level("WARNING", logger="edsl.hf.schema")
    image = attachments[0]
    with pytest.raises(HFSchemaError, match="row 0.*max_file_bytes"):
        ScenarioList([Scenario({"file": image})]).save_hf(tmp_path, max_file_bytes=2)
    with pytest.raises(HFSchemaError, match="companion column"):
        ScenarioList([Scenario({"file": image, "file__meta": "user field"})]).save_hf(
            tmp_path
        )
    obj = ScenarioList([Scenario({"nested": {"files": [image]}})])
    obj.save_hf(tmp_path)
    assert "base64 remains inline" in caplog.text
    assert ScenarioList.load_hf(tmp_path) == obj
    restored = ScenarioList.load_hf(tmp_path)[0]["nested"]["files"][0]
    assert isinstance(restored, FileStore)
    assert dict(restored) == dict(image)


def test_loading_files_performs_no_io(attachments, tmp_path, monkeypatch):
    file = attachments[0]
    file.data["path"] = "https://example.invalid/do-not-fetch.png"
    file.data["extracted_text"] = None
    ScenarioList([Scenario({"file": file, "nested": [file]})]).save_hf(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("FileStore constructor must not run on load")

    monkeypatch.setattr(FileStore, "__init__", forbidden)
    result = ScenarioList.load_hf(tmp_path)
    assert dict(result[0]["file"]) == dict(file)
    assert dict(result[0]["nested"][0]) == dict(file)


def test_non_edsl_local_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(
        hf.config,
        "HF_DATASETS_CACHE",
        str(tmp_path.parent / (tmp_path.name + "-cache")),
    )
    pq.write_table(
        pa.table({"text": ["a", "b"], "age": [1, None]}), tmp_path / "train.parquet"
    )
    assert ScenarioList.load_hf(tmp_path)[1] == Scenario({"text": "b", "age": None})
    assert AgentList.load_hf(tmp_path)[0].traits == {"text": "a", "age": 1}


def test_v1_fixture():
    folder = Path(__file__).parent / "fixtures" / "v1"
    agents = AgentList.load_hf(folder)
    assert agents[0].traits == {"age": 30, "note": None}
    assert agents[1].traits == {"age": 41}
    assert agents[0].name == "Alice"
    assert agents[0].codebook == {"age": "Age in years"}
    scenarios = ScenarioList.load_hf(folder)
    assert scenarios[0] == Scenario({"text": "hello", "nested": {"a": [1, "é"]}})
