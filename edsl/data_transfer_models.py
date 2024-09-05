from typing import NamedTuple, Dict, List, Optional, Any


class ModelInputs(NamedTuple):
    "This is what was send by the agent to the model"
    user_prompt: str
    system_prompt: str
    encoded_image: Optional[str] = None


class EDSLOutput(NamedTuple):
    "This is the edsl dictionary that is returned by the model"
    answer: Any
    generated_tokens: str
    comment: Optional[str] = None


class ModelResponse(NamedTuple):
    "This is the metadata that is returned by the model and includes info about the cache"
    response: dict
    cache_used: bool
    cache_key: str
    cached_response: Optional[Dict[str, Any]] = None


class AgentResponseDict(NamedTuple):
    edsl_dict: EDSLOutput
    model_inputs: ModelInputs
    model_outputs: ModelResponse


class EDSLResultObjectInput(NamedTuple):
    generated_tokens: str
    question_name: str
    prompts: dict
    cached_response: str
    raw_model_response: str
    cache_used: bool
    cache_key: str
    answer: Any
    comment: str


# from collections import UserDict


# class AgentResponseDict(UserDict):
#     """A dictionary to store the response of the agent to a question."""

#     def __init__(
#         self,
#         *,
#         question_name,
#         answer,
#         prompts,
#         generated_tokens: str,
#         usage=None,
#         comment=None,
#         cached_response=None,
#         raw_model_response=None,
#         simple_model_raw_response=None,
#         cache_used=None,
#         cache_key=None,
#     ):
#         """Initialize the AgentResponseDict object."""
#         usage = usage or {"prompt_tokens": 0, "completion_tokens": 0}
#         if generated_tokens is None:
#             raise ValueError("generated_tokens must be provided")
#         self.data = {
#             "answer": answer,
#             "comment": comment,
#             "question_name": question_name,
#             "prompts": prompts,
#             "usage": usage,
#             "cached_response": cached_response,
#             "raw_model_response": raw_model_response,
#             "simple_model_raw_response": simple_model_raw_response,
#             "cache_used": cache_used,
#             "cache_key": cache_key,
#             "generated_tokens": generated_tokens,
#         }

#     @property
#     def data(self):
#         return self._data

#     @data.setter
#     def data(self, value):
#         self._data = value

#     def __getitem__(self, key):
#         return self.data.get(key, None)

#     def __setitem__(self, key, value):
#         self.data[key] = value

#     def __delitem__(self, key):
#         del self.data[key]

#     def __iter__(self):
#         return iter(self.data)

#     def __len__(self):
#         return len(self.data)

#     def keys(self):
#         return self.data.keys()

#     def values(self):
#         return self.data.values()

#     def items(self):
#         return self.data.items()

#     def is_this_same_model(self):
#         return True
