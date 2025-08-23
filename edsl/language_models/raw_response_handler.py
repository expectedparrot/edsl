import json
from typing import Optional, Any
from .exceptions import (
    LanguageModelBadResponseError,
    LanguageModelTypeError,
    LanguageModelIndexError,
    LanguageModelKeyError,
)

from json_repair import repair_json


def _extract_item_from_raw_response(data, sequence):
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return data
    current_data = data
    for i, key in enumerate(sequence):
        try:
            if isinstance(current_data, (list, tuple)):
                if not isinstance(key, int):
                    raise LanguageModelTypeError(
                        f"Expected integer index for sequence at position {i}, got {type(key).__name__}"
                    )
                if key < 0 or key >= len(current_data):
                    raise LanguageModelIndexError(
                        f"Index {key} out of range for sequence of length {len(current_data)} at position {i}"
                    )
            elif isinstance(current_data, dict):
                if key not in current_data:
                    raise LanguageModelKeyError(
                        f"Key '{key}' not found in dictionary at position {i}"
                    )
            else:
                raise LanguageModelTypeError(
                    f"Cannot index into {type(current_data).__name__} at position {i}. Full response is: {data} of type {type(data)}. Key sequence is: {sequence}"
                )

            current_data = current_data[key]
        except Exception as e:
            path = " -> ".join(map(str, sequence[: i + 1]))

            # Create a safe error message that won't be None
            if "error" in data and data["error"] is not None:
                msg = str(data["error"])
            else:
                msg = f"Error accessing path: {path}. {str(e)}. Full response is: '{data}'"

            raise LanguageModelBadResponseError(message=msg, response_json=data)
    if isinstance(current_data, str):
        return current_data.strip()
    else:
        return current_data


class RawResponseHandler:
    """Class to handle raw responses from language models."""

    def __init__(
        self,
        key_sequence: list,
        usage_sequence: Optional[list] = None,
        reasoning_sequence: Optional[list] = None,
    ):
        self.key_sequence = key_sequence
        self.usage_sequence = usage_sequence
        self.reasoning_sequence = reasoning_sequence

    def get_generated_token_string(self, raw_response):
        try:
            # Check if there are multiple choices and handle n parameter
            if isinstance(raw_response, dict) and "choices" in raw_response:
                choices = raw_response["choices"]
                if isinstance(choices, list) and len(choices) > 1:
                    # Log that we have multiple choices but return the first one for backward compatibility
                    import warnings
                    warnings.warn(
                        f"Model returned {len(choices)} completions (n={len(choices)}) but only using the first one. "
                        "To access all completions, you'll need to use the raw response.",
                        UserWarning
                    )
                    # Store all choices in a special attribute of the response for potential access
                    if not hasattr(raw_response, '_all_choices'):
                        raw_response['_all_choices'] = choices
            
            return _extract_item_from_raw_response(raw_response, self.key_sequence)
        except (
            LanguageModelKeyError,
            LanguageModelIndexError,
            LanguageModelTypeError,
            LanguageModelBadResponseError,
        ):
            # For non-reasoning models or reasoning models with different response formats,
            # try to extract text directly from common response formats
            if isinstance(raw_response, dict):
                # Responses API format for non-reasoning models
                if "output" in raw_response and isinstance(
                    raw_response["output"], list
                ):
                    # Try to get first message content
                    if len(raw_response["output"]) > 0:
                        item = raw_response["output"][0]
                        if isinstance(item, dict) and "content" in item:
                            if (
                                isinstance(item["content"], list)
                                and len(item["content"]) > 0
                            ):
                                first_content = item["content"][0]
                                if (
                                    isinstance(first_content, dict)
                                    and "text" in first_content
                                ):
                                    return first_content["text"]
                            elif isinstance(item["content"], str):
                                return item["content"]

                # OpenAI completions format
                if (
                    "choices" in raw_response
                    and isinstance(raw_response["choices"], list)
                    and len(raw_response["choices"]) > 0
                ):
                    choice = raw_response["choices"][0]
                    if isinstance(choice, dict):
                        if "text" in choice:
                            return choice["text"]
                        elif (
                            "message" in choice
                            and isinstance(choice["message"], dict)
                            and "content" in choice["message"]
                        ):
                            return choice["message"]["content"]

                # Text directly in response
                if "text" in raw_response:
                    return raw_response["text"]
                elif "content" in raw_response:
                    return raw_response["content"]

                # Error message - try to return a coherent error for debugging
                if "message" in raw_response:
                    return f"[ERROR: {raw_response['message']}]"

            # If we get a string directly, return it
            if isinstance(raw_response, str):
                return raw_response

            # As a last resort, convert the whole response to string
            try:
                return f"[ERROR: Could not extract text. Raw response: {str(raw_response)}]"
            except Exception:
                return "[ERROR: Could not extract text from response]"

    def get_usage_dict(self, raw_response):
        if self.usage_sequence is None:
            return {}
        try:
            return _extract_item_from_raw_response(raw_response, self.usage_sequence)
        except (
            LanguageModelKeyError,
            LanguageModelIndexError,
            LanguageModelTypeError,
            LanguageModelBadResponseError,
        ):
            # For non-reasoning models, try to extract usage from common response formats
            if isinstance(raw_response, dict):
                # Standard OpenAI usage format
                if "usage" in raw_response:
                    return raw_response["usage"]

                # Look for nested usage info
                if "choices" in raw_response and len(raw_response["choices"]) > 0:
                    choice = raw_response["choices"][0]
                    if isinstance(choice, dict) and "usage" in choice:
                        return choice["usage"]

            # If no usage info found, return empty dict
            return {}

    def get_reasoning_summary(self, raw_response):
        """
        Extract reasoning summary from the model response.

        Handles various response structures:
        1. Standard path extraction using self.reasoning_sequence
        2. Direct access to output[0]['summary'] for OpenAI responses
        3. List responses where the first item contains the output structure
        """
        if self.reasoning_sequence is None:
            return None

        try:
            # First try the standard extraction path
            summary_data = _extract_item_from_raw_response(
                raw_response, self.reasoning_sequence
            )

            # If summary_data is a list of dictionaries with 'text' and 'type' fields
            # (as in OpenAI's response format), combine them into a single string
            if isinstance(summary_data, list) and all(
                isinstance(item, dict) and "text" in item for item in summary_data
            ):
                return "\n\n".join(item["text"] for item in summary_data)

            return summary_data
        except Exception:
            # Fallback approaches for different response structures
            try:
                # Case 1: Direct dict with 'output' field (common OpenAI format)
                if isinstance(raw_response, dict) and "output" in raw_response:
                    output = raw_response["output"]
                    if (
                        isinstance(output, list)
                        and len(output) > 0
                        and "summary" in output[0]
                    ):
                        summary_data = output[0]["summary"]
                        if isinstance(summary_data, list) and all(
                            isinstance(item, dict) and "text" in item
                            for item in summary_data
                        ):
                            return "\n\n".join(item["text"] for item in summary_data)

                # Case 2: List where the first item is a dict with 'output' field
                if isinstance(raw_response, list) and len(raw_response) > 0:
                    first_item = raw_response[0]
                    if isinstance(first_item, dict) and "output" in first_item:
                        output = first_item["output"]
                        if (
                            isinstance(output, list)
                            and len(output) > 0
                            and "summary" in output[0]
                        ):
                            summary_data = output[0]["summary"]
                            if isinstance(summary_data, list) and all(
                                isinstance(item, dict) and "text" in item
                                for item in summary_data
                            ):
                                return "\n\n".join(
                                    item["text"] for item in summary_data
                                )
            except Exception:
                pass

            return None

    def parse_response(self, raw_response: dict[str, Any]) -> Any:
        """Parses the API response and returns the response text."""

        from edsl.data_transfer_models import EDSLOutput

        generated_token_string = self.get_generated_token_string(raw_response)
        # Ensure generated_token_string is a string before using string methods
        if not isinstance(generated_token_string, str):
            generated_token_string = str(generated_token_string)
        last_newline = generated_token_string.rfind("\n")
        reasoning_summary = self.get_reasoning_summary(raw_response)

        if last_newline == -1:
            # There is no comment
            edsl_dict = {
                "answer": self.convert_answer(generated_token_string),
                "generated_tokens": generated_token_string,
                "comment": None,
                "reasoning_summary": reasoning_summary,
            }
        else:
            edsl_dict = {
                "answer": self.convert_answer(generated_token_string[:last_newline]),
                "comment": generated_token_string[last_newline + 1 :].strip(),
                "generated_tokens": generated_token_string,
                "reasoning_summary": reasoning_summary,
            }
        return EDSLOutput(**edsl_dict)

    @staticmethod
    def convert_answer(response_part):
        import json

        response_part = response_part.strip()

        if response_part == "None":
            return None

        repaired = repair_json(response_part)
        if repaired == '""':
            # it was a literal string
            return response_part

        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            # last resort
            return response_part
