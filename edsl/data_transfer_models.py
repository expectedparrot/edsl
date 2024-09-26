from typing import NamedTuple, Dict, List, Optional, Any
from dataclasses import dataclass, fields
import reprlib


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
    cost: Optional[float] = None


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
    validated: bool = False
    exception_occurred: Exception = None
    cost: Optional[float] = None


@dataclass
class ImageInfo:
    file_path: str
    file_name: str
    image_format: str
    file_size: int
    encoded_image: str

    def __repr__(self):
        reprlib_instance = reprlib.Repr()
        reprlib_instance.maxstring = 30  # Limit the string length for the encoded image

        # Get all fields except encoded_image
        field_reprs = [
            f"{f.name}={getattr(self, f.name)!r}"
            for f in fields(self)
            if f.name != "encoded_image"
        ]

        # Add the reprlib-restricted encoded_image field
        field_reprs.append(f"encoded_image={reprlib_instance.repr(self.encoded_image)}")

        # Join everything to create the repr
        return f"{self.__class__.__name__}({', '.join(field_reprs)})"
