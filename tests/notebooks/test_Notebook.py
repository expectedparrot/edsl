import pytest

from edsl.notebooks.Notebook import Notebook
from jsonschema.exceptions import ValidationError
from nbformat.reader import NotJSONError
from nbformat.validator import NotebookValidationError

valid_data = {
    "metadata": dict(),
    "nbformat": 4,
    "nbformat_minor": 4,
    "cells": [
        {
            "cell_type": "markdown",
            "metadata": dict(),
            "source": "# Test notebook",
        },
        {
            "cell_type": "code",
            "execution_count": 1,
            "metadata": dict(),
            "outputs": [
                {
                    "name": "stdout",
                    "output_type": "stream",
                    "text": "Hello world!\n",
                }
            ],
            "source": 'print("Hello world!")',
        },
    ],
}


def test_notebook_creation_from_data_valid():
    """Test that a notebook can be created with valid arguments."""

    # Test default name
    notebook_dict = {"data": valid_data}
    notebook = Notebook(**notebook_dict)
    assert notebook.name == Notebook.default_name
    # Test custom name
    assert notebook.data == notebook_dict.get("data")
    notebook_dict = {"name": "test_notebook", "data": valid_data}
    notebook = Notebook(**notebook_dict)
    assert notebook.name == notebook_dict.get("name")
    assert notebook.data == notebook_dict.get("data")
    # Test custom name with apostrophe
    notebook_dict = {"name": "It's a Test Notebook", "data": valid_data}
    notebook = Notebook(**notebook_dict)
    assert notebook.name == notebook_dict.get("name")
    assert notebook.data == notebook_dict.get("data")


def test_notebook_creation_from_data_invalid():
    """Test that invalid data raises a NotebookValidationError."""

    from copy import deepcopy

    # Missing cells
    with pytest.raises(NotebookValidationError):
        invalid_data = valid_data.copy()
        invalid_data.pop("cells")
        notebook = Notebook(data=invalid_data)
    # Missing metadata
    with pytest.raises(NotebookValidationError):
        invalid_data = valid_data.copy()
        invalid_data.pop("metadata")
        notebook = Notebook(data=invalid_data)
    # Missing cell_type for first cell
    with pytest.raises(NotebookValidationError):
        invalid_dict = deepcopy(valid_data)
        invalid_dict["cells"][0].pop("cell_type")
        notebook = Notebook(data=invalid_data)


def test_notebook_creation_from_path_valid():
    """Tests that a notebook can be created from a filepath."""
    from edsl import Notebook

    notebook = Notebook("docs/notebooks/starter_tutorial.ipynb")
    assert notebook.data["nbformat"] == 4
    assert notebook.data["nbformat_minor"] == 5
    assert notebook.data["cells"][0]["cell_type"] == "markdown"

    notebook = Notebook(path="docs/notebooks/starter_tutorial.ipynb")
    assert notebook.data["nbformat"] == 4
    assert notebook.data["nbformat_minor"] == 5
    assert notebook.data["cells"][0]["cell_type"] == "markdown"


def test_notebook_creation_from_path_invalid():
    """Tests that creating a notebook from an invalid filepath raises an error."""

    # No such file
    with pytest.raises(FileNotFoundError):
        notebook = Notebook("docs/notebooks/invalid_path_to_starter_tutorial.ipynb")
    # File exists, but is not JSON
    with pytest.raises(NotJSONError):
        notebook = Notebook("docs/agents.rst")
    # No path - not implemented in environments other than VS Code
    with pytest.raises(NotImplementedError):
        notebook = Notebook()


def test_notebook_equality():
    """Tests the equality of notebook data."""

    # Test equality (only checks data, not name)
    notebook1 = Notebook.example()
    notebook2 = Notebook(data=valid_data, name="second_notebook")
    assert notebook1 == notebook2


def test_notebook_serialization():
    """Tests notebook serialization."""

    notebook = Notebook(data=valid_data)
    notebook2 = Notebook.from_dict(notebook.to_dict())
    assert isinstance(notebook, Notebook)
    assert type(notebook) == type(notebook2)
    assert repr(notebook) == repr(notebook2)

    # Serialization of invalid data raises an error
    with pytest.raises(NotebookValidationError):
        invalid_data = valid_data.copy()
        invalid_data.pop("metadata")
        notebook_dict = {"data": invalid_data, "name": "test_notebook"}
        notebook = Notebook.from_dict(notebook_dict)
    with pytest.raises(ValidationError):
        invalid_data = valid_data.copy()
        invalid_data.pop("nbformat")
        notebook_dict = {"data": invalid_data, "name": "test_notebook"}
        notebook = Notebook.from_dict(notebook_dict)
    with pytest.raises(KeyError):
        invalid_data = {"some": "data"}
        notebook = Notebook.from_dict(invalid_data)


def test_notebook_code():
    """Tests notebook code."""

    notebook = Notebook.example()
    code = [
        "from edsl import Notebook",
        "nb = Notebook(data={'metadata': {}, 'nbformat': 4, 'nbformat_minor': 4, 'cells': [{'cell_type': 'markdown', 'metadata': {}, 'source': '# Test notebook'}, {'cell_type': 'code', 'execution_count': 1, 'metadata': {}, 'outputs': [{'name': 'stdout', 'output_type': 'stream', 'text': 'Hello world!\\n'}], 'source': 'print(\"Hello world!\")'}]}, name=\"\"\"notebook\"\"\")",
    ]
    assert code == notebook.code()
