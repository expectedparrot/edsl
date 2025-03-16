"""Utility functions for working with strings, dictionaries, and files."""

from functools import wraps
import types
import time

import hashlib
import json
import keyword
import os
import random
import re
import string
import tempfile
import gzip
import webbrowser

from html import escape
from typing import Callable, Union


class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return json.JSONEncoder.default(self, obj)
        except TypeError:
            return str(obj)


def time_it(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        class_name = args[0].__class__.__name__ if args else func.__module__
        print(
            f"Function {class_name}.{func.__name__} took {execution_time:.4f} seconds to execute"
        )
        return result

    return wrapper


def time_all_functions(module_or_class):
    for name, obj in vars(module_or_class).items():
        if isinstance(obj, types.FunctionType):
            setattr(module_or_class, name, time_it(obj))


def dict_hash(data: dict):
    return hash(
        int(hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest(), 16)
    )


def extract_json_from_string(text):
    pattern = re.compile(r"\{.*?\}")
    match = pattern.search(text)
    if match:
        json_data = match.group(0)
        try:
            json_object = json.loads(json_data)
            return json_object
        except json.JSONDecodeError:
            return None
    return None


def fix_partial_correct_response(text: str) -> dict:
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

    # Validate the JSON
    try:
        json.loads(json_object)  # Just validate, don't need to keep the parsed result
    except json.JSONDecodeError:
        return {"error": "Failed to parse JSON object"}

    # Return the result as a dictionary with positions
    return {"start": start_pos, "stop": stop_pos, "extracted_json": json_object}


def clean_json(bad_json_str):
    """
    Clean JSON string by replacing single quotes with double quotes

    """
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


# def data_to_html(data, replace_new_lines=False):
#     if "edsl_version" in data:
#         _ = data.pop("edsl_version")
#     if "edsl_class_name" in data:
#         _ = data.pop("edsl_class_name")

#     from pygments import highlight
#     from pygments.lexers import JsonLexer
#     from pygments.formatters import HtmlFormatter
#     from IPython.display import HTML

#     json_str = json.dumps(data, indent=4, cls=CustomEncoder)
#     formatted_json = highlight(
#         json_str,
#         JsonLexer(),
#         HtmlFormatter(style="default", full=False, noclasses=False),
#     )
#     if replace_new_lines:
#         formatted_json = formatted_json.replace("\\n", "<br>")

#     return HTML(formatted_json).data


def is_gzipped(file_path):
    """Check if a file is gzipped."""
    try:
        with gzip.open(file_path, "rb") as file:
            file.read(1)  # Try reading a small amount of data
        return True
    except OSError:
        return False


def hash_value(value: Union[str, int]) -> str:
    """Hash a string or integer value using SHA-256."""
    if isinstance(value, str):
        value_bytes = value.encode("utf-8")
    elif isinstance(value, int):
        value_bytes = str(value).encode("utf-8")
    else:
        raise ValueError("Hashing supported only for strings or integers.")
    hash_obj = hashlib.sha256(value_bytes)
    return hash_obj.hexdigest()


def repair_json(json_string: str) -> str:
    """Attempt to repair a JSON string that is not valid JSON."""
    json_string = json_string.replace("\n", "\\n").replace("\r", "\\r")
    json_string = json_string.replace("'", "\\'")
    json_string = json_string.replace("'", '"')
    json_string = re.sub(r",\s*}", "}", json_string)
    json_string = re.sub(r",\s*]", "]", json_string)
    json_string = re.sub(r"(?<={|,)\s*([a-zA-Z0-9_]+)\s*:", r'"\1":', json_string)
    return json_string


def dict_to_html(d):
    """Convert a dictionary to an HTML table."""
    # Start the HTML table
    html_table = f'<table border="1">\n<tr><th>{escape("Key")}</th><th>{escape("Value")}</th></tr>\n'

    # Add rows to the HTML table
    for key, value in d.items():
        html_table += (
            f"<tr><td>{escape(str(key))}</td><td>{escape(str(value))}</td></tr>\n"
        )

    # Close the HTML table
    html_table += "</table>"
    return html_table


def is_notebook() -> bool:
    """Check if the code is running in a Jupyter notebook or Google Colab."""
    try:
        shell = get_ipython().__class__.__name__
        if shell == "ZMQInteractiveShell":
            return True  # Jupyter notebook or qtconsole
        elif shell == "Shell":  # Google Colab's shell class
            import sys

            if "google.colab" in sys.modules:
                return True  # Running in Google Colab
            return False
        elif shell == "TerminalInteractiveShell":
            return False  # Terminal running IPython
        else:
            return False  # Other type
    except NameError:
        return False  # Probably standard Python interpreter


def file_notice(file_name):
    """Print a notice about the file being created."""
    from ..display import file_notice as display_file_notice
    display_file_notice(file_name, link_text="Download file")


class HTMLSnippet(str):
    """Create an object with html content (`value`).

    `view` method allows you to view the html content in a web browser.
    """

    def __init__(self, value):
        """Initialize the HTMLSnippet object."""
        super().__init__()
        self.value = value

    def view(self):
        """View the HTML content in a web browser."""
        html_content = self.value

        # create a tempfile to write the HTML content
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".html") as f:
            f.write(html_content)

        # open the HTML tempfile in the default web browser
        webbrowser.open(f"file://{os.path.realpath(f.name)}")


def random_string() -> str:
    """Generate a random string of fixed length."""
    return "".join(random.choice(string.ascii_letters) for i in range(10))


def shortname_proposal(question, max_length=None):
    """Take a question text and generate a slug."""
    question = question.lower()
    tokens = question.split()
    stopwords = set(
        [
            "is",
            "your",
            "who",
            "the",
            "a",
            "an",
            "of",
            "could",
            "you",
            "what",
            "when",
            "where",
            "why",
            "in",
            "and",
            "to",
            "how",
            "are",
            "what",
        ]
    )
    filtered_tokens = [
        token.strip(string.punctuation) for token in tokens if token not in stopwords
    ]
    heading = "_".join(filtered_tokens)
    # Limit length if needed
    if max_length and len(heading) > max_length:
        heading = heading[:max_length]
    while heading.endswith("_"):  # trim any trailing _ characters
        heading = heading[:-1]
    return heading


def text_to_shortname(long_text, forbidden_names=[]):
    """Create a slug for the question."""
    proposed_name = shortname_proposal(long_text)
    counter = 1
    # make sure the name is unique
    while proposed_name in forbidden_names:
        proposed_name += f"_{counter}"
        counter += 1
    return proposed_name


def merge_dicts(dict_list):
    """Merge a list of dictionaries into a single dictionary."""
    result = {}
    all_keys = set()
    for d in dict_list:
        all_keys.update(d.keys())
    for key in all_keys:
        result[key] = [d.get(key, None) for d in dict_list]
    return result

# Note: extract_json_from_string is already defined above (line 58)


def valid_json(json_string):
    """Check if a string is valid JSON."""
    try:
        _ = json.loads(json_string)
        return True
    except json.JSONDecodeError:
        return False


def is_valid_variable_name(name, allow_name=True):
    """Check if a string is a valid variable name."""
    if allow_name:
        return name.isidentifier() and not keyword.iskeyword(name)
    else:
        return (
            name.isidentifier() and not keyword.iskeyword(name) and not name == "name"
        )


def create_valid_var_name(s, transform_func: Callable = lambda x: x.lower()) -> str:
    """Create a valid variable name from a string."""
    if transform_func is None:
        def identity(x):
            return x
        transform_func = identity

    # Ensure the string is not empty
    if not s:
        raise ValueError("Input string cannot be empty.")

    if is_valid_variable_name(s):
        return transform_func(s)

    # Remove leading numbers if they exist since variable names can't start with a number
    s = re.sub("^[0-9]+", "", s)

    # Replace invalid characters (anything not a letter, number, or underscore) with an underscore
    s = re.sub("[^0-9a-zA-Z_]", "_", s)

    # Check if the first character is a number; if so, prepend an underscore
    if re.match("^[0-9]", s):
        s = "_" + s

    if s in keyword.kwlist:
        s += "_"

    # Ensure the string is not empty after the transformations
    if not s:
        raise ValueError(
            "Input string does not contain valid characters for a variable name."
        )

    return transform_func(s)


def shorten_string(s, max_length, placeholder="..."):
    """Shorten a string to a maximum length by removing characters from the middle."""
    if len(s) <= max_length:
        return s

    # Length to be removed
    remove_length = len(s) - max_length + len(placeholder)

    # Find the indices to start and end removal
    start_remove = (len(s) - remove_length) // 2
    end_remove = start_remove + remove_length

    # Adjust start and end to break at spaces (if possible)
    start_space = s.rfind(" ", 0, start_remove)
    end_space = s.find(" ", end_remove)

    if start_space != -1 and end_space != -1:
        start_remove = start_space
        end_remove = end_space
    elif start_space != -1:
        start_remove = start_space
    elif end_space != -1:
        end_remove = end_space

    return s[:start_remove] + placeholder + s[end_remove:]


def write_api_key_to_env(api_key: str) -> str:
    """
    Write the user's Expected Parrot key to their .env file.

    If a .env file doesn't exist in the current directory, one will be created.

    Returns a string representing the absolute path to the .env file.
    """
    from pathlib import Path
    from dotenv import set_key

    # Create .env file if it doesn't exist
    env_path = ".env"
    env_file = Path(env_path)
    env_file.touch(exist_ok=True)

    # Write API key to file
    set_key(env_path, "EXPECTED_PARROT_API_KEY", str(api_key))

    absolute_path_to_env = env_file.absolute().as_posix()

    return absolute_path_to_env
