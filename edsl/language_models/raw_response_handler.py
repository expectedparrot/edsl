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
        inference_service: Optional[str] = None,
    ):
        self.key_sequence = key_sequence
        self.usage_sequence = usage_sequence
        self.reasoning_sequence = reasoning_sequence
        self.inference_service = inference_service

    def get_generated_token_string(self, raw_response):
        try:
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

                # Anthropic reasoning completions format
                text_blocks = []
                if "content" in raw_response and isinstance(
                    raw_response["content"], list
                ):
                    for item in raw_response["content"]:
                        if (
                            isinstance(item, dict)
                            and "type" in item
                            and item["type"] == "text"
                        ):
                            text_blocks.append(item["text"])
                    return "\n\n".join(text_blocks)

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

        When inference_service is None, returns None (skip).
        When set, uses the path for that service only; other services return None.

        Paths:
        - anthropic: reasoning_sequence ["content"] then filter type='thinking' blocks
        - openai / openai_v2: reasoning_sequence or output[0]['summary'] fallback
        - other: return None
        """
        if self.inference_service is None:
            return None

        # Anthropic: use reasoning_sequence to get content, then filter thinking blocks
        if self.inference_service == "anthropic":
            if self.reasoning_sequence is not None:
                try:
                    summary_data = _extract_item_from_raw_response(
                        raw_response, self.reasoning_sequence
                    )
                    if isinstance(summary_data, list):
                        thinking_parts = [
                            item["thinking"]
                            for item in summary_data
                            if isinstance(item, dict)
                            and item.get("type") == "thinking"
                            and "thinking" in item
                        ]
                        if thinking_parts:
                            return "\n\n".join(thinking_parts)
                except Exception:
                    pass
            return None

        # OpenAI-style: reasoning_sequence or output/summary fallbacks
        if self.inference_service in ("openai", "openai_v2"):
            if self.reasoning_sequence is not None:
                try:
                    summary_data = _extract_item_from_raw_response(
                        raw_response, self.reasoning_sequence
                    )
                    if isinstance(summary_data, list) and all(
                        isinstance(item, dict) and "text" in item
                        for item in summary_data
                    ):
                        return "\n\n".join(item["text"] for item in summary_data)
                    return summary_data
                except Exception:
                    pass
            try:
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

        # Other inference service: don't try anything
        return None

    # Delimiter used in prompt templates and for parsing the comment from
    # the generated text.  Kept as a class attribute so templates and tests
    # can reference the single source of truth.
    COMMENT_DELIMITERS = ["COMMENT:", "CORRECTION:"]

    def parse_response(self, raw_response: dict[str, Any]) -> Any:
        """Parses the API response and returns the response text.

        The comment is separated from the answer by looking for known
        delimiters (COMMENT:, CORRECTION:) on their own line.  If no
        delimiter is found, falls back to splitting on the last newline
        for backwards compatibility with cached responses.
        """

        from edsl.data_transfer_models import EDSLOutput

        generated_token_string = self.get_generated_token_string(raw_response)
        # Ensure generated_token_string is a string before using string methods
        if not isinstance(generated_token_string, str):
            generated_token_string = str(generated_token_string)

        reasoning_summary = self.get_reasoning_summary(raw_response)

        answer_text, comment_text = self._split_answer_and_comment(
            generated_token_string
        )

        edsl_dict = {
            "answer": self.convert_answer(answer_text),
            "generated_tokens": generated_token_string,
            "comment": comment_text,
            "reasoning_summary": reasoning_summary,
        }
        return EDSLOutput(**edsl_dict)

    @classmethod
    def _split_answer_and_comment(cls, generated_token_string: str):
        """Split *generated_token_string* into (answer, comment).

        Strategy (in order):
        1. Look for the **last** occurrence of ``COMMENT:`` (case-insensitive)
           on its own line (possibly preceded by whitespace).  Everything
           before that line is the answer; everything after the delimiter
           keyword is the comment.  Multi-line comments are supported.
        2. Fall back to the legacy ``rfind("\\n")`` approach so that older
           cached responses still parse correctly.
        """
        import re

        # Strategy 1: look for known comment delimiters (COMMENT:, CORRECTION:)
        # Match the last line starting with any recognized delimiter.
        delimiter_alts = "|".join(re.escape(d) for d in cls.COMMENT_DELIMITERS)
        pattern = r'(?m)^[ \t]*(?:' + delimiter_alts + r')[ \t]*(.*)'
        matches = list(re.finditer(pattern, generated_token_string, re.IGNORECASE))
        if matches:
            last_match = matches[-1]
            answer_part = generated_token_string[: last_match.start()].strip()
            # Combine the rest-of-line after the delimiter with any
            # subsequent lines to form the full comment.
            comment_part = (
                last_match.group(1)
                + generated_token_string[last_match.end() :]
            ).strip()
            if not answer_part:
                # Edge case: the entire string started with COMMENT:
                # Treat the whole thing as the answer with no comment.
                return generated_token_string.strip(), None
            return answer_part, comment_part or None

        # Strategy 2: split on first newline — answer is the first line,
        # everything after is the comment (preserving multi-line comments)
        first_newline = generated_token_string.find("\n")
        if first_newline == -1:
            return generated_token_string, None
        else:
            answer_part = generated_token_string[:first_newline].strip()
            comment_part = generated_token_string[first_newline + 1 :].strip()
            return answer_part, comment_part or None

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
