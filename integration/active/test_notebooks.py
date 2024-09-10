import os
import pytest
import glob

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


def get_notebooks(directory="docs/notebooks"):
    # Use glob to find all .ipynb files in the specified directory
    notebook_pattern = os.path.join(directory, "*.ipynb")
    notebooks = glob.glob(notebook_pattern)

    # Sort the notebooks alphabetically
    notebooks.sort()

    return notebooks


@pytest.mark.parametrize("notebook_path", get_notebooks())
def test_notebook_execution(notebook_path):
    """
    Test function that executes each Jupyter notebook and checks for exceptions.
    """
    print(f"Executing {notebook_path}...")
    execute_notebook(notebook_path)


if __name__ == "__main__":
    pytest.main([__file__])
