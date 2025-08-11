"""
Result serialization and deserialization functionality.

This module provides the ResultSerializer class which handles converting Result objects
to and from dictionary representations. This separation allows for cleaner code 
organization and easier testing of serialization logic.
"""

from __future__ import annotations
from typing import Any, TYPE_CHECKING

from ..utilities import remove_edsl_version

if TYPE_CHECKING:
    from .result import Result


class ResultSerializer:
    """Handles serialization and deserialization of Result objects.
    
    This class encapsulates all the logic for converting Result objects to and from
    dictionary representations, keeping the Result class focused on its core 
    responsibilities.
    """

    @staticmethod
    def to_dict(
        result: "Result", 
        add_edsl_version: bool = True, 
        include_cache_info: bool = False
    ) -> dict[str, Any]:
        """Convert a Result object to a dictionary representation.

        Args:
            result: The Result object to serialize
            add_edsl_version: Whether to include EDSL version information
            include_cache_info: Whether to include cache information

        Returns:
            Dictionary representation of the Result object

        Example:
            >>> from edsl.results import Result
            >>> r = Result.example()
            >>> serializer = ResultSerializer()
            >>> data = serializer.to_dict(r)
        """

        def convert_value(value, add_edsl_version=True):
            """Helper function to convert values with to_dict method."""
            if hasattr(value, "to_dict"):
                return value.to_dict(add_edsl_version=add_edsl_version)
            else:
                return value

        d = {}
        for key, value in result.items():
            d[key] = convert_value(value, add_edsl_version=add_edsl_version)

            if key == "prompt":
                new_prompt_dict = {}
                for prompt_name, prompt_obj in value.items():
                    new_prompt_dict[prompt_name] = (
                        prompt_obj
                        if not hasattr(prompt_obj, "to_dict")
                        else prompt_obj.to_dict()
                    )
                d[key] = new_prompt_dict

        if result.indices is not None:
            d["indices"] = result.indices

        if add_edsl_version:
            from .. import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = "Result"

        if include_cache_info:
            d["cache_used_dict"] = result.data["cache_used_dict"]
        else:
            d.pop("cache_used_dict", None)

        if hasattr(result, "interview_hash"):
            d["interview_hash"] = result.interview_hash

        # Preserve the order attribute if it exists
        if hasattr(result, "order"):
            d["order"] = result.order

        return d

    @classmethod  
    @remove_edsl_version
    def from_dict(cls, json_dict: dict) -> "Result":
        """Create a Result object from a dictionary representation.

        Args:
            json_dict: Dictionary containing Result data

        Returns:
            Result object created from the dictionary data

        Example:
            >>> from edsl.results import Result
            >>> r = Result.example()
            >>> data = r.to_dict()
            >>> serializer = ResultSerializer()
            >>> result = serializer.from_dict(data)
            >>> result == r
            True
        """
        from ..agents import Agent
        from ..scenarios import Scenario
        from ..language_models import LanguageModel
        from ..prompts import Prompt
        from .result import Result

        prompt_data = json_dict.get("prompt", {})
        prompt_d = {}
        for prompt_name, prompt_obj in prompt_data.items():
            prompt_d[prompt_name] = Prompt.from_dict(prompt_obj)

        result = Result(
            agent=Agent.from_dict(json_dict["agent"]),
            scenario=Scenario.from_dict(json_dict["scenario"]),
            model=LanguageModel.from_dict(json_dict["model"]),
            iteration=json_dict["iteration"],
            answer=json_dict["answer"],
            prompt=prompt_d,
            raw_model_response=json_dict.get(
                "raw_model_response", {"raw_model_response": "No raw model response"}
            ),
            question_to_attributes=json_dict.get("question_to_attributes", None),
            generated_tokens=json_dict.get("generated_tokens", {}),
            comments_dict=json_dict.get("comments_dict", {}),
            reasoning_summaries_dict=json_dict.get("reasoning_summaries_dict", {}),
            cache_used_dict=json_dict.get("cache_used_dict", {}),
            cache_keys=json_dict.get("cache_keys", {}),
            indices=json_dict.get("indices", None),
            validated_dict=json_dict.get("validated_dict", {}),
        )
        
        if "interview_hash" in json_dict:
            result.interview_hash = json_dict["interview_hash"]

        # Restore the order attribute if it exists in the dictionary
        if "order" in json_dict:
            result.order = json_dict["order"]

        return result 