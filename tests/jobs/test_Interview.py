import asyncio
import pytest
from typing import Any
from edsl import Survey
from edsl.config import CONFIG
from edsl.enums import InferenceServiceType
from edsl.language_models.LanguageModel import LanguageModel
from edsl.questions import QuestionFreeText


def create_language_model(
    exception: Exception, fail_at_number: int, never_ending=False
):
    class TestLanguageModel(LanguageModel):
        _model_ = "test"
        _parameters_ = {"temperature": 0.5}
        _inference_service_ = InferenceServiceType.TEST.value

        async def async_execute_model_call(
            self, user_prompt: str, system_prompt: str
        ) -> dict[str, Any]:
            question_number = int(
                user_prompt.split("XX")[1]
            )  ## grabs the question number from the prompt
            await asyncio.sleep(0.1)
            if never_ending:  ## you're not going anywhere buddy
                await asyncio.sleep(float("inf"))
            if question_number == fail_at_number:
                if asyncio.iscoroutinefunction(exception):
                    await exception()
                else:
                    raise exception
            return {"message": """{"answer": "SPAM!"}"""}

        def parse_response(self, raw_response: dict[str, Any]) -> str:
            return raw_response["message"]

    return TestLanguageModel


@pytest.fixture
def create_survey():
    def _create_survey(num_questions: int, chained: bool = True, take_scenario = False):
        survey = Survey()
        for i in range(num_questions):
            if take_scenario:
                q = QuestionFreeText(question_text = f"XX{i}XX and {{scenario_value }}", question_name = f"question_{i}")                     
            else:
                q = QuestionFreeText(
                    question_text=f"XX{i}XX", question_name=f"question_{i}"
                )
            survey.add_question(q)
            if i > 0 and chained:
                survey.add_targeted_memory(f"question_{i}", f"question_{i-1}")
        return survey

    return _create_survey

def test_order(create_survey):
    survey = create_survey(5, chained=False, take_scenario=True)
    from edsl import ScenarioList
    import random
    scenario_values =  ["a", "b", "c", "d", "e"]
    random.shuffle(scenario_values)
    sl = ScenarioList.from_list("scenario_value", scenario_values)
    model = create_language_model(ValueError, 100)()
    jobs = survey.by(model).by(sl)
    results = jobs.run()
    for result, interview in zip(results, jobs.interviews()):
        assert result.interview_hash == hash(interview)

def test_token_usage(create_survey):
    model = create_language_model(ValueError, 100)()
    survey = create_survey(num_questions=5, chained=False)
    jobs = survey.by(model)
    from edsl.data.Cache import Cache

    cache = Cache()
    results = jobs.run(cache=cache)
    token_usage = jobs.interviews()[0].token_usage

    # from edsl.jobs.tokens.TokenUsage import TokenUsage
    # from edsl.jobs.tokens.TokenPricing import TokenPricing
    # from edsl.jobs.tokens.InterviewTokensUsage import InterviewTokenUsage

    assert token_usage.new_token_usage.prompt_tokens == 0
    assert token_usage.new_token_usage.completion_tokens == 0
    assert token_usage.cached_token_usage.completion_tokens == 0
    assert token_usage.cached_token_usage.prompt_tokens == 0


def test_task_management(create_survey):
    model = create_language_model(ValueError, 100)()
    survey = create_survey(num_questions=5, chained=False)
    jobs = survey.by(model)
    from edsl.data.Cache import Cache

    cache = Cache()
    results = jobs.run(cache=cache)

    from edsl.jobs.interviews.InterviewStatusDictionary import InterviewStatusDictionary

    interview_status = jobs.interviews()[0].interview_status
    assert isinstance(interview_status, InterviewStatusDictionary)
    assert list(interview_status.values())[0] == 0


def test_bucket_collection(create_survey):
    model = create_language_model(ValueError, 100)()
    survey = create_survey(num_questions=5, chained=False)
    jobs = survey.by(model)
    from edsl.data.Cache import Cache

    cache = Cache()

    results = jobs.run(cache=cache)

    bc = jobs.bucket_collection
    bucket_list = list(bc.values())

    bucket_list[0].requests_bucket.bucket_type == "requests"


@pytest.mark.parametrize("fail_at_number, chained", [(6, False), (10, True)])
def test_handle_model_exceptions(create_survey, fail_at_number, chained):
    model = create_language_model(ValueError, fail_at_number)()
    survey = create_survey(num_questions=20, chained=chained)
    jobs = survey.by(model)
    from edsl.data.Cache import Cache

    cache = Cache()

    results = jobs.run(cache=cache)

    if not chained:
        assert results.select(f"answer.question_{fail_at_number}").first() is None
        assert (
            results.select(f"answer.question_{fail_at_number + 1}").first() == "SPAM!"
        )
    else:
        assert results[0]["answer"][f"question_{fail_at_number}"] is None
        assert results[0]["answer"][f"question_{fail_at_number + 1}"] is None


def test_handle_timeout_exception(create_survey, capsys):
    ## TODO: We want to shrink the API_TIMEOUT_SEC param for testing purposes.
    model = create_language_model(ValueError, 3, never_ending=True)()
    survey = create_survey(num_questions=5, chained=False)
    from edsl.data.Cache import Cache

    cache = Cache()
    results = survey.by(model).run(cache=cache)
    captured = capsys.readouterr()
    # assert (
    #     "WARNING: At least one question in the survey was not answered." in captured.out
    # )
    # assert "Task `question_0` failed with `InterviewTimeoutError" in captured.out


if __name__ == "__main__":
    pytest.main()
