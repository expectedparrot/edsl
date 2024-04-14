"""This module contains the data transfer models for the application."""
from collections import UserDict


class AgentResponseDict(UserDict):
    """A dictionary to store the response of the agent to a question."""

    def __init__(
        self,
        *,
        question_name,
        answer,
        prompts,
        usage=None,
        comment=None,
        cached_response=None,
        raw_model_response=None,
        simple_model_raw_response=None,
    ):
        """Initialize the AgentResponseDict object."""
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
                "simple_model_raw_response": simple_model_raw_response,
            }
        )
