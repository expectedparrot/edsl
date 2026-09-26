"""Definition reuse must preserve validation, isolation, and execution behavior."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from unittest.mock import patch

import pytest

from edsl import Model, QuestionFreeText, Survey
from edsl.runner import Runner
from edsl.runner.survey_cache import SurveyCache
from edsl.sharedstate import (
    ExecutionLimits,
    ResourceLimitError,
    UnsupportedCapabilityError,
)
from edsl.sharedstate.dsl_runtime import Runtime
from examples.question_coverage import build_survey, demo_agents


def payload():
    survey, _, _ = build_survey(question_ids=["q1", "q2"], target=2, per_agent=1)
    return survey.to_dict()


def machine_data(data):
    return data["state_steps"]["reads"]["coverage_slot_1"][0]["definition"]["machines"][
        "coverage"
    ]


def machine(survey):
    return survey._state_reads["coverage_slot_1"][0].definition.machines["coverage"]


def test_cached_template_and_input_are_isolated_from_caller_mutations():
    data, cache = payload(), SurveyCache()
    original = deepcopy(data)
    first = cache.get(data)
    first.questions[1].answer = 5
    first.questions[1].question_options.reverse()
    first.add_skip_rule("q1", "True")
    machine(first).constants["questions"] = ("injected",)
    machine(first).fields["counts"].initial["q1"] = 99
    assert data == original
    assert cache.get(data).to_dict() == original

    # In-memory storage can return mutable dictionaries; the template must not
    # retain their nested containers, even when the old definition is read later.
    machine_data(data)["constants"]["questions"].append("changed_input")
    assert cache.get(original).to_dict() == original


def test_changed_payload_rebuilds_and_revalidates_instead_of_reusing_old_rules():
    cache, data = SurveyCache(), payload()
    cache.get(data)
    changed = Survey.from_dict(data)
    changed.questions[1].question_text = "An updated question?"
    changed.add_skip_rule("q1", "True")
    assert (
        cache.get(changed.to_dict()).to_dict()
        == Survey.from_dict(changed.to_dict()).to_dict()
    )
    assert cache.get(data).to_dict() == data


@pytest.mark.parametrize(
    "bad_change", ["boolean_integer", "integer_map_key", "version"]
)
def test_invalid_replacement_does_not_hit_valid_template_or_poison_it(bad_change):
    data, cache = payload(), SurveyCache()
    for group in data["state_steps"].values():
        for steps in group.values():
            for step in steps:
                step["definition"]["machines"]["coverage"]["constants"]["lookup"] = {
                    "1": "value"
                }
    cache.get(data)
    bad = deepcopy(data)
    spec = machine_data(bad)
    if bad_change == "boolean_integer":
        spec["fields"]["counts"]["initial"]["q1"] = True
    elif bad_change == "integer_map_key":
        # JSON hashing alone would confuse this with the valid string-key map.
        spec["constants"]["lookup"] = {1: "value"}
    else:
        spec["version"] = 999
    with pytest.raises((ValueError, TypeError)) as expected:
        Survey.from_dict(deepcopy(bad))
    with patch.object(Survey, "from_dict", wraps=Survey.from_dict) as decode:
        for _ in range(2):
            with pytest.raises(type(expected.value)):
                cache.get(bad)
        assert decode.call_count == 2  # Failed definitions are never published.
        assert cache.get(data).to_dict() == data
        assert decode.call_count == 2


def test_concurrent_reads_decode_once_and_return_independent_copies():
    data, cache = payload(), SurveyCache()
    with patch.object(Survey, "from_dict", wraps=Survey.from_dict) as decode:
        with ThreadPoolExecutor(max_workers=8) as pool:
            surveys = list(pool.map(lambda _: cache.get(deepcopy(data)), range(16)))
        assert decode.call_count == 1
    assert len({id(s) for s in surveys}) == 16
    for index, survey in enumerate(surveys):
        survey.questions[1].answer = index
    assert [s.questions[1].answer for s in surveys] == list(range(16))
    assert all(s.to_dict() == data for s in surveys)


def test_cache_evicts_least_recently_used_definition():
    cache = SurveyCache(max_entries=2)
    data = [
        Survey(
            [QuestionFreeText(question_name="reply", question_text=f"Question {i}?")]
        ).to_dict()
        for i in range(3)
    ]
    with patch.object(Survey, "from_dict", wraps=Survey.from_dict) as decode:
        for index in [0, 1, 0, 2, 0]:
            cache.get(data[index])
        assert decode.call_count == 3
        cache.get(data[1])
        assert decode.call_count == 4


def test_cached_machine_still_obeys_destination_capabilities_and_runtime_limits():
    data, cache = payload(), SurveyCache()
    cache.get(data)
    spec = machine(cache.get(data))
    supported = set(Runtime().capability_manifest()["supported"])
    restricted = Runtime(capabilities=supported - {"effect:put@1"})
    with pytest.raises(UnsupportedCapabilityError):
        restricted.initial_state(spec)
    with pytest.raises(ResourceLimitError):
        Runtime(limits=ExecutionLimits(max_steps=1)).initial_state(spec)


def test_coverage_runner_decodes_once_and_keeps_interview_views_separate():
    survey, _, schedule = build_survey(question_ids=["q1", "q2"], target=1, per_agent=1)
    with patch.object(Survey, "from_dict", wraps=Survey.from_dict) as decode:
        results = (
            Runner(interview_schedule=schedule)
            .submit(survey.by(demo_agents(3)).by(Model("test")), cache=False)
            .results()
        )
        assert decode.call_count == 1
    assert not results.has_unfixed_exceptions
    rows = {r.agent.traits["respondent_id"]: r.answer for r in results}
    assert rows["R0"]["coverage_slot_1"] == "q1"
    assert rows["R1"]["coverage_slot_1"] == "q2"
    assert rows["R0"]["q1"] == rows["R1"]["q2"] == 3
    assert rows["R0"].get("q2") is None and rows["R1"].get("q1") is None
    assert all(rows["R2"].get(q) is None for q in ("q1", "q2"))
