import pytest
import uuid
from edsl.coop.coop import Coop
from edsl.questions import QuestionMultipleChoice, QuestionCheckBox, QuestionFreeText
from edsl.surveys import Survey
from edsl.agents import Agent, AgentList
from edsl.results import Results


# NOTE:
# - The coop server must be running in the background.
# - Go to coop and run `make fresh-db && make launch` to start the server.
# - The api_key is drawn from pytest.ini
# - You have to use the client to delete all objects at the start and end of the test.
# TODO:
# - make the above better


@pytest.mark.coop
def test_coop_client_questions():
    """
    Test the Coop client questions functions.
    """
    coop = Coop()
    assert coop.api_key == "b"
    # make sure we start fresh
    for question in coop.questions:
        coop.delete("question", question.get("uuid"))
    assert coop.questions == []
    # cannot get an object that does not exist
    with pytest.raises(Exception):
        coop.get(object_type="question", uuid=uuid.uuid4())
    # create
    question_examples = [
        (QuestionMultipleChoice.example(), True),
        (QuestionCheckBox.example(), False),
        (QuestionFreeText.example(), True),
    ]
    # ..test creation and retrieval
    responses = []
    for question, public in question_examples:
        response = coop.create(question, public=public)
        assert response.get("type") == "question", "Expected type 'question'"
        assert (
            coop.get(object_type="question", uuid=response.get("uuid")) == question
        ), "Question retrieval mismatch"
        responses.append(response)
    # ..check length
    assert len(coop.questions) == 3
    # other client..
    coop2 = Coop(api_key="a")
    # ..should be able to get public but not private questions
    for i, response in enumerate(responses):
        question, public = question_examples[i]
        if public:
            assert (
                coop2.get(object_type="question", uuid=response.get("uuid")) == question
            )
        else:
            with pytest.raises(Exception):
                coop2.get(object_type="question", uuid=response.get("uuid"))
    # ..should not be able to delete another client's questions
    for response in responses:
        with pytest.raises(Exception):
            coop2.delete("question", response.get("uuid"))
    # cleanup
    for question in coop.questions:
        x = coop.delete("question", question.get("uuid"))
        assert x.get("status") == "success"
    assert coop.questions == []


@pytest.mark.coop
def test_coop_client_surveys():
    """
    Test the Coop client survey functions.
    """
    coop = Coop()
    assert coop.api_key == "b"
    # make sure we start fresh
    for survey in coop.surveys:
        coop.delete("survey", survey.get("uuid"))
    assert coop.surveys == []
    # cannot get an object that does not exist
    with pytest.raises(Exception):
        coop.get(object_type="survey", uuid=uuid.uuid4())
    # create
    survey_examples = [
        (Survey.example(), True),
        (Survey.example(), False),
        (Survey.example(), True),
    ]
    # ..test creation and retrieval
    responses = []
    for survey, public in survey_examples:
        response = coop.create(survey, public=public)
        assert response.get("type") == "survey", "Expected type 'survey'"
        assert coop.get(object_type="survey", uuid=response.get("uuid")) == survey
        responses.append(response)
    # ..can't create an empty survey
    with pytest.raises(Exception):
        response = coop.create(Survey(), public=True)
    # ..check length
    assert len(coop.surveys) == 3
    # other client..
    coop2 = Coop(api_key="a")
    # ..should be able to get public but not private surveys
    for i, response in enumerate(responses):
        survey, public = survey_examples[i]
        if public:
            assert coop2.get(object_type="survey", uuid=response.get("uuid")) == survey
        else:
            with pytest.raises(Exception):
                coop2.get(object_type="survey", uuid=response.get("uuid"))
    # ..should not be able to delete another client's surveys
    for response in responses:
        with pytest.raises(Exception):
            coop2.delete("survey", response.get("uuid"))
    # cleanup
    for survey in coop.surveys:
        x = coop.delete("survey", survey.get("uuid"))
        assert x.get("status") == "success"


@pytest.mark.coop
def test_coop_client_agents():
    """
    Test the Coop client agent functions.
    """
    coop = Coop()
    assert coop.api_key == "b"
    # make sure we start fresh
    for agent in coop.agents:
        coop.delete("agent", agent.get("uuid"))
    assert coop.agents == []
    # cannot get an object that does not exist
    with pytest.raises(Exception):
        coop.get(object_type="agent", uuid=uuid.uuid4())
    # create
    agent_examples = [
        (Agent.example(), True),
        (Agent.example(), False),
        (Agent.example(), True),
    ]
    # ..test creation and retrieval
    responses = []
    for agent, public in agent_examples:
        response = coop.create(agent, public=public)
        assert response.get("type") == "agent", "Expected type 'agent'"
        assert coop.get(object_type="agent", uuid=response.get("uuid")) == agent
        responses.append(response)
    # ..check length
    assert len(coop.agents) == 3
    # other client..
    coop2 = Coop(api_key="a")
    # ..should be able to get public but not private agents
    for i, response in enumerate(responses):
        agent, public = agent_examples[i]
        if public:
            assert coop2.get(object_type="agent", uuid=response.get("uuid")) == agent
        else:
            with pytest.raises(Exception):
                coop2.get(object_type="agent", uuid=response.get("uuid"))
    # ..should not be able to delete another client's agents
    for response in responses:
        with pytest.raises(Exception):
            coop2.delete("agent", response.get("uuid"))
    # cleanup
    for agent in coop.agents:
        x = coop.delete("agent", agent.get("uuid"))
        assert x.get("status") == "success"


@pytest.mark.coop
def test_coop_client_results():
    """
    Test the Coop client results functions.
    """
    coop = Coop()
    assert coop.api_key == "b"
    # make sure we start fresh
    for results in coop.results:
        coop.delete("results", results.get("uuid"))
    assert coop.results == []
    # cannot get an object that does not exist
    with pytest.raises(Exception):
        coop.get(object_type="results", uuid=uuid.uuid4())
    # create
    results_examples = [
        (Results.example(), True),
        (Results.example(), False),
        (Results.example(), True),
    ]
    # ..test creation and retrieval
    responses = []
    for results, public in results_examples:
        response = coop.create(results, public=public)
        assert response.get("type") == "results", "Expected type 'results'"
        assert coop.get(object_type="results", uuid=response.get("uuid")) == results
        responses.append(response)
    # ..check length
    assert len(coop.results) == 3
    # other client..
    coop2 = Coop(api_key="a")
    # ..should be able to get public but not private results
    for i, response in enumerate(responses):
        results, public = results_examples[i]
        if public:
            assert (
                coop2.get(object_type="results", uuid=response.get("uuid")) == results
            )
        else:
            with pytest.raises(Exception):
                coop2.get(object_type="results", uuid=response.get("uuid"))
    # ..should not be able to delete another client's results
    for response in responses:
        with pytest.raises(Exception):
            coop2.delete("results", response.get("uuid"))
    # cleanup
    for results in coop.results:
        x = coop.delete("results", results.get("uuid"))
        assert x.get("status") == "success"
