"""Utility functions for working with JSON data."""

import hashlib
import json
import re


class CustomEncoder(json.JSONEncoder):
    """Custom JSON encoder for handling non-serializable objects."""
    def default(self, obj):
        try:
            return json.JSONEncoder.default(self, obj)
        except TypeError:
            return str(obj)


def dict_hash(data: dict):
    """Create a hash of a dictionary."""
    return hash(
        int(hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest(), 16)
    )


def clean_json(bad_json_str):
    """Clean JSON string by replacing problematic characters."""
    replacements = [
        ("\\", "\\\\"),
        ("\n", "\\n"),
        ("\r", "\\r"),
        ("\t", "\\t"),
        ("\b", "\\b"),
        ("\f", "\\f"),
        ("[/INST]", "removed_inst"),
    ]

    s = bad_json_str
    for old, new in replacements:
        s = s.replace(old, new)
    return s


def repair_json(json_string: str) -> str:
    """Attempt to repair a JSON string that is not valid JSON."""
    json_string = json_string.replace("\n", "\\n").replace("\r", "\\r")
    json_string = json_string.replace("'", "\\'")
    json_string = json_string.replace("'", '"')
    json_string = re.sub(r",\s*}", "}", json_string)
    json_string = re.sub(r",\s*]", "]", json_string)
    json_string = re.sub(r"(?<={|,)\s*([a-zA-Z0-9_]+)\s*:", r'"\1":', json_string)
    return json_string


def extract_json_from_string(s):
    """Extract a JSON string from a string."""
    # Find the first occurrence of '{'
    start_idx = s.find("{")
    # Find the last occurrence of '}'
    end_idx = s.rfind("}")
    # If both '{' and '}' are found in the string
    if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
        # Extract the substring from start_idx to end_idx (inclusive)
        json_str = s[start_idx : end_idx + 1]
        return json_str
    else:
        raise ValueError("No JSON object found in string")


def valid_json(json_string):
    """Check if a string is valid JSON."""
    try:
        _ = json.loads(json_string)
        return True
    except json.JSONDecodeError:
        return False


def fix_partial_correct_response(text: str) -> dict:
    """Try to extract valid JSON from a partial or malformed response."""
    # Find the start position of the key "answer"
    answer_key_start = text.find('"answer"')

    if answer_key_start == -1:
        return {"error": "No 'answer' key found in the text"}

    # Define regex to find the complete JSON object starting with "answer"
    json_pattern = r'(\{[^\{\}]*"answer"[^\{\}]*\})'
    match = re.search(json_pattern, text)

    if not match:
        return {"error": "No valid JSON object found"}

    # Extract the matched JSON object
    json_object = match.group(0)

    # Find the start and stop positions of the JSON object in the original text
    start_pos = text.find(json_object)
    stop_pos = start_pos + len(json_object)

    # Parse the JSON object to validate it
    try:
        parsed_json = json.loads(json_object)
    except json.JSONDecodeError:
        return {"error": "Failed to parse JSON object"}

    # Return the result as a dictionary with positions
    return {"start": start_pos, "stop": stop_pos, "extracted_json": json_object}


def merge_dicts(dict_list):
    """Merge a list of dictionaries into a single dictionary."""
    result = {}
    all_keys = set()
    for d in dict_list:
        all_keys.update(d.keys())
    for key in all_keys:
        result[key] = [d.get(key, None) for d in dict_list]
    return result