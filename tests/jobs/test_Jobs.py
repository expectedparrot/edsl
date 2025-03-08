import pytest
from edsl.agents import Agent
from edsl.exceptions.jobs import JobsRunError
from edsl.exceptions.agents import AgentCombinationError
from edsl.jobs.interviews.Interview import Interview
from edsl.jobs.Jobs import Jobs, main
from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice
from edsl.questions.QuestionFreeText import QuestionFreeText
from edsl.scenarios import Scenario, ScenarioList
from edsl.surveys import Survey
from edsl.language_models.model import Model
from edsl.questions.question_registry import (
    Question,
)  # needed for the eval() of the repr() of the Job
from edsl.language_models.LanguageModel import LanguageModel
from edsl.data.Cache import Cache

from edsl.agents import AgentList
from edsl.language_models.ModelList import ModelList


@pytest.fixture(scope="function")
def valid_job():
    q = QuestionMultipleChoice(
        question_text="How are you?",
        question_options=["Good", "Great", "OK", "Bad"],
        question_name="how_feeling",
    )
    survey = Survey(questions=[q])
    agent = Agent(traits={"trait1": "value1"})
    # model = LanguageModel.example(test_model=True, canned_response="SPAM!")
    model = Model("test", canned_response="SPAM!")
    scenario = Scenario({"price": 100, "quantity": 2})
    valid_job = Jobs(
        survey=survey,
        agents=[agent],
        models=[model],
        scenarios=[scenario],
    )
    yield valid_job


def test_jobs_simple_stuf(valid_job):
    # simple stuff
    # assert valid_job.survey.name == "Test Survey"
    from edsl.surveys.rules import RuleCollection
    from edsl.surveys.rules import Rule

    assert valid_job.agents[0].traits == {"trait1": "value1"}
    # assert valid_job.models[0].model == "gpt-4-1106-preview"
    assert valid_job.scenarios[0].get("price") == 100
    # eval works and returns eval-able string
    assert "Jobs(survey=Survey(" in repr(valid_job)

    assert isinstance(eval(repr(valid_job)), Jobs)
    # serialization
    assert isinstance(valid_job.to_dict(), dict)

    ## When we have a test_model, we can uncomment this.

    assert isinstance(Jobs.from_dict(valid_job.to_dict()), Jobs)
    assert Jobs.from_dict(valid_job.to_dict()).to_dict() == valid_job.to_dict()
    # serialize and de-serialize an empty job
    empty_job = Jobs(survey=Survey(questions=[valid_job.survey._questions[0]]))
    assert Jobs.from_dict(empty_job.to_dict()).to_dict() == empty_job.to_dict()


def test_jobs_by_agents():
    q = QuestionMultipleChoice(
        question_text="How are you?",
        question_options=["Good", "Great", "OK", "Bad"],
        question_name="how_feeling",
    )
    survey = Survey(name="Test Survey", questions=[q])
    agent1 = Agent(traits={"trait1": "value1"})
    agent2 = Agent(traits={"trait2": "value2"})
    # by without existing agents
    job = survey.by(agent1)
    assert job.agents == AgentList([agent1])
    job = survey.by(agent1, agent2)
    assert job.agents == AgentList([agent1, agent2])
    assert len(job) == 2
    job = survey.by([agent1, agent2])
    assert job.agents == AgentList([agent1, agent2])
    assert len(job) == 2
    job = survey.by((agent1, agent2))
    assert job.agents == AgentList([agent1, agent2])
    assert len(job) == 2
    # by with existing agents
    job = survey.by(agent1).by(agent2)
    assert job.agents == AgentList([agent1 + agent2])
    assert len(job) == 1
    with pytest.raises(AgentCombinationError):
        job = survey.by(agent1).by(agent1)


def test_jobs_by_scenarios():
    q = QuestionMultipleChoice(
        question_text="How are you?",
        question_options=["Good", "Great", "OK", "Bad"],
        question_name="how_feeling",
    )

    survey = Survey(name="Test Survey", questions=[q])
    scenario1 = Scenario({"price": "100"})
    scenario2 = Scenario({"value": "200"})
    scenario3 = Scenario({"price": "200"})
    # by without existing scenarios
    job = survey.by(scenario1)
    assert job.scenarios == ScenarioList([scenario1])
    job = survey.by(scenario1, scenario2)
    assert job.scenarios == ScenarioList([scenario1, scenario2])
    assert len(job) == 2
    job = survey.by([scenario1, scenario2])
    assert job.scenarios == ScenarioList([scenario1, scenario2])
    assert len(job) == 2
    job = survey.by((scenario1, scenario2))
    assert job.scenarios == ScenarioList([scenario1, scenario2])
    assert len(job) == 2
    # by with existing scenarios
    job = survey.by(scenario1).by(scenario2)
    assert job.scenarios == ScenarioList([scenario1 + scenario2])
    assert len(job) == 1
    # if the scenarios have the same keys, new scenarios take precedence
    job = survey.by(scenario1).by(scenario3)
    assert job.scenarios == ScenarioList([scenario3])
    assert len(job) == 1


def test_agent_info():
    agent = Agent(traits={"first_name": "John"})

    q = QuestionFreeText(
        question_text="What is your name, {{ agent.first_name }}?", question_name="name"
    )
    job = q.by(agent)
    assert "John" in job.prompts().select("user_prompt").first().text


def test_jobs_by_models():
    q = QuestionMultipleChoice(
        question_text="How are you?",
        question_options=["Good", "Great", "OK", "Bad"],
        question_name="how_feeling",
    )
    survey = Survey(name="Test Survey", questions=[q])
    from edsl.inference_services.registry import default

    model1 = Model(default.available()[0][0])
    model2 = Model(default.available()[1][0])
    # by without existing models
    job = survey.by(model1)
    assert job.models == ModelList([model1])
    job = survey.by(model1, model2)
    assert job.models == ModelList([model1, model2])
    assert len(job) == 2
    job = survey.by([model1, model2])
    assert job.models == ModelList([model1, model2])
    assert len(job) == 2
    job = survey.by((model1, model2))
    assert job.models == ModelList([model1, model2])
    assert len(job) == 2
    # by with existing models
    job = survey.by(model1).by(model2)
    assert job.models == ModelList([model2])
    assert len(job) == 1


def test_jobs_interviews(valid_job):
    # on a job with existing agents, scenarios, and models
    interviews = valid_job.interviews()
    assert isinstance(interviews[0], Interview)
    assert len(interviews) == 1
    # on a job with no agents, scenarios, or models
    q = QuestionMultipleChoice(
        question_text="How are you?",
        question_options=["Good", "Great", "OK", "Bad"],
        question_name="how_feeling",
    )
    survey = Survey(questions=[q])
    job = Jobs(survey=survey)
    interviews = job.interviews()
    assert interviews[0].survey == survey
    assert interviews[0].scenario == Scenario()
    assert interviews[0].agent == Agent()
    # assert interviews[0].model.model == "test"


def test_jobs_run(valid_job):

    cache = Cache()

    results = valid_job.run(cache=cache, check_api_keys=False)
    # breakpoint()

    assert len(results) == 1
    # with pytest.raises(JobsRunError):
    #    valid_job.run(method="invalid_method")


def test_normal_run():
    from edsl.language_models.LanguageModel import LanguageModel
    from edsl.enums import InferenceServiceType
    import asyncio
    from typing import Any

    # class TestLanguageModelGood(LanguageModel):
    #     _model_ = "test"
    #     _parameters_ = {"temperature": 0.5}
    #     _inference_service_ = InferenceServiceType.TEST.value
    #     key_sequence = ["message", 0, "text"]

    #     async def async_execute_model_call(
    #         self, user_prompt: str, system_prompt: str
    #     ) -> dict[str, Any]:
    #         await asyncio.sleep(0.0)
    #         return {"message": [{"text": "SPAM!"}]}

    #     # def parse_response(self, raw_response: dict[str, Any]) -> str:
    #     #     return raw_response["message"]

    # model = TestLanguageModelGood()
    model = Model("test", canned_response="SPAM!")
    from edsl.questions import QuestionFreeText

    q = QuestionFreeText(question_text="What is your name?", question_name="name")
    from edsl.data.Cache import Cache

    cache = Cache()
    results = q.by(model).run(cache=cache)
    # breakpoint()
    assert results[0]["answer"]["name"] == "SPAM!"


def test_handle_model_exception():
    import random
    from edsl.language_models.LanguageModel import LanguageModel
    from edsl.enums import InferenceServiceType
    import asyncio
    from typing import Any

    from httpcore import ConnectionNotAvailable
    from edsl.questions import QuestionFreeText

    def create_exception_throwing_model(exception: Exception, probability: float):
        class TestLanguageModelGood(LanguageModel):
            _model_ = "test"
            _parameters_ = {"temperature": 0.5}
            _inference_service_ = InferenceServiceType.TEST.value

            async def async_execute_model_call(
                self, user_prompt: str, system_prompt: str
            ) -> dict[str, Any]:
                await asyncio.sleep(0.1)
                if random.random() < probability:
                    raise exception
                return {"message": """{"answer": "SPAM!"}"""}

            def parse_response(self, raw_response: dict[str, Any]) -> str:
                return raw_response["message"]

        return TestLanguageModelGood()

    survey = Survey()
    for i in range(20):
        q = QuestionFreeText(
            question_text=f"How are you?", question_name=f"question_{i}"
        )
        survey.add_question(q)
        if i > 0:
            survey.add_targeted_memory(f"question_{i}", f"question_{i-1}")

    target_exception = ConnectionNotAvailable
    model = create_exception_throwing_model(target_exception, 0.1)
    # So right now, these just fails.
    # What would we want to happen?
    # with pytest.raises(target_exception):
    #    results = survey.by(model).run()


def test_jobs_bucket_creator(valid_job):
    # from edsl.jobs.runners.job_runners_registry import JobsRunnersRegistry
    # JobRunner = JobsRunnersRegistry["asyncio"](jobs=valid_job)
    from edsl.jobs.runners.JobsRunnerAsyncio import JobsRunnerAsyncio

    bc_to_use = valid_job.create_bucket_collection()

    from edsl.jobs.Jobs import RunEnvironment

    re = RunEnvironment()
    re.bucket_collection = bc_to_use

    bc = JobsRunnerAsyncio(jobs=valid_job, environment=re).environment.bucket_collection
    assert bc[valid_job.models[0]].requests_bucket.tokens > 10
    assert bc[valid_job.models[0]].tokens_bucket.tokens > 10


def test_jobs_main():
    main()


if __name__ == "__main__":

    def valid_job():
        q = QuestionMultipleChoice(
            question_text="How are you?",
            question_options=["Good", "Great", "OK", "Bad"],
            question_name="how_feeling",
        )
        survey = Survey(name="Test Survey", questions=[q])
        agent = Agent(traits={"trait1": "value1"})
        model = Model()
        scenario = Scenario({"price": 100, "quantity": 2})
        valid_job = Jobs(
            survey=survey,
            agents=[agent],
            models=[model],
            scenarios=[scenario],
        )
        return valid_job

    test_jobs_run(valid_job())
