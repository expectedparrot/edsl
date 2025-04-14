from typing import Any, List, Optional, TYPE_CHECKING
import asyncio
import random

from ..inference_service_abc import InferenceServiceABC

from ...enums import InferenceServiceType

# Use TYPE_CHECKING to avoid circular imports at runtime
if TYPE_CHECKING:
    from ...language_models import LanguageModel

if TYPE_CHECKING:
    from ...scenarios.file_store import FileStore as File


from edsl import Model
from edsl.questions import (
    QuestionMultipleChoice,
    QuestionCheckBox,
    QuestionLinearScale,
    QuestionList,
    QuestionDict,
    QuestionNumerical,
    QuestionFreeText,
)


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
    available_models_url = None

    @classmethod
    def available(cls) -> list[str]:
        return ["test"]

    @classmethod
    def create_model(cls, model_name, model_class_name=None) -> "LanguageModel":
        # Removed unused variable

        # Import LanguageModel only when actually creating a model
        from ...language_models import LanguageModel

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
                    return "Hello, world X"

            async def async_execute_model_call(
                self,
                user_prompt: str,
                system_prompt: str,
                # func: Optional[callable] = None,
                files_list: Optional[List["File"]] = None,
                question_name: Optional[str] = None,
            ) -> dict[str, Any]:
                await asyncio.sleep(0.1)

                if hasattr(self, "throw_exception") and self.throw_exception:
                    if hasattr(self, "exception_probability"):
                        p = self.exception_probability
                    else:
                        p = 1

                    if random.random() < p:
                        from ..exceptions import InferenceServiceIntendedError

                        raise InferenceServiceIntendedError("This is a test error")

                if hasattr(self, "func"):
                    return {
                        "message": [
                            {"text": self.func(user_prompt, system_prompt, files_list)}
                        ],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                    }

                response = self._canned_response
                if isinstance(response, dict) and question_name:
                    canned_text = response.get(
                        question_name, f"No canned response for '{question_name}'"
                    )
                else:
                    canned_text = response

                return {
                    "message": [{"text": f"{canned_text}"}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                }

            def set_canned_response(self, survey: "Survey") -> None:
                canned_response = {}

                for q in survey.questions:
                    name = q.question_name

                    if isinstance(q, QuestionMultipleChoice):
                        # Return first option
                        canned_response[name] = q.question_options[0]

                    elif isinstance(q, QuestionCheckBox):
                        # Return first two options as a list
                        canned_response[name] = q.question_options[:2]

                    elif isinstance(q, QuestionLinearScale):
                        # Return middle of the scale
                        values = q.question_options
                        if isinstance(values, list) and all(
                            isinstance(i, int) for i in values
                        ):
                            mid = values[len(values) // 2]
                            canned_response[name] = mid
                        else:
                            canned_response[name] = 5  # default fallback

                    elif isinstance(q, QuestionNumerical):
                        # Return a fixed float value
                        canned_response[name] = 42.0

                    elif isinstance(q, QuestionList):
                        # Return a list of simple strings
                        canned_response[name] = [f"{name} item 1", f"{name} item 2"]

                    elif isinstance(q, QuestionDict):
                        # Return a dict with keys from question_dict_keys if present
                        keys = getattr(q, "answer_keys", ["field1", "field2"])
                        canned_response[name] = {k: f"{k} value" for k in keys}

                    elif isinstance(q, QuestionFreeText):
                        # Return a string
                        canned_response[name] = f"This is a canned answer for {name}."

                    else:
                        # Fallback: simple string
                        canned_response[name] = f"Canned fallback for {name}"
                self.canned_response = canned_response

        return TestServiceLanguageModel
