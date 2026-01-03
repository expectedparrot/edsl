"""A Notebook is a utility class that allows you to easily share/pull ipynbs from Coop."""

from __future__ import annotations
import json
import subprocess
import tempfile
import os
import shutil
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from rich.table import Table
from uuid import uuid4

from ..base import Base
from ..utilities.decorators import remove_edsl_version


class Notebook(Base):
    """
    A Notebook is a utility class that allows you to easily share/pull ipynbs from Coop.
    """

    default_name = "notebook"

    @staticmethod
    def _lint_code(code: str) -> str:
        """
        Lint Python code using ruff.

        :param code: The Python code to lint
        :return: The linted code
        """
        try:
            # Check if ruff is installed
            if shutil.which("ruff") is None:
                # If ruff is not installed, return original code
                return code

            with tempfile.NamedTemporaryFile(
                mode="w+", suffix=".py", delete=False
            ) as temp_file:
                temp_file.write(code)
                temp_file_path = temp_file.name

            # Run ruff to format the code
            try:
                result = subprocess.run(
                    ["ruff", "format", temp_file_path],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                # Read the formatted code
                with open(temp_file_path, "r") as f:
                    linted_code = f.read()

                return linted_code
            except subprocess.CalledProcessError:
                # If ruff fails, return the original code
                return code
            except FileNotFoundError:
                # If ruff is not installed, return the original code
                return code
        finally:
            # Clean up temporary file
            if "temp_file_path" in locals() and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    def __init__(
        self,
        path: Optional[str] = None,
        data: Optional[Dict] = None,
        name: Optional[str] = None,
        lint: bool = True,
    ):
        """
        Initialize a new Notebook.

        :param data: A dictionary representing the notebook data.
        This dictionary must conform to the official Jupyter Notebook format, as defined by nbformat.
        Cell outputs (including Altair charts, plots, and other visualizations) are preserved.
        :param path: A filepath from which to load the notebook.
        If no path is provided, assume this code is run in a notebook and try to load the current notebook from file.
        :param name: A name for the Notebook.
        :param lint: Whether to lint Python code cells using ruff. Defaults to True.

        Note: When loading from a file, make sure the notebook has been saved after executing cells
        to ensure all outputs (especially graphics) are captured. Jupyter only saves cell outputs
        to the .ipynb file when you save the notebook.
        """
        import nbformat

        # Load current notebook path as fallback (VS Code only)
        current_notebook_path = globals().get("__vsc_ipynb_file__")

        # Store the source path for potential reloading
        self._source_path = None

        if path is not None:
            self._source_path = path
            with open(path, mode="r", encoding="utf-8") as f:
                data = nbformat.read(f, as_version=4)
            self.data = json.loads(json.dumps(data))
        elif data is not None:
            nbformat.validate(data)
            self.data = data
        elif current_notebook_path is not None:
            self._source_path = current_notebook_path
            with open(current_notebook_path, mode="r", encoding="utf-8") as f:
                data = nbformat.read(f, as_version=4)
            self.data = json.loads(json.dumps(data))
        else:
            # TODO: Support for IDEs other than VSCode
            from .exceptions import NotebookEnvironmentError

            raise NotebookEnvironmentError(
                "Cannot create a notebook from within itself in this development environment"
            )

        # Store the lint parameter
        self.lint = lint

        # Apply linting to code cells if enabled
        if self.lint and self.data and "cells" in self.data:
            for cell in self.data["cells"]:
                if cell.get("cell_type") == "code" and "source" in cell:
                    # Only lint Python code cells
                    cell["source"] = self._lint_code(cell["source"])

        # TODO: perhaps add sanity check function
        # 1. could check if the notebook is a valid notebook
        # 2. could check notebook uses EDSL
        # ....

        self.name = name or self.default_name

    @classmethod
    def from_script(
        cls, path: str, name: Optional[str] = None, lint: bool = True
    ) -> "Notebook":
        import nbformat

        # Read the script file
        with open(path, "r") as script_file:
            script_content = script_file.read()

        # Create a new Jupyter notebook
        nb = nbformat.v4.new_notebook()

        # Add the script content to the first cell
        first_cell = nbformat.v4.new_code_cell(script_content)
        nb.cells.append(first_cell)

        # Create a Notebook instance with the notebook data
        notebook_instance = cls(data=nb, name=name, lint=lint)

        return notebook_instance

    def generate_description(self) -> str:
        """Generate a description of the notebook."""
        from ..questions import QuestionFreeText

        notebook_content = ""
        for cell in self.data["cells"]:
            if "source" in cell:
                notebook_content += cell["source"]
        q = QuestionFreeText(
            question_text=f"What is a good one sentence description of this notebook? The content is {notebook_content}",
            question_name="description",
        )
        results = q.run(verbose=False)
        return results.select("answer.description").first()

    @classmethod
    def from_current_script(cls, lint: bool = True) -> "Notebook":
        import inspect
        import os

        # Get the path to the current file
        current_frame = inspect.currentframe()
        caller_frame = inspect.getouterframes(current_frame, 2)
        current_file_path = os.path.abspath(caller_frame[1].filename)

        # Use from_script to create the notebook
        return cls.from_script(current_file_path, lint=lint)

    def __eq__(self, other):
        """
        Check if two Notebooks are equal.
        This only checks the notebook data.
        """
        return self.data == other.data

    def __hash__(self) -> int:
        """
        Allow the model to be used as a key in a dictionary.
        """
        from ..utilities.utilities import dict_hash

        return dict_hash(self.data["cells"])

    def reload(self) -> None:
        """
        Reload the notebook data from the source file.

        This is useful when you've executed cells and saved the notebook,
        and want to pick up the new outputs (like Altair charts) without
        creating a new Notebook object.

        :raises ValueError: If the notebook was not loaded from a file

        Example:
            >>> nb = Notebook()  # Load current notebook
            >>> # ... execute cells and save notebook ...
            >>> nb.reload()  # Pick up new outputs
            >>> nb.push()  # Now push with outputs included
        """
        import nbformat

        if self._source_path is None:
            raise ValueError(
                "Cannot reload: this notebook was not loaded from a file. "
                "Only notebooks created with a path or from the current notebook can be reloaded."
            )

        # Reload from the source file
        with open(self._source_path, mode="r", encoding="utf-8") as f:
            data = nbformat.read(f, as_version=4)
        self.data = json.loads(json.dumps(data))

        # Re-apply linting if enabled
        if self.lint and self.data and "cells" in self.data:
            for cell in self.data["cells"]:
                if cell.get("cell_type") == "code" and "source" in cell:
                    cell["source"] = self._lint_code(cell["source"])

    def has_outputs(self) -> bool:
        """
        Check if the notebook has any cell outputs.

        :return: True if at least one code cell has outputs, False otherwise
        """
        if not self.data or "cells" not in self.data:
            return False

        for cell in self.data["cells"]:
            if cell.get("cell_type") == "code" and cell.get("outputs"):
                return True
        return False

    def push(
        self,
        description: Optional[str] = None,
        alias: Optional[str] = None,
        visibility: Optional[str] = "private",
        expected_parrot_url: Optional[str] = None,
    ) -> dict:
        """
        Push the notebook to Coop.

        Note: Make sure to save your notebook before pushing to ensure all cell outputs
        (including Altair charts and other visualizations) are included. If the notebook
        hasn't been saved after executing cells, the outputs won't be captured.

        :param description: Optional description for the notebook
        :param alias: Optional alias for the notebook
        :param visibility: Visibility setting (default: "private")
        :param expected_parrot_url: Optional custom URL for the coop service
        :return: Response dictionary from the push operation
        """
        import warnings

        # Warn if notebook appears to have no outputs
        if not self.has_outputs():
            warnings.warn(
                "This notebook does not appear to have any cell outputs. "
                "If you have executed cells with outputs (like Altair charts), "
                "make sure to save the notebook file before creating the Notebook object. "
                "Cell outputs are only captured when the notebook file is saved.",
                UserWarning,
                stacklevel=2,
            )

        # Call the parent class push method
        return super().push(description, alias, visibility, expected_parrot_url)

    def to_dict(self, add_edsl_version=False) -> dict:
        """
        Serialize to a dictionary.
        """
        d = {"name": self.name, "data": self.data, "lint": self.lint}
        if add_edsl_version:
            from .. import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = self.__class__.__name__
        return d

    @classmethod
    @remove_edsl_version
    def from_dict(cls, d: Dict, lint: bool = None) -> "Notebook":
        """
        Convert a dictionary representation of a Notebook to a Notebook object.

        :param d: Dictionary containing notebook data and name
        :param lint: Whether to lint Python code cells. If None, uses the value from the dictionary or defaults to True.
        :return: A new Notebook instance
        """
        # Use the lint parameter from the dictionary if none is provided, otherwise default to True
        notebook_lint = lint if lint is not None else d.get("lint", True)
        return cls(data=d["data"], name=d["name"], lint=notebook_lint)

    def to_file(self, path: str):
        """
        Save the notebook at the specified filepath.
        """
        import nbformat

        nbformat.write(nbformat.from_dict(self.data), fp=path)

    def __repr__(self):
        """
        Return representation of Notebook.
        """
        return f'Notebook(data={self.data}, name="""{self.name}""")'

    def _repr_html_(self):
        """
        Return HTML representation of Notebook.
        """
        from nbconvert import HTMLExporter
        import nbformat

        notebook = nbformat.from_dict(self.data)
        html_exporter = HTMLExporter(template_name="basic")
        (body, _) = html_exporter.from_notebook_node(notebook)
        return body

    def _table(self) -> tuple[dict, list]:
        """
        Prepare generic table data.
        """
        table_data = []

        notebook_preview = ""
        for cell in self.data["cells"]:
            if "source" in cell:
                notebook_preview += f"{cell['source']}\n"
            if len(notebook_preview) > 1000:
                notebook_preview = f"{notebook_preview[:1000]} [...]"
                break
        notebook_preview = notebook_preview.rstrip()

        table_data.append(
            {
                "Attribute": "name",
                "Value": repr(self.name),
            }
        )
        table_data.append(
            {
                "Attribute": "notebook_preview",
                "Value": notebook_preview,
            }
        )

        column_names = ["Attribute", "Value"]
        return table_data, column_names

    def rich_print(self) -> "Table":
        """
        Display a Notebook as a rich table.
        """
        from rich.table import Table

        table_data, column_names = self._table()
        table = Table(title=f"{self.__class__.__name__} Attributes")
        for column in column_names:
            table.add_column(column, style="bold")

        for row in table_data:
            row_data = [row[column] for column in column_names]
            table.add_row(*row_data)

        return table

    @classmethod
    def example(cls, randomize: bool = False, lint: bool = True) -> Notebook:
        """
        Returns an example Notebook instance.

        :param randomize: If True, adds a random string one of the cells' output.
        :param lint: Whether to lint Python code cells. Defaults to True.
        :return: An example Notebook instance
        """
        addition = "" if not randomize else str(uuid4())
        cells = [
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
                        "text": f"Hello world!\n{addition}",
                    }
                ],
                "source": 'print("Hello world!")',
            },
        ]
        data = {
            "metadata": dict(),
            "nbformat": 4,
            "nbformat_minor": 4,
            "cells": cells,
        }
        return cls(data=data, lint=lint)

    def code(self) -> List[str]:
        """
        Return the code that could be used to create this Notebook.
        """
        lines = []
        lines.append(
            "from edsl import Notebook"
        )  # Keep as absolute for code generation
        lines.append(
            f'nb = Notebook(data={self.data}, name="""{self.name}""", lint={self.lint})'
        )
        return lines

    def to_latex(self, filename: str):
        """
        Convert notebook to LaTeX and create a folder with all necessary components.

        :param filename: Name of the output folder and main tex file (without extension)
        """
        from .notebook_to_latex import NotebookToLaTeX

        NotebookToLaTeX(self).convert(filename)

    def _eval_repr_(self) -> str:
        """Return an eval-able string representation of the Notebook."""
        return f'Notebook(data={self.data}, name="""{self.name}""", lint={self.lint})'

    def _summary_repr(self) -> str:
        """Generate a summary representation of the Notebook with Rich formatting."""
        notebook_preview = ""
        for cell in self.data["cells"]:
            if "source" in cell:
                notebook_preview += f"{cell['source']}\n"
            if len(notebook_preview) > 200:
                notebook_preview = f"{notebook_preview[:200]} [...]"
                break
        notebook_preview = notebook_preview.rstrip()
        return f"Notebook(name={self.name!r}, cells={len(self.data.get('cells', []))}, preview={notebook_preview!r})"


if __name__ == "__main__":
    from .. import Notebook

    notebook = Notebook.example()
    assert notebook == notebook.from_dict(notebook.to_dict())
