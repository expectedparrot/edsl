from edsl import Model
from edsl.causal import CausalExperimentRunner, EDSLCausalAdapter
from edsl.conversations import SQLiteConversationStore
from examples.automated_social_science.mug_causal_spec import build_compiled_mug_experiment


def test_edsl_adapter_runs_normal_pipeline_and_records_provenance(tmp_path, monkeypatch):
    from edsl.object_store.store import ObjectStore
    monkeypatch.setattr(ObjectStore, "default_root", staticmethod(lambda: tmp_path / "objects"))
    compiled, conversation = build_compiled_mug_experiment()
    replication = compiled.replications[0]
    adapter = EDSLCausalAdapter(
        Model("test", canned_response="I propose a price of five dollars."),
        coordinator_model=Model("test", canned_response="Yes"),
        measurement_model=Model("test", canned_response="Yes"),
    )
    runner = CausalExperimentRunner(
        compiled,
        conversation,
        SQLiteConversationStore(tmp_path / "adapter.sqlite"),
        speakers={"buyer": adapter.speak, "seller": adapter.speak},
        semantic_judge=adapter.judge,
        measurers={"deal_occurred": adapter.measure},
    )
    observation = runner.run(replication)
    assert observation.values["deal_occurred"] == 1
    assert observation.transcript_version == 1
    assert [call["kind"] for call in adapter.provenance()] == ["speaker", "semantic_stop", "measurement"]
    speaker_input = adapter.provenance()[0]["input"]
    assert "maximum budget" in speaker_input["prompt"]
    assert "sentimental attachment" not in speaker_input["prompt"]


def test_measurement_coercion_is_strict():
    assert EDSLCausalAdapter._coerce("Yes", "binary", (0, 1)) == 1
    assert EDSLCausalAdapter._coerce("No", "binary", (0, 1)) == 0
    assert EDSLCausalAdapter._coerce("2.5", "continuous", ()) == 2.5
