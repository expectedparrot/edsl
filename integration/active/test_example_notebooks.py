import os
import pytest
import nbformat
from nbconvert.preprocessors import ExecutePreprocessor, CellExecutionError


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


full_list = [
    "docs/notebooks/critique_questions.ipynb",
    "docs/notebooks/hiring_interviews.ipynb",  # no good - onet db broken
    "docs/notebooks/adding_metadata.ipynb",  # works
    "docs/notebooks/analyze_evaluations.ipynb",  # works
]


@pytest.mark.parametrize(
    "notebook_path",
    ["docs/notebooks/hiring_interviews.ipynb"],
    # [
    #     os.path.join(dirpath, f)
    #     for dirpath, _, files in os.walk("integration/notebooks")  # Update this path
    #     for f in files
    #     if f.endswith(".ipynb")
    # ]
    # + ,
)
def test_notebook_execution(notebook_path):
    """
    Test function that executes each Jupyter notebook found in the directory, and checks for exceptions.
    """
    print(f"Executing {notebook_path}...")
    execute_notebook(notebook_path)
