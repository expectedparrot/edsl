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
