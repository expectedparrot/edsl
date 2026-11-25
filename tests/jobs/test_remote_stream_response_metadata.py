from types import SimpleNamespace

from edsl.jobs.remote_inference import JobsRemoteInferenceHandler
from edsl import QuestionFreeText
from edsl.surveys import Survey


class _Logger:
    def __init__(self):
        self.jobs_info = SimpleNamespace(results_url=None, results_uuid=None)

    def update(self, *args, **kwargs):
        pass

    def add_info(self, *args, **kwargs):
        pass


def test_streamed_results_preserve_response_metadata_for_retried_answers(monkeypatch):
    class _Coop:
        def __init__(self, api_key=None):
            pass

        def remote_inference_results_manifest(self, job_uuid):
            return {"total_interviews": 1, "page_count": 1, "page_size": 100}

        def remote_inference_results_page(self, job_uuid, page, page_size):
            return {
                "interviews": [
                    {
                        "agent": {},
                        "scenario": {},
                        "model": {},
                        "iteration": 0,
                        "answers": [
                            {
                                "question_name": "q",
                                "answer": "answer",
                                "cached": True,
                                "raw_model_response": {
                                    "choices": [
                                        {
                                            "finish_reason": "stop",
                                            "message": {"content": "answer"},
                                        }
                                    ],
                                    "usage": {"prompt_tokens": 4, "completion_tokens": 2},
                                },
                                "response_metadata": {
                                    "retry_count": 1,
                                    "provider_calls_attempted": 2,
                                    "failure": {"code": "TIMEOUT"},
                                    "attempts": [{"number": 1}, {"number": 2}],
                                },
                            }
                        ],
                    }
                ]
            }

    monkeypatch.setattr("edsl.coop.Coop", _Coop)
    handler = JobsRemoteInferenceHandler.__new__(JobsRemoteInferenceHandler)
    handler.api_key = None
    handler.jobs = SimpleNamespace(
        survey=Survey([QuestionFreeText(question_name="q", question_text="Question?")])
    )
    handler._log_results_metadata = lambda *args, **kwargs: None
    info = SimpleNamespace(job_uuid="job-1", logger=_Logger())
    remote_data = {
        "status": "completed",
        "latest_job_run_details": {
            "interview_details": {
                "total_interviews": 1,
                "completed_interviews": 1,
                "interviews_with_exceptions": 0,
            },
            "cost_usd": 0,
        },
    }

    results = handler._fetch_results_streamed(
        info, "completed", remote_data
    )

    metadata_map = results.data[0].to_dict()["raw_model_response"]
    assert "q_response_metadata" in metadata_map, metadata_map
    metadata = metadata_map["q_response_metadata"]
    assert metadata["retry_count"] == 1
    assert metadata["provider_calls_attempted"] == 2
    assert metadata["failure"] == {"code": "TIMEOUT"}
    assert len(metadata["attempts"]) == 2
