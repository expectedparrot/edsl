import requests
import subprocess
from io import StringIO
import os
import pandas as pd
import warnings
import sys
from collections.abc import Hashable
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console(stderr=True)


def setup_warning_filter():
    """Set up a custom warning filter to display nice Rich-formatted notices."""
    def rich_warning_handler(message, category, filename, lineno, file=None, line=None):
        warning_text = str(message)
        
        # Check if this is the specific EDSL warning we want to format
        if "is already in use. Renaming to" in warning_text:
            # Extract the key name from the warning
            if "Key '" in warning_text:
                key_part = warning_text.split("Key '")[1].split("' of")[0]
                title = f"📝 Column Renamed"
                content = f"The column '[bold cyan]{key_part}[/bold cyan]' was automatically renamed to avoid conflicts."
                style = "blue"
            else:
                title = "📝 Notice"
                content = warning_text
                style = "blue"
        else:
            # Handle other warnings with a generic format
            title = "⚠️  Warning"
            content = warning_text
            style = "yellow"
        
        # Create a rich panel for the warning
        panel = Panel(
            Text(content, style="white"),
            title=title,
            border_style=style,
            padding=(0, 1)
        )
        
        console.print(panel)
    
    # Set the warning handler
    warnings.showwarning = rich_warning_handler


class ValidFilename:
    """A descriptor that checks if a file exists.


    >>> f = ValidFilename()
    >>> f = "hello"
    """

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        return instance.__dict__.get(self.name, None)

    def __set__(self, instance, value):
        if not isinstance(value, str):
            raise ValueError(
                f"The filename must be a string, not {type(value).__name__}"
            )

        if not os.path.exists(value):
            raise ValueError(f"The file '{value}' does not exist.")

        instance.__dict__[self.name] = value


class DummyClassToTestDescriptor:
    """

    >>> d = DummyClassToTestDescriptor(1)
    Traceback (most recent call last):
    ...
    ValueError: The filename must be a string, not int

    >>> d = DummyClassToTestDescriptor("hello")
    Traceback (most recent call last):
    ...
    ValueError: The file 'hello' does not exist.
    """

    filename = ValidFilename()

    def __init__(self, filename):
        self.filename = filename

    def __repr__(self):
        return f"DummyClassToTestDescriptor({self.filename})"


class Missing:
    def __repr__(self):
        return "Missing()"

    def __str__(self):
        return "Missing()"

    def value(self):
        return "missing"


# Cache for convert_value to avoid repeated conversions
_convert_value_cache = {}

def convert_value(x):
    """Takes a string and tries to convert it with caching for performance.

    >>> convert_value('1')
    1
    >>> convert_value('1.2')
    1.2
    >>> convert_value("how are you?")
    'how are you?'
    >>> convert_value("")
    'missing'
    >>> convert_value("nan")
    'missing'
    >>> convert_value("null")
    'missing'

    """
    # Use cache for performance - many duplicate values in surveys
    cacheable = isinstance(x, Hashable)
    if cacheable and x in _convert_value_cache:
        return _convert_value_cache[x]

    # Handle nested collections such as multi-select answers
    if isinstance(x, list):
        result = [convert_value(item) for item in x]
        return result
    
    # Original conversion logic
    try:
        float_val = float(x)
        # Check for NaN or infinite values which are not JSON serializable
        if float_val != float_val or float_val == float('inf') or float_val == float('-inf'):
            result = Missing().value()
        elif float_val.is_integer():
            result = int(float_val)
        else:
            result = float_val
    except (ValueError, TypeError):
        if x is None:
            result = Missing().value()
        else:
            x_str = str(x)
            if len(x_str) == 0:
                result = Missing().value()
            else:
                # Handle common representations of missing values
                if x_str.lower() in ['nan', 'null', 'none', 'n/a']:
                    result = Missing().value()
                else:
                    result = x_str
    
    # Cache the result for future calls
    if cacheable:
        _convert_value_cache[x] = result
    return result


# class RCodeSnippet:
#     def __init__(self, r_code):
#         self.r_code = r_code

#     def __call__(self, data_file_name):
#         return self.run_R_stdin(self.r_code, data_file_name)

#     def __add__(self, other):
#         return RCodeSnippet(self.r_code + other.r_code)

#     def write_to_file(self, filename) -> None:
#         """Writes the R code to a file; useful for debugging."""
#         if filename.endswith(".R") or filename.endswith(".r"):
#             pass
#         else:
#             filename += ".R"

#         with open(filename, "w") as f:
#             f.write(self.r_code)

#     @staticmethod
#     def run_R_stdin(r_code, data_file_name, transform_func=lambda x: pd.read_csv(x)):
#         """Runs an R script and returns the stdout as a string."""
#         cmd = ["Rscript", "-e", r_code, data_file_name]
#         process = subprocess.Popen(
#             cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
#         )
#         stdout, stderr = process.communicate()
#         if stderr != "":
#             print("Warning: stderr is not empty.")
#             print(f"Problem running: {r_code}")
#             raise Exception(stderr)
#         return transform_func(StringIO(stdout))


def infer_question_type(question_text, responses, sample_size=15):
    from edsl.questions import QuestionMultipleChoice

    q = QuestionMultipleChoice(
        question_text="""We have a survey question and we are trying to infer its type.
                        The question text is: '{{question_text}}'.                                   
                        The first {{ sample_size }} responses are: '{{responses}}'.
                        There are {{ total }} responses in total.
                        If a response is a command-separated list, it is likely a checkbox question.
                        """,
        question_name="infer_question_type",
        question_options=[
            "budget",
            "checkbox",
            "extract",
            "free_text",
            "likert_five",
            "linear_scale",
            "list",
            "multiple_choice",
            "numerical",
            "rank",
            "top_k",
            "yes_no",
        ],
    )
    response = (
        q.to_survey()(
            question_text=question_text,
            sample_zize=sample_size,
            responses=responses[:sample_size],
        )
        .select("infer_question_type")
        .first()
    )
    return response


def download_file(url, filename):
    """
    Downloads a file from a given URL and saves it to the specified filename.

    Parameters:
    url (str): The URL of the file to download.
    filename (str): The name of the file to save the downloaded content.

    Returns:
    str: The path to the saved file.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    # Sending the GET request
    response = requests.get(url, headers=headers)

    # Checking if the request was successful
    if response.status_code == 200:
        # Writing the content to the specified file
        with open(filename, "wb") as file:
            file.write(response.content)
        print(f"File downloaded successfully and saved to {filename}")
        return filename
    else:
        print(f"Failed to download file: {response.status_code}")
        return None


# Example usage
if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
