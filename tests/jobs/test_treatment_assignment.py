import json
import pytest

from edsl import Agent, Jobs, Model, QuestionFreeText, Scenario, ScenarioList, Survey
from edsl.jobs import TreatmentAssignment
from edsl.jobs.exceptions import JobsValueError
from edsl.runner import Runner


def _job():
    return Jobs(
        survey=Survey(
            [
                QuestionFreeText(
                    question_name="response",
                    question_text="Respond to this {{ scenario.condition }} condition.",
                )
            ]
        ),
        agents=[
            Agent(traits={"respondent_id": "r1"}),
            Agent(traits={"respondent_id": "r2"}),
        ],
        scenarios=ScenarioList(
            [Scenario({"condition": "control"}), Scenario({"condition": "treatment"})]
        ),
        models=[Model("test", canned_response="ok")],
    )


def _policy():
    return TreatmentAssignment(
        conditions={"control": 0, "treatment": 1},
        schedule={
            "agent:r1|iteration:0": "control",
            "agent:r1|iteration:1": "treatment",
            "agent:r2|iteration:0": "treatment",
            "agent:r2|iteration:1": "control",
        },
        unit="agent_iteration",
        unit_id_field="respondent_id",
        exposure_questions=("response",),
        balance="exact",
        planned_iterations=2,
    )


def test_treatment_assignment_serializes_and_validates_exact_schedule():
    job = _job().set_treatment_assignment(_policy())
    restored = Jobs.from_dict(json.loads(json.dumps(job.to_dict())))

    assert restored.treatment_assignment.to_dict() == job.treatment_assignment.to_dict()
    assert job.treatment_assignment.condition_counts() == {
        "control": 2,
        "treatment": 2,
    }
    original = job.treatment_assignment.realize(0, job.agents[0], 0, 0)
    round_tripped = restored.treatment_assignment.realize(0, restored.agents[0], 0, 0)
    assert round_tripped == original


def test_treatment_assignment_runs_local_and_records_assignment_and_exposure():
    job = _job().set_treatment_assignment(_policy())
    results = job.run(
        n=2,
        cache=False,
        disable_remote_inference=True,
        disable_remote_cache=True,
        progress_bar=False,
    )

    assert len(results) == 4
    observed = {}
    for result in results:
        respondent_id = result.agent.traits["respondent_id"]
        condition = result.scenario["condition"]
        treatment = result["randomization"]["treatment_assignment"]
        exposure = result["randomization"]["treatment_exposure"]
        observed[(respondent_id, result["iteration"])] = condition
        assert treatment["condition"] == condition
        assert treatment["assignment_unit"] == "agent_iteration"
        assert exposure == {
            "questions": ["response"],
            "exposed_questions": ["response"],
            "exposed": True,
        }
    assert observed == {
        ("r1", 0): "control",
        ("r1", 1): "treatment",
        ("r2", 0): "treatment",
        ("r2", 1): "control",
    }


def test_treatment_assignment_runner_persists_interview_realizations():
    job = _job().set_treatment_assignment(_policy())
    results = Runner().submit(job, n=2, cache=False).results(stop_on_exception=True)

    assert len(results) == 4
    for result in results:
        treatment = result["randomization"]["treatment_assignment"]
        assert treatment["assignment_id"]
        assert treatment["schedule_counts"] == {"control": 2, "treatment": 2}
        assert result["randomization"]["treatment_exposure"]["exposed"] is True


def test_treatment_assignment_humanize_is_rejected_before_scenario_processing():
    from edsl.coop.exceptions import CoopValueError

    job = _job().set_treatment_assignment(_policy())
    job.models = []
    with pytest.raises(CoopValueError, match="does not support treatment assignment"):
        job.humanize()


def test_treatment_assignment_rejects_missing_schedule_units():
    policy = TreatmentAssignment(
        conditions={"control": 0, "treatment": 1},
        schedule={"agent:0": "control"},
    )
    with pytest.raises(JobsValueError, match="does not match Jobs units"):
        _job().set_treatment_assignment(policy)


def test_treatment_assignment_unit_keys_control_model_and_iteration_sharing():
    agent = Agent(traits={"respondent_id": "r1"})
    shared = TreatmentAssignment(
        conditions={"control": 0, "treatment": 1},
        schedule={"agent:r1": "control"},
        unit="agent",
        unit_id_field="respondent_id",
    )
    per_model = TreatmentAssignment(
        conditions={"control": 0, "treatment": 1},
        schedule={
            "agent:r1|model:0": "control",
            "agent:r1|model:1": "treatment",
        },
        unit="agent_model",
        unit_id_field="respondent_id",
    )

    assert shared.unit_key(0, agent, 0, 0) == shared.unit_key(0, agent, 1, 3)
    assert per_model.unit_key(0, agent, 0, 0) != per_model.unit_key(0, agent, 1, 0)


def test_treatment_assignment_rejects_uneven_exact_schedule():
    policy = TreatmentAssignment(
        conditions={"control": 0, "treatment": 1},
        schedule={"agent:0": "control", "agent:1": "control"},
        balance="exact",
    )

    with pytest.raises(
        JobsValueError, match="Exact balance requires equal assignments"
    ):
        _job().set_treatment_assignment(policy)
