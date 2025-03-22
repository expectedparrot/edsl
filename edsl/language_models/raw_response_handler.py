import json
from typing import Optional, Any
from .exceptions import (
    LanguageModelBadResponseError,
    LanguageModelTypeError,
    LanguageModelIndexError,
    LanguageModelKeyError
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
            if "error" in data:
                msg = data["error"]
            else:
                msg = f"Error accessing path: {path}. {str(e)}. Full response is: '{data}'"
            raise LanguageModelBadResponseError(message=msg, response_json=data)
    if isinstance(current_data, str):
        return current_data.strip()
    else:
        return current_data


class RawResponseHandler:
    """Class to handle raw responses from language models."""

    def __init__(self, key_sequence: list, usage_sequence: Optional[list] = None):
        self.key_sequence = key_sequence
        self.usage_sequence = usage_sequence

    def get_generated_token_string(self, raw_response):
        return _extract_item_from_raw_response(raw_response, self.key_sequence)

    def get_usage_dict(self, raw_response):
        if self.usage_sequence is None:
            return {}
        return _extract_item_from_raw_response(raw_response, self.usage_sequence)

    def parse_response(self, raw_response: dict[str, Any]) -> Any:
        """Parses the API response and returns the response text."""

        from edsl.data_transfer_models import EDSLOutput

        generated_token_string = self.get_generated_token_string(raw_response)
        last_newline = generated_token_string.rfind("\n")

        if last_newline == -1:
            # There is no comment
            edsl_dict = {
                "answer": self.convert_answer(generated_token_string),
                "generated_tokens": generated_token_string,
                "comment": None,
            }
        else:
            edsl_dict = {
                "answer": self.convert_answer(generated_token_string[:last_newline]),
                "comment": generated_token_string[last_newline + 1 :].strip(),
                "generated_tokens": generated_token_string,
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
