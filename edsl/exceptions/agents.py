class AgentErrors(Exception):
    pass


class AgentDynamicTraitsFunctionError(AgentErrors):
    pass


class AgentDirectAnswerFunctionError(AgentErrors):
    pass


class AgentAttributeLookupCallbackError(AgentErrors):
    pass


class AgentCombinationError(AgentErrors):
    pass


class AgentLacksLLMError(AgentErrors):
    pass


class AgentRespondedWithBadJSONError(AgentErrors):
    pass


class AgentNameError(AgentErrors):
    pass


class AgentTraitKeyError(AgentErrors):
    pass


class FailedTaskException(Exception):
    def __init__(self, message, agent_response_dict):
        super().__init__(message)
        self.agent_response_dict = agent_response_dict
