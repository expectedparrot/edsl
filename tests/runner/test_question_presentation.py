"""Historical choices must survive execution, storage, and Results export."""

from copy import deepcopy
from datetime import datetime
import json

import pytest

from edsl import Cache, Model, QuestionMultipleChoice, Results
from edsl.runner import Runner
from edsl.runner.models import Answer
from edsl.runner.presentation import capture_presentation
from edsl.runner.service import JobService
from edsl.runner.storage import InMemoryStorage
from examples.pairwise_comparisons import build_survey, demo_agents


def presentation(row, name="preference"):
    return row.data["question_to_attributes"][name].get("presentation")


@pytest.mark.parametrize("direct", [True, False])
def test_pairwise_choices_and_read_versions_survive_rebuild_and_export(
    direct, tmp_path
):
    survey, _, schedule = build_survey(budget=3)
    observed, prompts = {}, []
    agents = demo_agents(4, observed_options=observed)
    if not direct:
        for agent in agents:
            agent.remove_direct_question_answering_method()
        # Exercise normal prompt rendering, queue transport, and model execution.
        survey.questions[1].use_code = True

    def first_option(user_prompt, system_prompt, files_list):
        prompts.append(user_prompt)
        return "0"

    storage = InMemoryStorage()
    runner = Runner(storage=storage, interview_schedule=schedule)
    handle = runner.submit(
        survey.by(agents).by(Model("test", func=first_option)), cache=False
    )
    results = handle.results()
    assert not results.has_unfixed_exceptions
    events = results.shared_state["bindings"][0]["events"]
    reads = {e["read_id"]: e for e in events if e["kind"] == "read"}
    assert len(prompts) == (0 if direct else 3)
    answered = [r for r in results if r.answer["preference"] is not None]
    assert len(answered) == 3
    for index, row in enumerate(answered):
        captured = presentation(row)
        assert captured["source"] == ("agent_direct" if direct else "prompt")
        assert captured["version"] == 1
        assert len(captured["shared_state_reads"]) == 1
        ref = captured["shared_state_reads"][0]
        event = reads[ref["read_id"]]
        assert event["version"] == ref["version"] == 2 * index + 1
        options = row.get_question_options("preference")
        assert options == event["value"]["options"]
        if direct:
            assert options == observed[row.agent.traits["respondent_id"]]
        else:
            assert row.answer["preference"] == options[0]
            assert prompts[index].index(options[0]) < prompts[index].index(options[1])
        assert presentation(row, "pairwise_gate") is None  # Computation, not a prompt.
    assert answered[0].get_question_options("preference") != answered[
        1
    ].get_question_options("preference")
    assert presentation(results[-1]) is None  # Never asked after budget exhaustion.

    # Rebuild with a fresh service after discarding the volatile answer copies.
    for key in storage.scan_keys_persistent(
        f"job:{handle.job_id}:interview:*:answer:*"
    ):
        storage.delete_volatile(key)
    rebuilt = JobService(storage).build_edsl_results(handle.job_id)
    path = tmp_path / "pairwise.ep"
    results.git.save(path)
    for restored in (
        rebuilt,
        Results.from_dict(json.loads(json.dumps(results.to_dict()))),
        Results.git.load(path),
    ):
        assert [r.data["question_to_attributes"] for r in restored] == [
            r.data["question_to_attributes"] for r in results
        ]


@pytest.mark.parametrize("batch", [False, True])
def test_completion_persists_detached_snapshot_and_legacy_answers_still_work(batch):
    storage = InMemoryStorage()
    service = JobService(storage)
    question = QuestionMultipleChoice(
        question_name="pick", question_text="Pick?", question_options=["old", "choices"]
    )
    job_id, _, _ = service.submit_job(question.by(Model("test")))
    interview_id = service.jobs.get_definition(job_id).interview_ids[0]
    task_id = service.interviews.get_definition(job_id, interview_id).task_ids[0]
    snapshot = capture_presentation(
        {"question_options": ["shown", "choices"]}, source="prompt"
    )
    args = dict(
        interview_id=interview_id,
        task_id=task_id,
        answer_value="shown",
        question_presentation=snapshot,
    )
    if batch:
        service.on_tasks_completed_batch(job_id, [args])
    else:
        service.on_task_completed(job_id, **args)
    snapshot["attributes"]["question_options"].clear()
    result = service.build_edsl_results(job_id)[0]
    assert result.get_question_options("pick") == ["shown", "choices"]
    result.get_question_options("pick").clear()
    assert service.build_edsl_results(job_id)[0].get_question_options("pick") == [
        "shown",
        "choices",
    ]

    # An older stored answer lacks the new field; use the original fallback.
    key = f"job:{job_id}:interview:{interview_id}:answer:pick"
    legacy = deepcopy(storage.read_persistent(key))
    del legacy["question_presentation"]
    storage.delete_persistent(key)
    storage.write_persistent(key, legacy)
    storage.delete_volatile(key)
    restored = JobService(storage).build_edsl_results(job_id)[0]
    assert restored.get_question_options("pick") == ["old", "choices"]
    assert presentation(restored, "pick") is None


def test_snapshot_whitelist_and_answer_serialization_are_detached():
    question = {
        "question_options": ["A", "B"],
        "question_items": ["row"],
        "option_labels": {1: "yes"},
        "private_state": {"secret": True},
    }
    snapshot = capture_presentation(
        question, source="prompt", read_versions=(("read", 2),)
    )
    original = deepcopy(snapshot)
    question["question_options"].reverse()
    assert snapshot == original and "private_state" not in snapshot["attributes"]
    answer = Answer(
        "job", "interview", "pick", "A", datetime.now(), question_presentation=snapshot
    )
    encoded = answer.to_dict()
    restored = Answer.from_dict("job", "interview", "pick", encoded)
    encoded["question_presentation"]["attributes"]["question_options"].clear()
    assert answer.question_presentation == restored.question_presentation == original
    answer.question_presentation = None
    assert "question_presentation" not in answer.to_dict()


def test_model_cache_hit_keeps_this_runs_read_reference():
    calls = []

    def first_option(user_prompt, system_prompt, files_list):
        calls.append(user_prompt)
        return "0"

    cache, runs = Cache(), []
    for _ in range(2):
        # Identical displayed question, independent state and read event.
        survey, _, schedule = build_survey(budget=1)
        survey.questions[1].use_code = True
        agents = demo_agents(1)
        agents[0].remove_direct_question_answering_method()
        results = (
            Runner(interview_schedule=schedule)
            .submit(survey.by(agents).by(Model("test", func=first_option)), cache=cache)
            .results()
        )
        assert not results.has_unfixed_exceptions
        runs.append(results)
    assert len(calls) == 1
    assert runs[1][0]["cache_used_dict"]["preference"] is True
    first, second = [presentation(r[0])["shared_state_reads"][0] for r in runs]
    assert first["read_id"] != second["read_id"]
    assert first["version"] == second["version"] == 1
    assert any(
        e.get("read_id") == second["read_id"]
        for e in runs[1].shared_state["bindings"][0]["events"]
    )
