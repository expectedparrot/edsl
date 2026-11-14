"""Live-example checks must detect broken histories, not merely count rows."""

from copy import deepcopy

import pytest

from edsl import Model, Results
from edsl.runner import Runner
from examples.shared_state_advanced_acceptance import (
    binding,
    build_case,
    check_case,
    save_transcript,
)


@pytest.mark.parametrize(
    "name,response",
    [
        ("message_board", "A picnic sounds good."),
        ("repeated_matrix", "cooperate"),
        ("work_pool", "Completed the assigned item."),
    ],
)
def test_round_and_claim_checks_detect_corruption(name, response, tmp_path):
    job = build_case(name, Model("test", canned_response=response))
    results = (
        Runner(interview_schedule=job.run_config.parameters.interview_schedule)
        .submit(job, cache=False)
        .results()
    )
    check_case(name, results)
    save_transcript(results, tmp_path)
    transcript = (tmp_path / "transcript.md").read_text()
    assert "round 1:" in transcript
    if name != "work_pool":
        assert "round 2:" in transcript

    altered = Results.from_dict(deepcopy(results.to_dict()))
    state = binding(altered)["exit_snapshots"][0]["state"]["game"]
    if name == "message_board":
        state["messages"][0]["author"] = "wrong participant"
    elif name == "work_pool":
        state["claims"]["Worker B"] = state["claims"]["Worker A"]
    else:
        first = next(e for e in binding(altered)["events"] if e["kind"] == "read")
        first["value"]["rounds"] = {"1": {"0": "defect"}}
    with pytest.raises(AssertionError):
        check_case(name, altered)
