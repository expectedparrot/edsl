from edsl.agents import Agent
from edsl.data import CRUD
from edsl.jobs import Jobs
from edsl.questions import QuestionMultipleChoice
from edsl.scenarios import Scenario
from edsl.surveys import Survey


def test_jobs_stress(test_language_model_good_fixture):
    CRUD.clear_LLMOutputData()
    m = test_language_model_good_fixture(
        crud=CRUD,
        use_cache=True,
        model="fake model",
        parameters={"temperature": 0.5},
    )
    q = QuestionMultipleChoice(
        question_text="How are you?",
        question_options=["Good", "Great", "OK", "Bad"],
        question_name="how_feeling",
    )
    job = Jobs(
        survey=Survey(name="Test Survey", questions=[q]),
        agents=[Agent(traits={"trait1": f"value{x}"}) for x in range(100)],
        models=[m],
        scenarios=[Scenario({"price": x, "quantity": 2}) for x in range(100)],
    )
    results = job.run()
    cached_results = CRUD.get_all_LLMOutputData()
    assert len(CRUD.get_all_LLMOutputData()) == 10000
    assert len(results) == 10000
