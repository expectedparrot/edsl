import pytest
import asyncio
import nest_asyncio

from edsl.surveys import Survey
from edsl.questions import QuestionFreeText
from edsl.language_models.utilities import create_language_model
from edsl.scenarios import ScenarioList
from edsl.caching import Cache

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

@pytest.fixture(scope="function")
def event_loop():
    """Create an instance of the default event loop for each test."""
    loop = asyncio.new_event_loop()
    yield loop
    # Cleanup properly after each test
    loop.run_until_complete(asyncio.sleep(0))
    loop.close()


@pytest.fixture
def create_survey():
    def _create_survey(num_questions: int, chained: bool = True, take_scenario=False):
        survey = Survey()
        for i in range(num_questions):
            if take_scenario:
                q = QuestionFreeText(
                    question_text=f"XX{i}XX and {{scenario_value }}",
                    question_name=f"question_{i}",
                )
            else:
                q = QuestionFreeText(
                    question_text=f"XX{i}XX", question_name=f"question_{i}"
                )
            survey.add_question(q)
            if i > 0 and chained:
                survey.add_targeted_memory(f"question_{i}", f"question_{i-1}")
        return survey

    return _create_survey


def test_order(create_survey, event_loop):
    """Test the order of interviews with a clean event loop setup."""
    survey = create_survey(5, chained=False, take_scenario=True)
    import random

    scenario_values = ["a", "b", "c", "d", "e"]
    random.shuffle(scenario_values)
    sl = ScenarioList.from_list("scenario_value", scenario_values)
    
    model = create_language_model(ValueError, 100)()
    jobs = survey.by(model).by(sl)
    
    # Set the event loop to our fresh loop before running
    asyncio.set_event_loop(event_loop)
    
    # Run the jobs
    results = jobs.run()

    hashes = []
    # TODO: Need to fix this
    for result, interview in zip(results, jobs.interviews()):
        hashes.append((interview.initial_hash, result.interview_hash))

    # Something is going wrong here - the hashes are not matching
    # assert result.interview_hash == interview.initial_hash  # hash(interview)


def test_token_usage(create_survey, event_loop):
    model = create_language_model(ValueError, 100)()
    survey = create_survey(num_questions=5, chained=False)
    jobs = survey.by(model)

    # Set the event loop to our fresh loop
    asyncio.set_event_loop(event_loop)
    
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


def test_task_management(create_survey, event_loop):
    model = create_language_model(ValueError, 100)()
    survey = create_survey(num_questions=5, chained=False)
    jobs = survey.by(model)

    # Set the event loop to our fresh loop
    asyncio.set_event_loop(event_loop)
    
    cache = Cache()
    results = jobs.run(cache=cache)

    from edsl.interviews import InterviewStatusDictionary

    interview_status = jobs.interviews()[0].interview_status
    assert isinstance(interview_status, InterviewStatusDictionary)
    assert list(interview_status.values())[0] == 0


def test_bucket_collection(create_survey, event_loop):
    model = create_language_model(ValueError, 100)()
    survey = create_survey(num_questions=5, chained=False)
    jobs = survey.by(model)

    # Set the event loop to our fresh loop
    asyncio.set_event_loop(event_loop)
    
    cache = Cache()
    results = jobs.run(cache=cache)

    bc = jobs.run_config.environment.bucket_collection
    bucket_list = list(bc.values())

    bucket_list[0].requests_bucket.bucket_type == "requests"


@pytest.mark.parametrize("fail_at_number, chained", [(6, False), (10, True)])
def test_handle_model_exceptions(set_env_vars, create_survey, fail_at_number, chained, event_loop):
    "A chained survey is one where each survey question depends on the previous one."
    model = create_language_model(ValueError, fail_at_number)()
    survey = create_survey(num_questions=20, chained=chained)
    jobs = survey.by(model)

    # Set the event loop to our fresh loop
    asyncio.set_event_loop(event_loop)
    
    cache = Cache()
    results = jobs.run(cache=cache, print_exceptions=False)

    print(f"Results: {results}")
    print(
        f"Answer for question_{fail_at_number}: {results.select(f'answer.question_{fail_at_number}').first()}"
    )
    print(
        f"Answer for question_{fail_at_number + 1}: {results.select(f'answer.question_{fail_at_number + 1}').first()}"
    )
    # raise Exception("Stop here")
    if not chained:
        assert results.select(f"answer.question_{fail_at_number}").first() is None
        assert (
            results.select(f"answer.question_{fail_at_number + 1}").first() == "SPAM!"
        )
    else:
        assert results[0]["answer"][f"question_{fail_at_number}"] is None
        assert results[0]["answer"][f"question_{fail_at_number + 1}"] is None


def test_handle_timeout_exception(create_survey, capsys, event_loop):
    ## TODO: We want to shrink the API_TIMEOUT_SEC param for testing purposes.
    model = create_language_model(ValueError, 3, never_ending=True)()
    survey = create_survey(num_questions=5, chained=False)

    # Set the event loop to our fresh loop
    asyncio.set_event_loop(event_loop)
    
    cache = Cache()
    results = survey.by(model).run(cache=cache, print_exceptions=False)
    captured = capsys.readouterr()
    # assert (
    #     "WARNING: At least one question in the survey was not answered." in captured.out
    # )
    # assert "Task `question_0` failed with `InterviewTimeoutError" in captured.out


if __name__ == "__main__":
    pytest.main()
