from typing import Any, List, Optional
import os
import asyncio
from edsl.inference_services.InferenceServiceABC import InferenceServiceABC
from edsl.language_models import LanguageModel
from edsl.inference_services.rate_limits_cache import rate_limits
from edsl.utilities.utilities import fix_partial_correct_response

from edsl.enums import InferenceServiceType
import random


class TestService(InferenceServiceABC):
    """OpenAI service class."""

    _inference_service_ = "test"
    _env_key_name_ = None
    _base_url_ = None

    _sync_client_ = None
    _async_client_ = None

    _sync_client_instance = None
    _async_client_instance = None

    key_sequence = None
    usage_sequence = None
    model_exclude_list = []
    input_token_name = "prompt_tokens"
    output_token_name = "completion_tokens"

    @classmethod
    def available(cls) -> list[str]:
        return ["test"]

    @classmethod
    def create_model(cls, model_name, model_class_name=None) -> LanguageModel:
        throw_exception = False

        class TestServiceLanguageModel(LanguageModel):
            _model_ = "test"
            _parameters_ = {"temperature": 0.5}
            _inference_service_ = InferenceServiceType.TEST.value
            usage_sequence = ["usage"]
            key_sequence = ["message", 0, "text"]
            input_token_name = cls.input_token_name
            output_token_name = cls.output_token_name
            _rpm = 1000
            _tpm = 100000

            @property
            def _canned_response(self):
                if hasattr(self, "canned_response"):
                    return self.canned_response
                else:
                    return "Hello, world"

            async def async_execute_model_call(
                self,
                user_prompt: str,
                system_prompt: str,
                # func: Optional[callable] = None,
                files_list: Optional[List["File"]] = None,
            ) -> dict[str, Any]:
                await asyncio.sleep(0.1)
                # return {"message": """{"answer": "Hello, world"}"""}

                if hasattr(self, "func"):
                    return {
                        "message": [
                            {"text": self.func(user_prompt, system_prompt, files_list)}
                        ],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                    }

                if hasattr(self, "throw_exception") and self.throw_exception:
                    if hasattr(self, "exception_probability"):
                        p = self.exception_probability
                    else:
                        p = 1

                    if random.random() < p:
                        raise Exception("This is a test error")
                return {
                    "message": [{"text": f"{self._canned_response}"}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                }

        return TestServiceLanguageModel
