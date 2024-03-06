from collections import UserDict


class AgentResponseDict(UserDict):
    def __init__(
        self,
        *,
        question_name,
        answer,
        comment,
        prompts,
        usage=None,
        cached_response=None,
        raw_model_response=None
    ):
        usage = usage or {"prompt_tokens": 0, "completion_tokens": 0}
        super().__init__(
            {
                "answer": answer,
                "comment": comment,
                "question_name": question_name,
                "prompts": prompts,
                "usage": usage,
                "cached_response": cached_response,
                "raw_model_response": raw_model_response,
            }
        )
