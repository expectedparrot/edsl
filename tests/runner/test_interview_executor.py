import asyncio
from datetime import datetime
from types import SimpleNamespace

from edsl.agents import Agent
from edsl.agents.agent_invigilator import AgentInvigilator
from edsl.base.data_transfer_models import EDSLResultObjectInput
from edsl.caching import Cache
from edsl.inference_services.services.test_service import TestService
from edsl.key_management import KeyLookup
from edsl.questions import QuestionFreeText, QuestionInterview
from edsl.runner.executor import ExecutionWorker
from edsl.runner.models import Answer
from edsl.runner.service import JobService
from edsl.runner.storage import InMemoryStorage
from edsl.surveys import Survey


def _build_test_model():
    return TestService.create_model("test")(
        skip_api_key_check=True,
        func=lambda user_prompt, system_prompt, files_list: "done",
    )


def test_interview_executor_uses_job_context_and_reports_invigilator_failure(
    monkeypatch,
):
    prior_question = QuestionFreeText(
        question_name="warmup",
        question_text="What should the interview remember?",
    )
    interview_question = QuestionInterview(
        question_name="interview",
        question_text="Interview the respondent.",
        interview_guide="Use the prior survey context.",
        max_turns=1,
    )
    survey = Survey([prior_question, interview_question]).add_targeted_memory(
        "interview", "warmup"
    )
    key_lookup = KeyLookup.example()
    job = survey.to_jobs().by(Agent()).by(_build_test_model()).using_key_lookup(
        key_lookup
    )

    service = JobService(InMemoryStorage())
    job_id, _, _ = service.submit_job(job, job_id="job")
    job_definition = service.jobs.get_definition(job_id)
    interview_id = job_definition.interview_ids[0]
    interview_definition = service.interviews.get_definition(job_id, interview_id)
    task_definition = next(
        service.tasks.get_definition(job_id, interview_id, task_id)
        for task_id in interview_definition.task_ids
        if service.tasks.get_definition(job_id, interview_id, task_id).question_name
        == "interview"
    )
    service.answers.store(
        Answer(
            job_id=job_id,
            interview_id=interview_id,
            question_name="warmup",
            answer="The respondent prefers concise answers.",
            created_at=datetime.now(),
        )
    )

    captured = {}

    class DummyInvigilator:
        async def async_answer_question(self):
            return EDSLResultObjectInput(
                generated_tokens="{}",
                question_name="interview",
                prompts={},
                cached_response=None,
                raw_model_response=None,
                cache_used=False,
                cache_key=None,
                answer=None,
                comment="failed",
                exception_occurred=RuntimeError("interview failed"),
            )

    def fake_create_invigilator(self, **kwargs):
        captured.update(kwargs)
        return DummyInvigilator()

    monkeypatch.setattr(
        AgentInvigilator, "create_invigilator", fake_create_invigilator
    )

    worker = ExecutionWorker(
        coordinator=None,
        job_service=service,
    )
    task = SimpleNamespace(
        task_id=task_definition.task_id,
        job_id=job_id,
        interview_id=interview_id,
        question_id=task_definition.question_id,
        question_name=task_definition.question_name,
        iteration=task_definition.iteration,
    )

    result = asyncio.run(
        worker._execute_via_invigilator(
            task,
            service.get_model_for_task(job_id, task_definition.model_id),
            Cache(),
        )
    )

    assert captured["key_lookup"] is key_lookup
    assert [q.question_name for q in captured["survey"].questions] == [
        "warmup",
        "interview",
    ]
    assert list(captured["memory_plan"]["interview"]) == ["warmup"]
    assert captured["current_answers"] == {
        "warmup": "The respondent prefers concise answers."
    }
    assert result.success is False
    assert result.error_type == "unknown"
    assert result.error_message == "interview failed"
