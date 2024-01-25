from collections import UserDict


class AgentResponseDict(UserDict):
    def __init__(self, answer, comment, prompts):
        super().__init__({"answer": answer, "comment": comment, "prompts": prompts})
