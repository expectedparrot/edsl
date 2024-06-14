"""A Notebook is ...."""

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

    def __init__(self, data: Optional[Dict] = None, path: Optional[str] = None):
        """
        Initialize a new Notebook.
        - if a path is provided, try to load the notebook from that path.
        - if no path is provided, assume this code is run in a notebook and try to load the current notebook.
        """
        if data is not None:
            self.data = data
        elif path is not None:
            # TO BE IMPLEMENTED
            # store in this var the data from the notebook
            self.data = {"some": "data"}
        else:
            # TO BE IMPLEMENTED
            # 1. Check you're in a notebook ...
            # 2. get its info and store it in self.data
            self.data = {"some": "data"}

        # deprioritize - perhaps add sanity check function
        # 1. could check if the notebook is a valid notebook
        # 2. could check notebook uses EDSL
        # ....

    def __eq__(self, other):
        """
        Check if two Notebooks are equal.
        """
        return self.data == other.data

    @add_edsl_version
    def to_dict(self) -> dict:
        """
        Convert to a dictionary.
        AF: here you will create a dict from which self.from_dict can recreate the object.
        AF: the decorator will add the edsl_version to the dict.
        """
        return {"data": self.data}

    @classmethod
    @remove_edsl_version
    def from_dict(cls, d: Dict) -> "Notebook":
        """
        Convert a dictionary representation of a Notebook to a Notebook object.
        """
        return cls(data=d["data"])

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
        return f"Notebook({self.to_dict()})"

    def _repr_html_(self):
        """
        AF: not sure how this should behave for a notebook
        """
        from edsl.utilities.utilities import data_to_html

        return data_to_html(self.to_dict())

    def rich_print(self) -> "Table":
        """
        AF: not sure how we should implement this for a notebook
        """
        pass

    @classmethod
    def example(cls) -> "Notebook":
        """
        Return an example Notebook.
        AF: add a simple custom example here
        """
        return cls(data={"some": "data"})

    def code(self) -> List[str]:
        """
        Return the code that could be used to create this Notebook.
        AF: Again, not sure
        """
        lines = []
        lines.append("from edsl.notebooks import Notebook")
        lines.append(f"s = Notebook({self.data})")
        return lines


if __name__ == "__main__":
    from edsl.notebooks import Notebook

    notebook = Notebook.example()
    assert notebook == notebook.from_dict(notebook.to_dict())
