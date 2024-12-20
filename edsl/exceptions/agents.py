from edsl.exceptions.BaseException import BaseException


# from edsl.utilities.utilities import is_notebook

# from IPython.core.error import UsageError

# class AgentListErrorAlternative(UsageError):
#     def __init__(self, message):
#         super().__init__(message)

import sys
from edsl.utilities.is_notebook import is_notebook


class AgentListError(BaseException):
    relevant_doc = "https://docs.expectedparrot.com/en/latest/agents.html#agent-lists"


class AgentErrors(BaseException):
    relevant_doc = "https://docs.expectedparrot.com/en/latest/agents.html"


class AgentDynamicTraitsFunctionError(AgentErrors):
    relevant_doc = (
        "https://docs.expectedparrot.com/en/latest/agents.html#dynamic-traits-function"
    )
    relevant_notebook = "https://docs.expectedparrot.com/en/latest/notebooks/example_agent_dynamic_traits.html"


class AgentDirectAnswerFunctionError(AgentErrors):
    relevant_doc = "https://docs.expectedparrot.com/en/latest/agents.html#agent-direct-answering-methods"


class AgentCombinationError(AgentErrors):
    relevant_doc = (
        "https://docs.expectedparrot.com/en/latest/agents.html#combining-agents"
    )


class AgentNameError(AgentErrors):
    relevant_doc = "https://docs.expectedparrot.com/en/latest/agents.html#agent-names"


class AgentTraitKeyError(AgentErrors):
    relevant_doc = (
        "https://docs.expectedparrot.com/en/latest/agents.html#constructing-an-agent"
    )


class FailedTaskException(Exception):
    def __init__(self, message, agent_response_dict):
        super().__init__(message)
        self.agent_response_dict = agent_response_dict
