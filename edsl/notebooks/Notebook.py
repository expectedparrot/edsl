"""A Notebook is ...."""

import json
import nbformat

from nbconvert import HTMLExporter
from typing import Dict, List, Optional
from rich.table import Table
from edsl.Base import Base
from edsl.utilities.decorators import (
    add_edsl_version,
    remove_edsl_version,
)


class Notebook(Base):
    """
    A Notebook is a utility class that allows you to easily share/pull ipynbs from Coop.
    """

    default_name = "notebook"

    def __init__(
        self,
        data: Optional[Dict] = None,
        path: Optional[str] = None,
        name: Optional[str] = None,
    ):
        """
        Initialize a new Notebook.
        - if a path is provided, try to load the notebook from that path.
        - if no path is provided, assume this code is run in a notebook and try to load the current notebook.
        """
        if data is not None:
            nbformat.validate(data)
            self.data = data
        elif path is not None:
            # TO BE IMPLEMENTED
            # store in this var the data from the notebook
            with open(path, mode="r", encoding="utf-8") as f:
                data = nbformat.read(f, as_version=4)
            self.data = json.loads(json.dumps(data))
        else:
            # TO BE IMPLEMENTED
            # 1. Check you're in a notebook ...
            # 2. get its info and store it in self.data
            # RI: Working on this
            self.data = {"some": "data"}

        # deprioritize - perhaps add sanity check function
        # 1. could check if the notebook is a valid notebook
        # 2. could check notebook uses EDSL
        # ....

        self.name = name or self.default_name

    def __eq__(self, other):
        """
        Check if two Notebooks are equal.
        This should maybe only check the cells and not the metadata/nbformat?
        """
        return self.data == other.data

    @add_edsl_version
    def to_dict(self) -> dict:
        """
        Convert to a dictionary.
        AF: here you will create a dict from which self.from_dict can recreate the object.
        AF: the decorator will add the edsl_version to the dict.
        """
        return {"name": self.name, "data": self.data}

    @classmethod
    @remove_edsl_version
    def from_dict(cls, d: Dict) -> "Notebook":
        """
        Convert a dictionary representation of a Notebook to a Notebook object.
        """
        return cls(data=d["data"], name=d["name"])

    def to_file(self, path: str):
        """
        Saves the notebook at the specified filepath.
        RI: Maybe you want to download a notebook to your local machine
        to work with it?
        """
        nbformat.write(nbformat.from_dict(self.data), fp=path)

    def print(self):
        """
        Print the notebook.
        AF: not sure how this should behave for a notebook
        """
        from rich import print_json
        import json

        print_json(json.dumps(self.to_dict()))

    def __repr__(self):
        """
        AF: not sure how this should behave for a notebook
        """
        return f'Notebook(data={self.data}, name="""{self.name}""")'

    def _repr_html_(self):
        """
        AF: not sure how this should behave for a notebook
        """
        notebook = nbformat.from_dict(self.data)
        html_exporter = HTMLExporter(template_name="basic")
        (body, _) = html_exporter.from_notebook_node(notebook)
        return body

    def _table(self) -> tuple[dict, list]:
        """Prepare generic table data."""
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
        AF: not sure how we should implement this for a notebook
        """
        table_data, column_names = self._table()
        table = Table(title=f"{self.__class__.__name__} Attributes")
        for column in column_names:
            table.add_column(column, style="bold")

        for row in table_data:
            row_data = [row[column] for column in column_names]
            table.add_row(*row_data)

        return table

    @classmethod
    def example(cls) -> "Notebook":
        """
        Return an example Notebook.
        AF: add a simple custom example here
        """
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
                        "text": "Hello world!\n",
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
        return cls(data=data)

    def code(self) -> List[str]:
        """
        Return the code that could be used to create this Notebook.
        AF: Again, not sure
        """
        lines = []
        lines.append("from edsl import Notebook")
        lines.append(f'nb = Notebook(data={self.data}, name="""{self.name}""")')
        return lines


if __name__ == "__main__":
    from edsl.notebooks import Notebook

    notebook = Notebook.example()
    assert notebook == notebook.from_dict(notebook.to_dict())
