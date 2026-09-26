import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from edsl import (
    Agent,
    Model,
    QuestionBudget,
    QuestionCompute,
    QuestionFreeText,
    QuestionFunctional,
    Results,
    Scenario,
    Survey,
)
from edsl.interviews.answering_function import AnswerQuestionFunctionConstructor
from edsl.interviews.interview import Interview
from edsl.questions.exceptions import QuestionAnswerValidationError
from edsl.inference_services.services.test_service import TestService
from edsl.runner.models import InterviewState, TaskStatus
from edsl.runner.runner import Runner
from edsl.runner.service import JobService
from edsl.runner.storage import InMemoryStorage


def _functional_answer(scenario, agent_traits):
    return 1


def test_validation_error_before_response_uses_no_response_failure_result():
    question = QuestionFunctional(
        question_name="functional",
        func=_functional_answer,
        unsafe=True,
    )
    interview = Interview(
        agent=Agent(),
        survey=Survey([question]),
        scenario=Scenario(),
        model=Model("test"),
        raise_validation_errors=False,
    )
    interview.skip_flags = {}
    error = QuestionAnswerValidationError(
        message="invalid functional answer",
        data={"answer": None},
        model=Mock(model_json_schema=Mock(return_value={})),
        pydantic_error=Mock(),
    )
    failed_result = object()
    invigilator = SimpleNamespace(
        question=question,
        async_answer_question=AsyncMock(side_effect=error),
        get_failed_task_result=Mock(return_value=failed_result),
    )
    constructor = AnswerQuestionFunctionConstructor(interview, key_lookup=None)
    constructor.invigilator_fetcher = Mock(return_value=invigilator)

    result = asyncio.run(
        constructor.answer_question_and_record_task(question=question)
    )

    assert result is failed_result
    invigilator.get_failed_task_result.assert_called_once_with(
        failure_reason="Question answer validation failed."
    )
    assert len(interview.exceptions[question.question_name]) == 1
    assert interview.exceptions[question.question_name][0].exception is error


def test_validation_failure_preserves_response_and_task_history(tmp_path):
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

    package_path = tmp_path / "validation-failure-results.ep"
    results.git.save(package_path)
    package_round_tripped = Results.git.load(package_path)
    assert package_round_tripped.has_unfixed_exceptions
    assert len(package_round_tripped.task_history.exceptions) == 1
    assert package_round_tripped[0]["generated_tokens"] == result["generated_tokens"]
    assert package_round_tripped[0]["raw_model_response"] == result[
        "raw_model_response"
    ]
    assert package_round_tripped[0]["validated_dict"]["budget_validated"] is False


def test_completed_task_without_stored_answer_is_reported_as_failure():
    question = QuestionFreeText(question_name="response", question_text="Respond?")
    job = question.by(Model("test"))
    storage = InMemoryStorage()
    service = JobService(storage)
    job_id, _, _ = service.submit_job(job, job_id="job")
    interview_id = service.jobs.get_definition(job_id).interview_ids[0]
    interview = service.interviews.get_definition(job_id, interview_id)
    task_id = interview.task_ids[0]

    service.on_task_completed(job_id, interview_id, task_id, "present")
    answer_key = f"job:{job_id}:interview:{interview_id}:answer:response"
    storage.delete_volatile(answer_key)
    storage.delete_persistent(answer_key)

    results = service.build_edsl_results(job_id)

    assert results[0].answer["response"] is None
    assert results.has_unfixed_exceptions
    exception = results.task_history.to_dict()["interviews"][0]["exceptions"][
        "response"
    ][0]["exception"]
    assert exception["type"] == "MissingCompletedTaskAnswerError"
    assert task_id in exception["message"]


def test_skipped_task_without_stored_answer_is_not_reported_as_failure():
    question = QuestionFreeText(question_name="response", question_text="Respond?")
    job = question.by(Model("test"))
    storage = InMemoryStorage()
    service = JobService(storage)
    job_id, _, _ = service.submit_job(job, job_id="job")
    interview_id = service.jobs.get_definition(job_id).interview_ids[0]
    interview = service.interviews.get_definition(job_id, interview_id)

    service.on_task_skipped(job_id, interview_id, interview.task_ids[0])
    results = service.build_edsl_results(job_id)

    assert results[0].answer["response"] is None
    assert not results.has_unfixed_exceptions


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
