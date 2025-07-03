import pytest
from edsl.agents import Agent

from edsl.agents.exceptions import (
    AgentCombinationError,
    AgentDirectAnswerFunctionError,
    AgentDynamicTraitsFunctionError,
    AgentNameError,
    AgentTraitKeyError,
)


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


def test_agent_dunder_methods():
    agent1 = Agent(traits={"age": 10})
    agent2 = Agent(traits={"first_name": "Peter"})
    agent3 = Agent(traits={"age": 10, "first_name": "Peter"})
    # __add__
    assert isinstance(agent1 + None, Agent)
    assert (agent1 + None) is agent1
    assert isinstance(agent1 + agent2, Agent)
    assert (agent1 + agent2).traits == agent3.traits
    # Agents now combine without raising exceptions
    combined = agent1 + agent3
    assert isinstance(combined, Agent)
    # __eq__
    assert agent1 == agent1
    assert agent1 + agent2 == agent3
    # __repr__
    assert repr(agent1) == "Agent(traits = {'age': 10})"


def test_agent_serialization():
    agent = Agent(traits={"age": 10})
    agent_dict = agent.to_dict()
    assert {"traits": {"age": 10}}.items() <= agent_dict.items()
    agent2 = Agent.from_dict(agent_dict)
    assert agent2.traits == {"age": 10}
    assert agent2 == agent


def test_agent_forbidden_name():
    with pytest.raises(AgentNameError):
        Agent(traits={"age": 10, "name": "Peter"})


def test_agent_invalid_trait_key():
    with pytest.raises(AgentTraitKeyError):
        Agent(traits={"age": 10, "home state": "Massachusetts"})


def test_agent_serialization_with_name():
    agent = Agent(traits={"age": 10}, name="Peter")
    agent_dict = agent.to_dict()
    assert {"traits": {"age": 10}, "name": "Peter"}.items() <= agent_dict.items()
    agent2 = Agent.from_dict(agent_dict)
    assert agent2.traits == {"age": 10}
    assert agent2.name == "Peter"
    assert agent2 == agent


def test_adding_direct_question_answering_method():
    def answer_question_directly(self, question, scenario):
        return self.traits["age"]

    agents = [Agent(traits={"age": i}) for i in range(10, 90)]
    for agent in agents:
        agent.add_direct_question_answering_method(answer_question_directly)

    assert agents[0].answer_question_directly(None, None) == 10

    agent = Agent()

    def bad_answer_question_directly(self, question):
        pass

    with pytest.raises(AgentDirectAnswerFunctionError):
        agent.add_direct_question_answering_method(bad_answer_question_directly)

    def bad_answer_question_directly(question, scenario):
        pass

    with pytest.raises(AgentDirectAnswerFunctionError):
        agent.add_direct_question_answering_method(bad_answer_question_directly)


def test_invigilator_creation():
    from edsl.questions import QuestionMultipleChoice as qmc

    q = qmc.example()
    q.answer_question_directly = lambda x: x
    a = Agent(traits={"age": 10, "hair": "brown", "height": 5.5})
    i = a._create_invigilator(question=q)
    assert i.__class__.__name__ == "InvigilatorFunctional"

    from edsl.questions import QuestionMultipleChoice as qmc

    q = qmc.example()
    a = Agent(traits={"age": 10, "hair": "brown", "height": 5.5})
    a.answer_question_directly = lambda x: x
    i = a._create_invigilator(question=q)
    assert i.__class__.__name__ == "InvigilatorHuman"


def test_agent_dyanmic_traits():
    with pytest.raises(AgentDynamicTraitsFunctionError):

        def foo(x):
            return x

        a = Agent(dynamic_traits_function=foo)

    with pytest.raises(AgentDynamicTraitsFunctionError):

        def foo(question, x):
            return x

        a = Agent(dynamic_traits_function=foo)

    a = Agent(dynamic_traits_function=lambda question: {"age": 30})
    assert a.traits == {"age": 30}


def test_agent_dynamic_traits_answering():
    from edsl import Agent
    from edsl import Model
    from edsl import QuestionFreeText

    def dynamic_traits_function(question):
        if question.question_name == "age":
            return {"age": 10}
        elif question.question_name == "hair":
            return {"hair": "brown"}

    a = Agent(dynamic_traits_function=dynamic_traits_function)

    q = QuestionFreeText(question_name="age", question_text="How old are you?")
    m = Model("test")
    results = q.by(m).by(a).run(disable_remote_inference=True, disable_remote_cache=True, stop_on_exception=True)
    assert results.select("answer.age").to_list()
