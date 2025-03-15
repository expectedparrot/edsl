import json


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
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON string")
    else:
        raise ValueError("No JSON object found in string")


if __name__ == "__main__":
    text = (
        'Sure - here is some JSON { "key": "value", "number": 123, "array": [1, 2, 3] }'
    )
    extracted_json = extract_json_from_string(text)
    d = extracted_json
