"""A Scenario is a dictionary with a key/value to parameterize a question."""
import copy
from collections import UserDict
from rich.table import Table
from typing import Union, List
import base64

from edsl.Base import Base

from edsl.scenarios.ScenarioImageMixin import ScenarioImageMixin
from edsl.scenarios.ScenarioHtmlMixin import ScenarioHtmlMixin

from edsl.utilities.decorators import (
    add_edsl_version,
    remove_edsl_version,
)


class Scenario(Base, UserDict, ScenarioImageMixin, ScenarioHtmlMixin):
    """A Scenario is a dictionary of keys/values for parameterizing questions."""

    def __init__(self, data: Union[dict, None] = None, name: str = None):
        """Initialize a new Scenario.

        :param data: A dictionary of keys/values for parameterizing questions.
        """
        if data is None:
            data = {}
        self.data = data
        self.name = name

    @property
    def has_image(self) -> bool:
        """Return whether the scenario has an image."""
        if not hasattr(self, "_has_image"):
            self._has_image = False
        return self._has_image

    @has_image.setter
    def has_image(self, value):
        self._has_image = value

    def __add__(self, other_scenario: "Scenario") -> "Scenario":
        """Combine two scenarios.

        If the other scenario is None, then just return self.

        :param other_scenario: The other scenario to combine with.

        Example:
        Here are some examples of usage.

        >>> s1 = Scenario({"price": 100, "quantity": 2})
        >>> s2 = Scenario({"color": "red"})
        >>> s1 + s2
        Scenario({'price': 100, 'quantity': 2, 'color': 'red'})
        >>> (s1 + s2).__class__.__name__
        'Scenario'
        """
        if other_scenario is None:
            return self
        else:
            data1 = copy.deepcopy(self.data)
            data2 = copy.deepcopy(other_scenario.data)
            s = Scenario(data1 | data2)
            if self.has_image or other_scenario.has_image:
                s._has_image = True
            return s

    def rename(self, replacement_dict: dict) -> "Scenario":
        """Rename the keys of a scenario.

        :param replacement_dict: A dictionary of old keys to new keys.

        Examples:
        This renames a key in a scenario.

        >>> s = Scenario({"food": "wood chips"})
        >>> s.rename({"food": "food_preference"})
        Scenario({'food_preference': 'wood chips'})
        """
        new_scenario = Scenario()
        for key, value in self.items():
            if key in replacement_dict:
                new_scenario[replacement_dict[key]] = value
            else:
                new_scenario[key] = value
        return new_scenario

    @add_edsl_version
    def to_dict(self) -> dict:
        """Convert a scenario to a dictionary.

        >>> s = Scenario({"food": "wood chips"})
        >>> s.to_dict()
        {'food': 'wood chips', 'edsl_version': '...', 'edsl_class_name': 'Scenario'}
        """
        return self.data

    def print(self):
        from rich import print_json
        import json

        print_json(json.dumps(self.to_dict()))

    def __repr__(self):
        return "Scenario(" + repr(self.data) + ")"

    def _repr_html_(self):
        from edsl.utilities.utilities import data_to_html

        return data_to_html(self.to_dict())

    @classmethod
    def from_image(cls, image_path: str) -> str:
        """Creates a scenario with a base64 encoding of an image.

        >>> s = Scenario.from_image(Scenario.example_image())
        >>> s
        Scenario({'file_path': '...', 'encoded_image': '...'})
        """

        with open(image_path, "rb") as image_file:
            s = cls(
                {
                    "file_path": image_path,
                    "encoded_image": base64.b64encode(image_file.read()).decode(
                        "utf-8"
                    ),
                }
            )
            s.has_image = True
            return s
        
    def chunk(self, field, chunk_size):
        """Split a field into chunks of a given size.

        :param field: The field to split.
        :param chunk_size: The size of each chunk, in characters.
        
        TODO: Add more chunking options, like splitting by words or lines

        Examples:
        This splits a field into chunks.

        >>> s = Scenario({"text": "This is a test."})
        >>> s.chunk("text", 4)
        ScenarioList([Scenario({'text': 'This', 'text_chunk': 0}), Scenario({'text': ' is ', 'text_chunk': 1}), Scenario({'text': 'a te', 'text_chunk': 2}), Scenario({'text': 'st.', 'text_chunk': 3})])
        """
        from edsl.scenarios.ScenarioList import ScenarioList
        new_scenario = Scenario()
        new_scenario.data = copy.deepcopy(self.data)
        chunks = [
            self[field][i : i + chunk_size]
            for i in range(0, len(self[field]), chunk_size)
        ]
        scenarios = []
        for i, chunk in enumerate(chunks):
            new_scenario = copy.deepcopy(self)
            new_scenario[field] = chunk
            new_scenario[field + "_chunk"] = i
            scenarios.append(new_scenario)
        return ScenarioList(scenarios)


    @classmethod
    @remove_edsl_version
    def from_dict(cls, d: dict) -> "Scenario":
        """Convert a dictionary to a scenario.

        >>> Scenario.from_dict({"food": "wood chips"})
        Scenario({'food': 'wood chips'})
        """
        return cls(d)

    def _table(self) -> tuple[dict, list]:
        """Prepare generic table data."""
        table_data = []
        for attr_name, attr_value in self.__dict__.items():
            table_data.append({"Attribute": attr_name, "Value": repr(attr_value)})
        column_names = ["Attribute", "Value"]
        return table_data, column_names

    def rich_print(self) -> "Table":
        """Display an object as a rich table."""
        table_data, column_names = self._table()
        table = Table(title=f"{self.__class__.__name__} Attributes")
        for column in column_names:
            table.add_column(column, style="bold")

        for row in table_data:
            row_data = [row[column] for column in column_names]
            table.add_row(*row_data)

        return table

    @classmethod
    def example(cls) -> "Scenario":
        """Return an example scenario.

        >>> Scenario.example()
        Scenario({'persona': 'A reseacher studying whether LLMs can be used to generate surveys.'})
        """
        return cls(
            {
                "persona": "A reseacher studying whether LLMs can be used to generate surveys."
            }
        )

    def code(self) -> List[str]:
        """Return the code for the scenario."""
        lines = []
        lines.append("from edsl.scenario import Scenario")
        lines.append(f"s = Scenario({self.data})")
        # return f"Scenario({self.data})"
        return lines


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
