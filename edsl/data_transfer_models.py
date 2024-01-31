from collections import UserDict


class AgentResponseDict(UserDict):
    def __init__(self, *, question_name, answer, comment, prompts):
        super().__init__(
            {
                "answer": answer,
                "comment": comment,
                "question_name": question_name,
                "prompts": prompts,
            }
        )
