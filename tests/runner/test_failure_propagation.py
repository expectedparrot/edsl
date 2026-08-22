from edsl import (
    Agent,
    Model,
    QuestionBudget,
    QuestionCompute,
    QuestionFreeText,
    Results,
    Survey,
)
from edsl.inference_services.services.test_service import TestService
from edsl.runner.models import InterviewState, TaskStatus
from edsl.runner.runner import Runner
from edsl.runner.service import JobService
from edsl.runner.storage import InMemoryStorage


def test_validation_failure_preserves_response_and_task_history():
    question = QuestionBudget(
        question_name="budget",
        question_text="Allocate the budget.",
        question_options=["item", "other_or_unspent"],
        budget_sum=100,
    )

    job = question.by(Model("test", canned_response="[60,30]"))
    results = Runner().submit(job, cache=False).results()

    result = results[0]
    assert result.answer["budget"] is None
    assert result["generated_tokens"]["budget_generated_tokens"] == "[60,30]"
    assert result["raw_model_response"]["budget_raw_model_response"] is not None
    assert result["prompt"]["budget_user_prompt"].text
    assert result["validated_dict"]["budget_validated"] is False
    assert results.has_unfixed_exceptions
    history_dict = results.task_history.to_dict()
    response_context = history_dict["interviews"][0]["exceptions"]["budget"][0][
        "additional_data"
    ]["response_context"]
    assert response_context["generated_tokens"] == "[60,30]"
    assert response_context["raw_model_response"] is not None

    round_tripped = Results.from_dict(results.to_dict())
    assert round_tripped[0]["generated_tokens"] == result["generated_tokens"]
    assert round_tripped[0]["raw_model_response"] == result["raw_model_response"]
    assert round_tripped.has_unfixed_exceptions


def test_failure_propagation_blocks_converging_dag_nodes_once():
    root = QuestionFreeText(question_name="root", question_text="Root?")
    left = QuestionCompute(question_name="left", question_text="{{ root.answer }}")
    right = QuestionCompute(
        question_name="right", question_text="{{ root.answer }}"
    )
    join = QuestionCompute(
        question_name="join",
        question_text="{{ left.answer }} {{ right.answer }}",
    )
    survey = Survey([root, left, right, join])
    model = TestService.create_model("test")(skip_api_key_check=True)
    job = survey.to_jobs().by(Agent()).by(model)

    service = JobService(InMemoryStorage())
    job_id, _, _ = service.submit_job(job, job_id="job")
    interview_id = service.jobs.get_definition(job_id).interview_ids[0]
    interview = service.interviews.get_definition(job_id, interview_id)
    tasks = {
        service.tasks.get_definition(job_id, interview_id, task_id).question_name:
        service.tasks.get_definition(job_id, interview_id, task_id)
        for task_id in interview.task_ids
    }

    service.on_task_failed(
        job_id,
        interview_id,
        tasks["root"].task_id,
        "test_failure",
        "boom",
        force_permanent=True,
    )

    status = service.interviews.get_status(interview_id)
    assert status.failed == 1
    assert status.blocked == 3
    assert service.interviews.get_state(interview_id) == (
        InterviewState.COMPLETED_WITH_FAILURES
    )
    assert service.tasks.get_statuses_batch(
        [tasks[name].task_id for name in ("left", "right", "join")]
    ) == {
        tasks["left"].task_id: TaskStatus.BLOCKED,
        tasks["right"].task_id: TaskStatus.BLOCKED,
        tasks["join"].task_id: TaskStatus.BLOCKED,
    }


def test_separate_failures_do_not_recount_shared_blocked_descendants():
    left = QuestionFreeText(question_name="left", question_text="Left?")
    right = QuestionFreeText(question_name="right", question_text="Right?")
    join = QuestionCompute(
        question_name="join",
        question_text="{{ left.answer }} {{ right.answer }}",
    )
    leaf = QuestionCompute(question_name="leaf", question_text="{{ join.answer }}")
    survey = Survey([left, right, join, leaf])
    model = TestService.create_model("test")(skip_api_key_check=True)
    job = survey.to_jobs().by(Agent()).by(model)

    service = JobService(InMemoryStorage())
    job_id, _, _ = service.submit_job(job, job_id="job")
    interview_id = service.jobs.get_definition(job_id).interview_ids[0]
    interview = service.interviews.get_definition(job_id, interview_id)
    tasks = {
        service.tasks.get_definition(job_id, interview_id, task_id).question_name:
        service.tasks.get_definition(job_id, interview_id, task_id)
        for task_id in interview.task_ids
    }

    for question_name in ("left", "right"):
        service.on_task_failed(
            job_id,
            interview_id,
            tasks[question_name].task_id,
            "test_failure",
            "boom",
            force_permanent=True,
        )

    status = service.interviews.get_status(interview_id)
    assert status.failed == 2
    assert status.blocked == 2
    assert status.finished_count == interview.total_tasks
    assert service.interviews.get_state(interview_id) == (
        InterviewState.COMPLETED_WITH_FAILURES
    )
    assert service.tasks.get_statuses_batch(
        [tasks[name].task_id for name in ("join", "leaf")]
    ) == {
        tasks["join"].task_id: TaskStatus.BLOCKED,
        tasks["leaf"].task_id: TaskStatus.BLOCKED,
    }
