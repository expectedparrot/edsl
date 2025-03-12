import os
import pytest
from typing import List
from dataclasses import dataclass

from edsl.exceptions.general import MissingAPIKeyError
from edsl.enums import service_to_api_keyname
from edsl.jobs.jobs_checks import JobsChecks


# Test fixtures and helper classes
@dataclass
class MockModel:
    model: str
    has_api_key: bool = True
    _inference_service_: str = "openai"

    def has_valid_api_key(self) -> bool:
        return self.has_api_key


@dataclass
class MockAgent:
    answer_question_directly: bool = False


@dataclass
class MockQuestion:
    question_type: str = "standard"


@dataclass
class MockSurvey:
    questions: List[MockQuestion]


class MockJobs:
    def __init__(
        self,
        models: List[MockModel] = None,
        agents: List[MockAgent] = None,
        questions: List[MockQuestion] = None,
    ):
        self.models = models or []
        self.agents = agents or []
        self.survey = MockSurvey(questions or [])


@pytest.fixture
def clean_env():
    """Remove relevant environment variables before each test"""
    keys_to_remove = ["EXPECTED_PARROT_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"]
    # Store original values
    original_values = {}
    for key in keys_to_remove:
        original_values[key] = os.environ.get(key)
        if key in os.environ:
            del os.environ[key]

    yield

    # Restore original values
    for key, value in original_values.items():
        if value is not None:
            os.environ[key] = value


def test_init():

    jobs = MockJobs()
    checks = JobsChecks(jobs)
    assert checks.jobs == jobs


def test_check_api_keys_success(clean_env):

    os.environ["OPENAI_API_KEY"] = "test_key"

    model = MockModel(model="gpt-4", has_api_key=True)
    jobs = MockJobs(models=[model])
    checks = JobsChecks(jobs)

    # Should not raise an exception
    checks.check_api_keys()


def test_check_api_keys_failure(clean_env):

    model = MockModel(model="gpt-4", has_api_key=False)
    jobs = MockJobs(models=[model])
    checks = JobsChecks(jobs)

    with pytest.raises(MissingAPIKeyError) as exc_info:
        checks.check_api_keys()
    assert str(model.model) in str(exc_info.value)


def test_get_missing_api_keys(clean_env):

    model1 = MockModel(model="gpt-4", has_api_key=False, _inference_service_="openai")
    model2 = MockModel(
        model="claude", has_api_key=False, _inference_service_="anthropic"
    )
    jobs = MockJobs(models=[model1, model2])
    checks = JobsChecks(jobs)

    missing_keys = checks.get_missing_api_keys()
    assert "OPENAI_API_KEY" in missing_keys
    assert "ANTHROPIC_API_KEY" in missing_keys


def test_user_has_ep_api_key(clean_env):

    jobs = MockJobs()
    checks = JobsChecks(jobs)

    assert not checks.user_has_ep_api_key()

    os.environ["EXPECTED_PARROT_API_KEY"] = "test_key"
    assert checks.user_has_ep_api_key()


def test_user_has_all_model_keys(clean_env):

    os.environ["OPENAI_API_KEY"] = "test_key"

    # Test with valid API key
    model = MockModel(model="gpt-4", has_api_key=True)
    jobs = MockJobs(models=[model])
    checks = JobsChecks(jobs)
    assert checks.user_has_all_model_keys()

    # Test with invalid API key
    model = MockModel(model="gpt-4", has_api_key=False)
    jobs = MockJobs(models=[model])
    checks = JobsChecks(jobs)
    assert not checks.user_has_all_model_keys()


def test_needs_external_llms():

    # Test with agents that answer directly
    agents = [MockAgent(answer_question_directly=True)]
    jobs = MockJobs(agents=agents)
    checks = JobsChecks(jobs)
    assert not checks.needs_external_llms()

    # Test with test model
    model = MockModel(model="test")
    jobs = MockJobs(models=[model])
    checks = JobsChecks(jobs)
    assert not checks.needs_external_llms()

    # Test with functional questions
    questions = [MockQuestion(question_type="functional")]
    jobs = MockJobs(questions=questions)
    checks = JobsChecks(jobs)
    assert not checks.needs_external_llms()

    # Test with regular model
    model = MockModel(model="gpt-4")
    jobs = MockJobs(models=[model])
    checks = JobsChecks(jobs)
    assert checks.needs_external_llms()


def test_needs_key_process(clean_env):

    model = MockModel(model="gpt-4", has_api_key=False)
    jobs = MockJobs(models=[model])
    checks = JobsChecks(jobs)

    # Should need key process when no keys are present
    assert checks.needs_key_process()

    # Should not need key process when EP API key is present
    os.environ["EXPECTED_PARROT_API_KEY"] = "test_key"
    assert not checks.needs_key_process()

    # Should not need key process when all model keys are present
    os.environ.pop("EXPECTED_PARROT_API_KEY")
    model = MockModel(model="gpt-4", has_api_key=True)
    jobs = MockJobs(models=[model])
    checks = JobsChecks(jobs)
    try:
        assert not checks.needs_key_process()
    except AssertionError:
        print(checks.status())
        raise


# Note: We're not testing key_process() as it involves external services
# and user interaction. This would typically require integration tests
# or more complex mocking.
