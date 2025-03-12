"""Utility functions for string manipulation."""

import keyword
import random
import re
import string
from typing import Callable


def random_string(length=10) -> str:
    """Generate a random string of fixed length."""
    return "".join(random.choice(string.ascii_letters) for i in range(length))


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
        transform_func = lambda x: x

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


def sanitize_string(s):
    """Sanitize a string by removing invalid characters."""
    # Replace invalid characters with underscore
    return re.sub(r"[^a-zA-Z0-9_]", "_", s)


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