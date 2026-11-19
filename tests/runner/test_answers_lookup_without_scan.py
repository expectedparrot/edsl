"""AnswerStore.get_all_for_interview must not scan the keyspace.

It runs for every task the worker renders and validates. The old version found
an interview's answers with SCAN MATCH job:X:interview:Y:answer:*, which walks
every key in Redis; with millions of leaked keys that pinned prod Redis at 100%
CPU and froze jobs. It now builds the answer keys from the job's question names
and reads them in one batch.
"""

from edsl import Agent, QuestionFreeText, QuestionMultipleChoice, Scenario, Survey
from edsl.inference_services.services.test_service import TestService
from edsl.runner.service import JobService
from edsl.runner.storage import InMemoryStorage
from edsl.runner.stores import AnswerStore


class CountingStorage(InMemoryStorage):
    def __init__(self):
        super().__init__()
        self.scans = 0

    def scan_keys_volatile(self, pattern):
        self.scans += 1
        return super().scan_keys_volatile(pattern)


def _submit(storage, job_id="job"):
    survey = Survey(
        [
            QuestionFreeText(question_name="pick", question_text="Name a {{ scenario.topic }}."),
            QuestionFreeText(question_name="why", question_text="Why {{ pick.answer }}?"),
            QuestionMultipleChoice(
                question_name="like",
                question_text="Do you like {{ pick.answer }}?",
                question_options=["yes", "no"],
            ),
        ]
    )
    model = TestService.create_model("test")(skip_api_key_check=True)
    job = survey.by(Scenario({"topic": "fruit"})).by(Agent()).by(model)
    service = JobService(storage)
    job_id, _, _ = service.submit_job(job, job_id=job_id)
    interview_id = service.jobs.get_definition(job_id).interview_ids[0]
    tasks = {
        service.tasks.get_definition(job_id, interview_id, tid).question_name: tid
        for tid in service.interviews.get_definition(job_id, interview_id).task_ids
    }
    return service, job_id, interview_id, tasks


def _answers(store, job_id, interview_id):
    return {
        a.question_name: a.answer
        for a in store.get_all_for_interview(job_id, interview_id)
    }


def test_returns_only_answered_questions_without_scanning():
    storage = CountingStorage()
    service, job_id, interview_id, tasks = _submit(storage)
    store = AnswerStore(storage)

    assert _answers(store, job_id, interview_id) == {}

    service.on_task_completed(job_id, interview_id, tasks["pick"], answer_value="apple")
    assert _answers(store, job_id, interview_id) == {"pick": "apple"}

    service.on_task_completed(job_id, interview_id, tasks["like"], answer_value="yes")
    assert _answers(store, job_id, interview_id) == {"pick": "apple", "like": "yes"}

    assert storage.scans == 0


def test_matches_the_scan_it_replaces():
    storage = CountingStorage()
    service, job_id, interview_id, tasks = _submit(storage)
    for name, value in [("pick", "apple"), ("why", "crunchy"), ("like", "no")]:
        service.on_task_completed(job_id, interview_id, tasks[name], answer_value=value)

    store = AnswerStore(storage)
    direct = _answers(store, job_id, interview_id)
    by_scan = {
        a.question_name: a.answer
        for a in store._get_all_for_interview_by_scan(job_id, interview_id)
    }
    assert direct == by_scan == {"pick": "apple", "why": "crunchy", "like": "no"}


def test_falls_back_to_scan_when_job_definition_is_missing():
    storage = CountingStorage()
    service, job_id, interview_id, tasks = _submit(storage)
    service.on_task_completed(job_id, interview_id, tasks["pick"], answer_value="apple")
    storage.delete_persistent(f"job:{job_id}:meta")

    store = AnswerStore(storage)
    assert _answers(store, job_id, interview_id) == {"pick": "apple"}
    assert storage.scans == 1


def test_question_names_cache_is_bounded():
    storage = InMemoryStorage()
    store = AnswerStore(storage)
    store._QUESTION_NAMES_CACHE_SIZE = 2
    ids = []
    for n in range(4):
        _, job_id, interview_id, _ = _submit(storage, job_id=f"job{n}")
        ids.append(job_id)
        store.get_all_for_interview(job_id, interview_id)

    assert list(store._question_names) == ids[-2:]
