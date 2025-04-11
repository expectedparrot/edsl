import os
import glob
import csv
import subprocess
from pathlib import Path

import nbformat
from nbconvert.preprocessors import ExecutePreprocessor, CellExecutionError
import pytest


def get_git_hash():
    """
    Get the current git commit hash.
    """
    try:
        result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                              capture_output=True, 
                              text=True, 
                              check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "no_git_hash"


def get_execution_history(history_file='notebook_execution_history.csv'):
    """
    Read the execution history from CSV file.
    Returns a set of (commit_hash, notebook_name) tuples.
    """
    history = set()
    if os.path.exists(history_file):
        with open(history_file, 'r') as f:
            reader = csv.reader(f)
            next(reader, None)  # Skip header
            for row in reader:
                if len(row) == 2:
                    history.add(tuple(row))
    return history


def record_successful_execution(notebook_name, commit_hash, history_file='notebook_execution_history.csv'):
    """
    Record successful notebook execution in the history file.
    """
    file_exists = os.path.exists(history_file)
    with open(history_file, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['commit_hash', 'notebook_name'])
        writer.writerow([commit_hash, notebook_name])


def execute_notebook(notebook_path):
    """
    Execute a Jupyter notebook and either returns True if successful or raises an exception.
    """
    with open(notebook_path) as f:
        nb = nbformat.read(f, as_version=4)
        ep = ExecutePreprocessor(timeout=600, kernel_name="python3")

        try:
            # Attempt to execute the notebook
            ep.preprocess(nb, {"metadata": {"path": os.path.dirname(notebook_path)}})
        except CellExecutionError as cell_error:
            raise AssertionError(f"Execution error in {notebook_path}: {cell_error}")
        except Exception as e:
            raise RuntimeError(f"Error executing the notebook '{notebook_path}': {e}")


def get_notebooks(directory="docs/notebooks", exclude=None):
    # Use glob to find all .ipynb files in the specified directory
    notebook_pattern = os.path.join(directory, "*.ipynb")
    notebooks = glob.glob(notebook_pattern)

    # If exclude is provided, remove the excluded notebooks
    if exclude:
        # Convert exclude to a set for faster lookup
        exclude_set = set(exclude)
        notebooks = [nb for nb in notebooks if os.path.basename(nb) not in exclude_set]

    # Sort the notebooks alphabetically
    notebooks.sort()

    return notebooks


notebooks = get_notebooks()
# Define the list of notebooks
# notebooks = [
#     "docs/notebooks/critique_questions.ipynb",
#     "docs/notebooks/adding_metadata.ipynb",
#     "docs/notebooks/analyze_evaluations.ipynb",
#     "docs/notebooks/comparing_model_responses.ipynb",
#     "docs/notebooks/example_agent_dynamic_traits.ipynb",
# ]


def pytest_generate_tests(metafunc):
    if "notebook_path" in metafunc.fixturenames:
        metafunc.parametrize(
            "notebook_path", notebooks, ids=lambda x: os.path.basename(x)
        )


def test_notebook_execution(notebook_path):
    """
    Test function that executes each Jupyter notebook and checks for exceptions.
    Skips execution if the notebook has already passed for the current commit.
    """
    commit_hash = get_git_hash()
    notebook_name = os.path.basename(notebook_path)
    history = get_execution_history()
    
    if (commit_hash, notebook_name) in history:
        pytest.skip(f"Notebook {notebook_name} already passed for commit {commit_hash}")
    
    print(f"Executing {notebook_path}...")
    execute_notebook(notebook_path)
    
    # Record successful execution
    record_successful_execution(notebook_name, commit_hash)
