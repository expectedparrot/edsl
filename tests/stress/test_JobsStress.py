from edsl.agents import Agent
from edsl.data import CRUD
from edsl.jobs import Jobs
from edsl.questions import QuestionFreeText
from edsl.scenarios import Scenario
from edsl.surveys import Survey


def test_jobs_stress(model_with_cache_fixture):
    NUM_AGENTS = 100
    NUM_SCENARIOS = 100
    CRUD.clear_LLMOutputData()
    m = model_with_cache_fixture(
        crud=CRUD,
        use_cache=True,
        model="fake model",
        parameters={"temperature": 0.5},
    )
    q = QuestionFreeText(
        question_text="How are you?",
        question_name="how_feeling",
    )
    job = Jobs(
        survey=Survey(name="Test Survey", questions=[q]),
        agents=[Agent(traits={"trait1": f"value{x}"}) for x in range(NUM_AGENTS)],
        models=[m],
        scenarios=[Scenario({"price": x, "quantity": 2}) for x in range(NUM_SCENARIOS)],
    )
    results = job.run()
    cached_results = CRUD.get_all_LLMOutputData()
    assert len(cached_results) == NUM_AGENTS * NUM_SCENARIOS
    assert len(results) == NUM_AGENTS * NUM_SCENARIOS
