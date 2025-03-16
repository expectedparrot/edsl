from collections import UserDict
from typing import NamedTuple, Dict, Optional, Any
from dataclasses import dataclass, fields


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
        import reprlib

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


class Answers(UserDict):
    """Helper class to hold the answers to a survey."""

    def add_answer(
        self, response: EDSLResultObjectInput, question: "QuestionBase"
    ) -> None:
        """Add a response to the answers dictionary."""
        answer = response.answer
        comment = response.comment
        generated_tokens = response.generated_tokens
        # record the answer
        if generated_tokens:
            self[question.question_name + "_generated_tokens"] = generated_tokens
        self[question.question_name] = answer
        if comment:
            self[question.question_name + "_comment"] = comment

    def replace_missing_answers_with_none(self, survey: "Survey") -> None:
        """Replace missing answers with None. Answers can be missing if the agent skips a question."""
        for question_name in survey.question_names:
            if question_name not in self:
                self[question_name] = None

    def to_dict(self):
        """Return a dictionary of the answers."""
        return self.data

    @classmethod
    def from_dict(cls, d):
        """Return an Answers object from a dictionary."""
        return cls(d)


if __name__ == "__main__":
    import doctest

    doctest.testmod()