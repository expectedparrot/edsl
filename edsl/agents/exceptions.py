
from ..base.base_exception import BaseException


class AgentListError(BaseException):
    """
    Exception raised when an AgentList operation fails.
    
    This exception is raised in the following cases:
    - When an invalid expression is provided in the filter() method
    - When trying to add traits with mismatched lengths
    - When attempting to create a table from an empty AgentList
    
    Examples:
        ```python
        agents.filter("invalid expression")  # Raises AgentListError
        agents.add_trait(name="scores", values=[1, 2])  # Raises AgentListError if agents list has different length
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/agents.html#agent-lists"


class AgentErrors(BaseException):
    """
    Base exception class for all agent-related errors.
    
    This class is the parent of all agent-specific exceptions and may also be raised directly
    when modifying agent traits or during operations like renaming or adding traits.
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/agents.html"


class AgentDynamicTraitsFunctionError(AgentErrors):
    """
    Exception raised when there's an issue with the dynamic traits function.
    
    This exception occurs when:
    - The dynamic traits function has too many parameters
    - The dynamic traits function has parameters other than 'question'
    
    This error typically indicates that your dynamic traits function has an incorrect signature.
    The function should accept only one parameter named 'question'.
    
    Examples:
        ```python
        def wrong_func(question, extra_param):  # Will raise AgentDynamicTraitsFunctionError
            return {"trait": "value"}
        ```
    """
    relevant_doc = (
        "https://docs.expectedparrot.com/en/latest/agents.html#dynamic-traits-function"
    )
    relevant_notebook = "https://docs.expectedparrot.com/en/latest/notebooks/example_agent_dynamic_traits.html"


class AgentDirectAnswerFunctionError(AgentErrors):
    """
    Exception raised when there's an issue with the direct answer method.
    
    This exception occurs when the direct answer method doesn't have the required parameters.
    The method must include 'question', 'scenario', and/or 'self' parameters.
    
    Examples:
        ```python
        def wrong_answer_func(wrong_param):  # Will raise AgentDirectAnswerFunctionError
            return "Answer"
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/agents.html#agent-direct-answering-methods"


class AgentCombinationError(AgentErrors):
    """
    Exception raised when attempting to combine agents with overlapping traits.
    
    This exception occurs when you try to combine agents that have the same trait names,
    which would result in ambiguous trait values in the combined agent.
    
    To fix this, ensure that the agents being combined have unique trait names,
    or rename the conflicting traits before combination.
    
    Examples:
        ```python
        agent1 = Agent(name="A1", age=30)
        agent2 = Agent(name="A2", age=40)
        agent1 + agent2  # Raises AgentCombinationError due to duplicate 'age' trait
        ```
    """
    relevant_doc = (
        "https://docs.expectedparrot.com/en/latest/agents.html#combining-agents"
    )


class AgentNameError(AgentErrors):
    """
    Exception raised when there's an issue with an agent's name.
    
    This exception occurs when a trait key conflicts with the 'name' parameter,
    as 'name' is a special attribute for agents and cannot be used as a trait name.
    
    Examples:
        ```python
        Agent(name="John", name="John")  # Raises AgentNameError
        agent.add_trait(name="name", value="NewName")  # Raises AgentNameError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/agents.html#agent-names"


class AgentTraitKeyError(AgentErrors):
    """
    Exception raised when an invalid trait key is used.
    
    This exception occurs when a trait key is not a valid Python identifier.
    Trait keys must follow Python variable naming rules (no spaces, no special characters 
    except underscore, cannot start with a number).
    
    Examples:
        ```python
        Agent(name="John", "invalid-key"=30)  # Raises AgentTraitKeyError
        agent.add_trait(name="2invalid", value="value")  # Raises AgentTraitKeyError
        ```
    """
    relevant_doc = (
        "https://docs.expectedparrot.com/en/latest/agents.html#constructing-an-agent"
    )


class AgentAttributeError(AgentErrors):
    """
    Exception raised when accessing a non-existent attribute of an agent.
    
    This exception occurs when trying to access a trait or attribute that
    doesn't exist on the agent.
    
    Examples:
        ```python
        agent = Agent(name="John", age=30)
        agent.height  # Raises AgentAttributeError as 'height' doesn't exist
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/agents.html#agent-traits"
    
    def __init__(self, message):
        super().__init__(message)
        

class FailedTaskException(BaseException):
    """
    Exception raised when an agent task execution fails.
    
    This exception is used to track agent execution failures and retain information
    about the agent's response when the failure occurred.
    
    Note: This exception class is currently not used in the codebase.
    """
    def __init__(self, message, agent_response_dict):
        super().__init__(f"Agent task failed: {message}")
        self.agent_response_dict = agent_response_dict
