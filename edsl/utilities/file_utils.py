"""Utility functions for file operations."""

import gzip
import hashlib
import os
import tempfile
import webbrowser
from pathlib import Path
from typing import Union

from .notebook_utils import is_notebook


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


def file_notice(file_name):
    """Print a notice about the file being created."""
    if is_notebook():
        from IPython.display import HTML, display

        link_text = "Download file"
        display(
            HTML(
                f'<p>File created: {file_name}</p>.<a href="{file_name}" download>{link_text}</a>'
            )
        )
    else:
        print(f"File created: {file_name}")


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


def write_api_key_to_env(api_key: str) -> str:
    """
    Write the user's Expected Parrot key to their .env file.

    If a .env file doesn't exist in the current directory, one will be created.

    Returns a string representing the absolute path to the .env file.
    """
    try:
        from dotenv import set_key
    except ImportError:
        raise ImportError("The python-dotenv package is required. Install it with 'pip install python-dotenv'")

    # Create .env file if it doesn't exist
    env_path = ".env"
    env_file = Path(env_path)
    env_file.touch(exist_ok=True)

    # Write API key to file
    set_key(env_path, "EXPECTED_PARROT_API_KEY", str(api_key))

    absolute_path_to_env = env_file.absolute().as_posix()

    return absolute_path_to_env