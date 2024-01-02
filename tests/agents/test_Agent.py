import json
import pytest
from unittest.mock import patch
from edsl.agents import Agent
from edsl.exceptions import (
    AgentAttributeLookupCallbackError,
    AgentCombinationError,
    AgentRespondedWithBadJSONError,
)
from edsl.jobs import Jobs
from edsl.language_models import LanguageModelOpenAIThreeFiveTurbo
from edsl.questions import QuestionMultipleChoice
from edsl.surveys import Survey


def test_agent_creation_valid():
    """Test that an agent can be created with valid arguments."""
    # valid cases
    agent = Agent()
    assert agent.traits == {}
    agent = Agent(traits={})
    assert agent.traits == {}
    agent_dict = {"traits": {"age": 10, "pro": True}}
    agent = Agent(**agent_dict)
    assert agent.traits == agent_dict.get("traits")
    agent_dict = {"traits": {"age": 10, "pro": [1, 2]}}
    agent = Agent(**agent_dict)
    assert agent.traits == agent_dict.get("traits")


def test_agent_update_traits():
    agent = Agent(traits={"age": 30})

    # missing callback
    with pytest.raises(AgentAttributeLookupCallbackError):
        agent.update_traits(["height"])

    # valid callback and features
    def valid_lookup_callback(attribute):
        if attribute == "height":
            return ("height", "170cm")
        return (attribute, "unknown")

    new_attributes = ["height", "profession"]
    agent.update_traits(new_attributes, valid_lookup_callback)
    assert agent.traits == {"height": "170cm", "profession": "unknown"}

    # invalid callback - doesn't handle missing
    def invalid_lookup_callback(attribute):
        if attribute == "length":
            return ("length", "150cm")

    new_attributes = ["duration"]
    with pytest.raises(AgentAttributeLookupCallbackError):
        agent.update_traits(new_attributes, invalid_lookup_callback)


def test_agent_dunder_methods():
    agent1 = Agent(traits={"age": 10})
    agent2 = Agent(traits={"name": "Peter"})
    agent3 = Agent(traits={"age": 10, "name": "Peter"})
    # __add__
    assert isinstance(agent1 + None, Agent)
    assert (agent1 + None) is agent1
    assert isinstance(agent1 + agent2, Agent)
    assert (agent1 + agent2).traits == agent3.traits
    with pytest.raises(AgentCombinationError):
        agent1 + agent3
    # __eq__
    assert agent1 == agent1
    assert agent1 + agent2 == agent3
    # __repr__
    assert repr(agent1) == "Agent(traits = {'age': 10})"


def test_agent_serialization():
    agent = Agent(traits={"age": 10})
    agent_dict = agent.to_dict()
    assert agent_dict == {"traits": {"age": 10}, "verbose": False}
    agent2 = Agent.from_dict(agent_dict)
    assert agent2.traits == {"age": 10}
    assert agent2 == agent


def test_agent_forward_methods():
    agent = Agent(traits={"age": 10})
    # to Question
    question = QuestionMultipleChoice(
        question_text="How are you?", question_options=["Good", "Bad"]
    )
    job = agent.to(question)
    assert type(job) == Jobs
    assert type(agent.get_value(job)) == list
    assert agent.get_value(job)[0] == agent
    # to Survey
    survey = Survey(questions=[question])
    job = agent.to(survey)
    assert type(job) == Jobs
    assert type(agent.get_value(job)) == list
    assert agent.get_value(job)[0] == agent
    # set value
    agent.set_value(job, [Agent(traits={"age": 20}), Agent(traits={"age": 30})])
    assert job.agents == [Agent(traits={"age": 20}), Agent(traits={"age": 30})]


def test_agent_llm_construct_prompt():
    # prompt construction
    agent = Agent(traits={"age": 10})
    question = QuestionMultipleChoice(
        question_text="How are you?", question_options=["Good", "Bad"]
    )
    prompt = agent.construct_system_prompt()
    assert "You are answering" in prompt
    assert "{'age': 10}" in prompt
    # get response - valid
    mock_response = {"some_key": "some_value"}
    with patch.object(
        LanguageModelOpenAIThreeFiveTurbo, "get_response", return_value=mock_response
    ):
        response = agent.get_response("prompt", "system prompt", None)
    assert response == mock_response
    # get response - invalid
    with patch.object(
        LanguageModelOpenAIThreeFiveTurbo,
        "get_response",
        side_effect=json.JSONDecodeError("msg", "doc", 0),
    ):
        with pytest.raises(AgentRespondedWithBadJSONError):
            agent.get_response("prompt", "system prompt", None)
    # answer_question
    question = QuestionMultipleChoice(
        question_text="Could you defeat a goose in mortal combat?",
        question_options=["yes", "no"],
        question_name="goose_fight",
    )
    answer = agent.answer_question(question, debug=True)
    assert "answer" in answer
    assert "comment" in answer
    mock_response = {"answer": 0, "comment": "I am a comment"}
    with patch.object(
        LanguageModelOpenAIThreeFiveTurbo, "get_response", return_value=mock_response
    ):
        answer = agent.answer_question(question, debug=False)
    assert "answer" in answer
    assert "comment" in answer
    assert "I am a comment" in answer.get("comment")


def test_agent_display_methods():
    agent = Agent(traits={"age": 10})
    assert (
        agent.dict_to_html()
        == '<table border="1">\n<tr><th>Key</th><th>Value</th></tr>\n<tr><td>age</td><td>10</td></tr>\n</table>'
    )
    assert (
        agent.print(html=True)
        == '<table border="1">\n<tr><th>Key</th><th>Value</th></tr>\n<tr><td>age</td><td>10</td></tr>\n</table>'
    )
