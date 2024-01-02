class AgentErrors(Exception):
    pass


class AgentAttributeLookupCallbackError(AgentErrors):
    pass


class AgentCombinationError(AgentErrors):
    pass


class AgentLacksLLMError(AgentErrors):
    pass


class AgentRespondedWithBadJSONError(AgentErrors):
    pass
