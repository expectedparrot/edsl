import pytest

from edsl.agents import Agent, AgentList
from edsl.caching import Cache
from edsl.scenarios import Scenario, ScenarioList
from edsl.questions import QuestionCheckBox
from edsl.questions import QuestionFreeText
from edsl.questions import QuestionMultipleChoice
from edsl.notebooks import Notebook
from edsl.results import Results
from edsl.surveys import Survey
from edsl.coop import Coop


def coop_object_api_workflows(object_type, object_examples):
    coop = Coop(api_key="b")

    # 1. Ensure we are starting with a clean state
    objects = coop.get_all(object_type)
    for object in objects:
        coop.delete(object.get("uuid"))
    objects = coop.get_all(object_type)
    assert objects == [], "Expected no objects in the database."

    # 2. Test object creation and retrieval
    responses = []
    for object, visibility in object_examples:
        response = coop.create(object, visibility=visibility)
        assert (
            coop.get(response.get("uuid")) == object
        ), f"Expected object to be the same as the one created. "
        # assert coop.get(response.get("url")) == object
        responses.append(response)

    # 3. Test visibility with different clients
    coop2 = Coop(api_key="a")
    for i, response in enumerate(responses):
        object, visibility = object_examples[i]
        if visibility != "private":
            assert coop2.get(response.get("uuid")) == object
        else:
            with pytest.raises(Exception):
                coop2.get(response.get("uuid"))

    # 4. Test changing visibility
    for i, response in enumerate(responses):
        object, visibility = object_examples[i]
        if visibility == "private":
            change_to_visibility = "public"
        else:
            change_to_visibility = "private"
        response = coop.patch(
            response.get("uuid"),
            visibility=change_to_visibility,
        )
        assert response.get("status") == "success"

    # 5. Cleanup
    for object in coop.get_all(object_type):
        response = coop.delete(object.get("uuid"))
        assert response.get("status") == "success"


@pytest.mark.coop
def test_coop_client_agents():
    agent_examples = [
        (Agent.example(), "public"),
        (Agent.example(), "private"),
        (Agent.example(), "public"),
        (Agent.example(), "unlisted"),
    ]
    coop_object_api_workflows("agent", agent_examples)


@pytest.mark.coop
def test_coop_client_agent_lists():
    agent_list_examples = [
        (AgentList.example(), "public"),
        (AgentList.example(), "private"),
        (AgentList.example(), "public"),
        (AgentList.example(), "unlisted"),
    ]
    coop_object_api_workflows("agent_list", agent_list_examples)


@pytest.mark.coop
def test_coop_client_caches():
    cache_examples = [
        (Cache.example(), "public"),
        (Cache.example(), "private"),
        (Cache.example(), "public"),
        (Cache.example(), "unlisted"),
    ]
    coop_object_api_workflows("cache", cache_examples)


@pytest.mark.coop
def test_coop_client_questions():
    question_examples = [
        (QuestionMultipleChoice.example(), "public"),
        (QuestionCheckBox.example(), "private"),
        (QuestionFreeText.example(), "public"),
        (QuestionFreeText.example(), "unlisted"),
    ]
    coop_object_api_workflows("question", question_examples)


@pytest.mark.coop
def test_coop_client_notebooks():
    notebook_examples = [
        (Notebook.example(), "public"),
        (Notebook.example(), "private"),
        (Notebook.example(), "public"),
        (Notebook.example(), "unlisted"),
    ]
    coop_object_api_workflows("notebook", notebook_examples)


@pytest.mark.coop
def test_coop_client_results():
    results_examples = [
        (Results.example(), "public"),
        (Results.example(), "private"),
        (Results.example(), "public"),
        (Results.example(), "unlisted"),
    ]
    coop_object_api_workflows("results", results_examples)


@pytest.mark.coop
def test_coop_client_scenarios():
    scenario_examples = [
        (Scenario.example(), "public"),
        (Scenario.example(), "private"),
        (Scenario.example(), "public"),
        (Scenario.example(), "unlisted"),
    ]
    coop_object_api_workflows("scenario", scenario_examples)


@pytest.mark.coop
def test_coop_client_scenario_lists():
    scenario_list_examples = [
        (ScenarioList.example(), "public"),
        (ScenarioList.example(), "private"),
        (ScenarioList.example(), "public"),
        (ScenarioList.example(), "unlisted"),
    ]
    coop_object_api_workflows("scenario_list", scenario_list_examples)


@pytest.mark.coop
def test_coop_client_surveys():
    survey_examples = [
        (Survey.example(), "public"),
        (Survey.example(), "private"),
        (Survey.example(), "public"),
        (Survey.example(), "unlisted"),
    ]
    coop_object_api_workflows("survey", survey_examples)
