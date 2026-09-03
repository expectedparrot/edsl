from edsl.causal import CausalExperimentRunner
from edsl.conversations import SQLiteConversationStore
from examples.automated_social_science.mug_causal_spec import build_compiled_mug_experiment


def test_scripted_mug_runner_preserves_privacy_stops_and_measures(tmp_path):
    compiled, conversation = build_compiled_mug_experiment()
    replication = compiled.replications[0]
    seen = {}

    def buyer(request):
        seen["buyer"] = request
        return "I offer $5."

    def seller(request):
        seen["seller"] = request
        return "I accept the offer."

    def judge(definition, transcript, question):
        return bool(transcript) and "accept" in transcript[-1]["text"].lower()

    def measure(request):
        return int(any("accept" in item["text"].lower() for item in request.transcript))

    store = SQLiteConversationStore(tmp_path / "mug.sqlite")
    runner = CausalExperimentRunner(compiled, conversation, store, speakers={"buyer": buyer, "seller": seller}, semantic_judge=judge, measurers={"deal_occurred": measure})
    observation = runner.run(replication)
    assert observation.values["deal_occurred"] == 1
    assert observation.transcript_version == 2
    assert set(seen["buyer"].private_context) == {"buyer_budget"}
    assert set(seen["seller"].private_context) == {"seller_attachment"}
    assert "seller_attachment" not in seen["buyer"].private_context
    assert [item["role"] for item in store.transcript(replication.instance_id)] == ["buyer", "seller"]


def test_runner_resumes_completed_transcript_without_duplicate_turns(tmp_path):
    compiled, conversation = build_compiled_mug_experiment()
    replication = compiled.replications[0]
    store = SQLiteConversationStore(tmp_path / "resume.sqlite")
    calls = {"count": 0}
    def speaker(request):
        calls["count"] += 1
        return "Done."
    runner = CausalExperimentRunner(compiled, conversation, store, speakers={"buyer": speaker, "seller": speaker}, semantic_judge=lambda definition, transcript, question: len(transcript) >= 1, measurers={"deal_occurred": lambda request: 0})
    first = runner.run(replication)
    second = runner.run(replication)
    assert first == second
    assert calls["count"] == 1
