import pytest
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
        coop.delete_question(question.get("id"))
    assert coop.questions == []

    # cannot get an object that does not exist
    with pytest.raises(Exception):
        coop.get(object_type="question", id=10000)

    # create
    question_examples = [
        (QuestionMultipleChoice.example(), True),
        (QuestionCheckBox.example(), False),
        (QuestionFreeText.example(), True),
    ]

    # Test creation and retrieval
    for question, public in question_examples:
        response = coop.create(question, public=public)
        assert response.get("type") == "question", "Expected type 'question'"
        assert (
            coop.get(object_type="question", id=response.get("id")) == question
        ), "Question retrieval mismatch"
        assert coop.get(url=response.get("url")) == question, "URL retrieval mismatch"

    # check
    assert len(coop.questions) == 3

    # other client..
    coop2 = Coop(api_key="a")
    # ..should be able to get public but not private questions
    assert coop2.get(object_type="question", id=4) == QuestionFreeText.example()
    with pytest.raises(Exception):
        coop2.get(object_type="question", id=3)
    # ..should not be able to delete another client's questions
    for i in range(2, 5):
        with pytest.raises(Exception):
            coop2.delete_question(i)

    # cleanup
    for question in coop.questions:
        x = coop.delete_question(question.get("id"))
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
        coop.delete_survey(survey.get("id"))
    assert coop.surveys == []

    # cannot get an object that does not exist
    with pytest.raises(Exception):
        coop.get(object_type="survey", id=100)

    # create
    response = coop.create(Survey.example())
    assert response.get("id") == 2
    assert response.get("type") == "survey"
    assert response.get("url") is not None
    response = coop.create(Survey.example(), public=False)
    assert response.get("id") == 3
    assert response.get("type") == "survey"
    assert response.get("url") is not None
    response = coop.create(Survey.example(), public=True)
    assert response.get("id") == 4
    assert response.get("type") == "survey"
    assert response.get("url") is not None
    #  can't create an empty survey
    with pytest.raises(Exception):
        response = coop.create(Survey(), public=True)
    # check
    assert len(coop.surveys) == 3
    assert coop.surveys[0].get("id") == 2
    assert coop.surveys[0].get("survey") == Survey.example()

    # other client..
    coop2 = Coop(api_key="a")
    # ..should be able to get public but not private surveys
    assert coop2.get(object_type="survey", id=4) == Survey.example()
    with pytest.raises(Exception):
        coop2.get(object_type="survey", id=3)
    # ..should not be able to delete another client's surveys
    for i in range(2, 5):
        with pytest.raises(Exception):
            coop2.delete_survey(i)

    # cleanup
    for survey in coop.surveys:
        coop.delete_survey(survey.get("id"))
    assert coop.surveys == []


@pytest.mark.coop
def test_coop_client_agents():
    """
    Test the Coop client agent functions.
    """
    coop = Coop()
    assert coop.api_key == "b"

    # make sure we start fresh
    for agent in coop.agents:
        coop.delete_agent(agent.get("id"))
    assert coop.agents == []

    # cannot get an object that does not exist
    with pytest.raises(Exception):
        coop.get(object_type="agent", id=100)

    # create
    response = coop.create(Agent.example())
    assert response.get("id") == 2
    assert response.get("type") == "agent"
    assert response.get("url") is not None
    response = coop.create(Agent.example(), public=False)
    assert response.get("id") == 3
    assert response.get("type") == "agent"
    assert response.get("url") is not None
    response = coop.create(Agent.example(), public=True)
    assert response.get("id") == 4
    assert response.get("type") == "agent"
    assert response.get("url") is not None

    # check
    assert len(coop.agents) == 3
    assert coop.agents[0].get("id") == 2
    assert coop.agents[0].get("agent") == Agent.example()

    # other client..
    coop2 = Coop(api_key="a")
    # ..should be able to get public but not private agents
    assert coop2.get(object_type="agent", id=4) == Agent.example()
    with pytest.raises(Exception):
        coop2.get(object_type="agent", id=3)
    # ..should not be able to delete another client's agents
    for i in range(2, 5):
        with pytest.raises(Exception):
            coop2.delete_agent(i)

    # cleanup
    for agent in coop.agents:
        coop.delete_agent(agent.get("id"))
    assert coop.agents == []


@pytest.mark.coop
def test_coop_client_results():
    """
    Test the Coop client results functions.
    """
    coop = Coop()
    assert coop.api_key == "b"

    # make sure we start fresh
    for results in coop.results:
        coop.delete_results(results.get("id"))
    assert coop.results == []

    # cannot get an object that does not exist
    with pytest.raises(Exception):
        coop.get(object_type="results", id=100)

    # create
    response = coop.create(Results.example())
    assert response.get("id") == 2
    assert response.get("type") == "results"
    assert response.get("url") is not None
    response = coop.create(Results.example(), public=False)
    assert response.get("id") == 3
    assert response.get("type") == "results"
    assert response.get("url") is not None
    response = coop.create(Results.example(), public=True)
    assert response.get("id") == 4
    assert response.get("type") == "results"
    assert response.get("url") is not None

    # check
    assert len(coop.results) == 3
    assert coop.results[0].get("id") == 2
    assert coop.results[0].get("results") == Results.example()

    # other client..
    coop2 = Coop(api_key="a")
    # ..should be able to get public but not private results
    assert coop2.get(object_type="results", id=4) == Results.example()
    with pytest.raises(Exception):
        coop2.get(object_type="results", id=3)
    # ..should not be able to delete another client's results
    for i in range(2, 5):
        with pytest.raises(Exception):
            coop2.delete_results(i)

    # cleanup
    for results in coop.results:
        coop.delete_results(results.get("id"))
    assert coop.results == []
