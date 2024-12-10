"""A Scenario is a dictionary with a key/value to parameterize a question."""

from __future__ import annotations
import copy
import os
import json
from collections import UserDict
from typing import Union, List, Optional, TYPE_CHECKING
from uuid import uuid4

from edsl.Base import Base
from edsl.scenarios.ScenarioHtmlMixin import ScenarioHtmlMixin
from edsl.utilities.decorators import remove_edsl_version
from edsl.exceptions.scenarios import ScenarioError

if TYPE_CHECKING:
    from edsl.scenarios.ScenarioList import ScenarioList
    from edsl.results.Dataset import Dataset


class DisplayJSON:
    def __init__(self, dict):
        self.text = json.dumps(dict, indent=4)

    def __repr__(self):
        return self.text


class DisplayYAML:
    def __init__(self, dict):
        import yaml

        self.text = yaml.dump(dict)

    def __repr__(self):
        return self.text


class Scenario(Base, UserDict, ScenarioHtmlMixin):
    """A Scenario is a dictionary of keys/values that can be used to parameterize questions."""

    __documentation__ = "https://docs.expectedparrot.com/en/latest/scenarios.html"

    def __init__(self, data: Optional[dict] = None, name: str = None):
        """Initialize a new Scenario.

        :param data: A dictionary of keys/values for parameterizing questions.
        :param name: The name of the scenario.
        """
        if not isinstance(data, dict) and data is not None:
            try:
                data = dict(data)
            except Exception as e:
                raise ScenarioError(
                    f"You must pass in a dictionary to initialize a Scenario. You passed in {data}"
                )

        self.data = data if data is not None else {}
        self.name = name

    def replicate(self, n: int) -> "ScenarioList":
        """Replicate a scenario n times to return a ScenarioList.

        :param n: The number of times to replicate the scenario.

        Example:

        >>> s = Scenario({"food": "wood chips"})
        >>> s.replicate(2)
        ScenarioList([Scenario({'food': 'wood chips'}), Scenario({'food': 'wood chips'})])
        """
        from edsl.scenarios.ScenarioList import ScenarioList

        return ScenarioList([copy.deepcopy(self) for _ in range(n)])

    @property
    def has_jinja_braces(self) -> bool:
        """Return whether the scenario has jinja braces. This matters for rendering.

        >>> s = Scenario({"food": "I love {{wood chips}}"})
        >>> s.has_jinja_braces
        True
        """
        for _, value in self.items():
            if isinstance(value, str):
                if "{{" in value and "}}" in value:
                    return True
        return False

    def convert_jinja_braces(
        self, replacement_left: str = "<<", replacement_right: str = ">>"
    ) -> Scenario:
        """Convert Jinja braces to some other character.

        >>> s = Scenario({"food": "I love {{wood chips}}"})
        >>> s.convert_jinja_braces()
        Scenario({'food': 'I love <<wood chips>>'})

        """
        new_scenario = Scenario()
        for key, value in self.items():
            if isinstance(value, str):
                new_scenario[key] = value.replace("{{", replacement_left).replace(
                    "}}", replacement_right
                )
            else:
                new_scenario[key] = value
        return new_scenario

    def __add__(self, other_scenario: Scenario) -> Scenario:
        """Combine two scenarios by taking the union of their keys

        If the other scenario is None, then just return self.

        :param other_scenario: The other scenario to combine with.

        Example:

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
            return s

    def rename(
        self, old_name_or_replacement_dict: dict, new_name: Optional[str] = None
    ) -> Scenario:
        """Rename the keys of a scenario.

        :param replacement_dict: A dictionary of old keys to new keys.

        Example:

        >>> s = Scenario({"food": "wood chips"})
        >>> s.rename({"food": "food_preference"})
        Scenario({'food_preference': 'wood chips'})

        >>> s = Scenario({"food": "wood chips"})
        >>> s.rename("food", "snack")
        Scenario({'snack': 'wood chips'})
        """
        if isinstance(old_name_or_replacement_dict, str) and new_name is not None:
            replacement_dict = {old_name_or_replacement_dict: new_name}
        else:
            replacement_dict = old_name_or_replacement_dict

        new_scenario = Scenario()
        for key, value in self.items():
            if key in replacement_dict:
                new_scenario[replacement_dict[key]] = value
            else:
                new_scenario[key] = value
        return new_scenario

    def new_column_names(self, new_names: List[str]) -> Scenario:
        """Rename the keys of a scenario.

        >>> s = Scenario({"food": "wood chips"})
        >>> s.new_column_names(["food_preference"])
        Scenario({'food_preference': 'wood chips'})
        """
        try:
            assert len(new_names) == len(self.keys())
        except AssertionError:
            print("The number of new names must match the number of keys.")

        new_scenario = Scenario()
        for new_names, value in zip(new_names, self.values()):
            new_scenario[new_names] = value
        return new_scenario

    def table(self, tablefmt: str = "grid") -> str:
        """Display a scenario as a table."""
        return self.to_dataset().table(tablefmt=tablefmt)

    def json(self):
        return DisplayJSON(self.to_dict(add_edsl_version=False))

    def yaml(self):
        import yaml

        return DisplayYAML(self.to_dict(add_edsl_version=False))

    def to_dict(self, add_edsl_version=True) -> dict:
        """Convert a scenario to a dictionary.

        Example:

        >>> s = Scenario({"food": "wood chips"})
        >>> s.to_dict()
        {'food': 'wood chips', 'edsl_version': '...', 'edsl_class_name': 'Scenario'}

        >>> s.to_dict(add_edsl_version = False)
        {'food': 'wood chips'}

        """
        from edsl.scenarios.FileStore import FileStore

        d = self.data.copy()
        for key, value in d.items():
            if isinstance(value, FileStore):
                d[key] = value.to_dict(add_edsl_version=add_edsl_version)
        if add_edsl_version:
            from edsl import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = "Scenario"

        return d

    def __hash__(self) -> int:
        """
        Return a hash of the scenario.

        Example:

        >>> s = Scenario({"food": "wood chips"})
        >>> hash(s)
        1153210385458344214
        """
        from edsl.utilities.utilities import dict_hash

        return dict_hash(self.to_dict(add_edsl_version=False))

    def __repr__(self):
        return "Scenario(" + repr(self.data) + ")"

    def to_dataset(self) -> "Dataset":
        """Convert a scenario to a dataset.

        >>> s = Scenario({"food": "wood chips"})
        >>> s.to_dataset()
        Dataset([{'key': ['food']}, {'value': ['wood chips']}])
        """
        from edsl.results.Dataset import Dataset

        keys = list(self.keys())
        values = list(self.values())
        return Dataset([{"key": keys}, {"value": values}])

    def select(self, list_of_keys: List[str]) -> "Scenario":
        """Select a subset of keys from a scenario.

        :param list_of_keys: The keys to select.

        Example:

        >>> s = Scenario({"food": "wood chips", "drink": "water"})
        >>> s.select(["food"])
        Scenario({'food': 'wood chips'})
        """
        new_scenario = Scenario()
        for key in list_of_keys:
            new_scenario[key] = self[key]
        return new_scenario

    def drop(self, list_of_keys: List[str]) -> "Scenario":
        """Drop a subset of keys from a scenario.

        :param list_of_keys: The keys to drop.

        Example:

        >>> s = Scenario({"food": "wood chips", "drink": "water"})
        >>> s.drop(["food"])
        Scenario({'drink': 'water'})
        """
        new_scenario = Scenario()
        for key in self.keys():
            if key not in list_of_keys:
                new_scenario[key] = self[key]
        return new_scenario

    def keep(self, list_of_keys: List[str]) -> "Scenario":
        """Keep a subset of keys from a scenario.

        :param list_of_keys: The keys to keep.

        Example:

        >>> s = Scenario({"food": "wood chips", "drink": "water"})
        >>> s.keep(["food"])
        Scenario({'food': 'wood chips'})
        """

        return self.select(list_of_keys)

    @classmethod
    def from_url(cls, url: str, field_name: Optional[str] = "text") -> "Scenario":
        """Creates a scenario from a URL.

        :param url: The URL to create the scenario from.
        :param field_name: The field name to use for the text.

        """
        import requests

        text = requests.get(url).text
        return cls({"url": url, field_name: text})

    @classmethod
    def from_file(cls, file_path: str, field_name: str) -> "Scenario":
        """Creates a scenario from a file.

        >>> import tempfile
        >>> with tempfile.NamedTemporaryFile(suffix=".txt", mode="w") as f:
        ...     _ = f.write("This is a test.")
        ...     _ = f.flush()
        ...     s = Scenario.from_file(f.name, "file")
        >>> s
        Scenario({'file': FileStore(path='...', ...)})

        """
        from edsl.scenarios.FileStore import FileStore

        fs = FileStore(file_path)
        return cls({field_name: fs})

    @classmethod
    def from_image(
        cls, image_path: str, image_name: Optional[str] = None
    ) -> "Scenario":
        """
        Creates a scenario with a base64 encoding of an image.

        Args:
            image_path (str): Path to the image file.

        Returns:
            Scenario: A new Scenario instance with image information.

        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")

        if image_name is None:
            image_name = os.path.basename(image_path).split(".")[0]

        return cls.from_file(image_path, image_name)

    @classmethod
    def from_pdf(cls, pdf_path):
        from edsl.scenarios.PdfExtractor import PdfExtractor

        return PdfExtractor(pdf_path, self).get_object()

    @classmethod
    def from_docx(cls, docx_path: str) -> "Scenario":
        """Creates a scenario from the text of a docx file.

        :param docx_path: The path to the docx file.

        Example:

        >>> from docx import Document
        >>> doc = Document()
        >>> _ = doc.add_heading("EDSL Survey")
        >>> _ = doc.add_paragraph("This is a test.")
        >>> doc.save("test.docx")
        >>> s = Scenario.from_docx("test.docx")
        >>> s
        Scenario({'file_path': 'test.docx', 'text': 'EDSL Survey\\nThis is a test.'})
        >>> import os; os.remove("test.docx")
        """
        from edsl.scenarios.DocxScenario import DocxScenario

        return Scenario(DocxScenario(docx_path).get_scenario_dict())

    def chunk(
        self,
        field,
        num_words: Optional[int] = None,
        num_lines: Optional[int] = None,
        include_original=False,
        hash_original=False,
    ) -> "ScenarioList":
        """Split a field into chunks of a given size.

        :param field: The field to split.
        :param num_words: The number of words in each chunk.
        :param num_lines: The number of lines in each chunk.
        :param include_original: Whether to include the original field in the new scenarios.
        :param hash_original: Whether to hash the original field in the new scenarios.

        If you specify `include_original=True`, the original field will be included in the new scenarios with an "_original" suffix.

        Either `num_words` or `num_lines` must be specified, but not both.

        The `hash_original` parameter is useful if you do not want to store the original text, but still want a unique identifier for it.

        Example:

        >>> s = Scenario({"text": "This is a test.\\nThis is a test.\\n\\nThis is a test."})
        >>> s.chunk("text", num_lines = 1)
        ScenarioList([Scenario({'text': 'This is a test.', 'text_chunk': 0}), Scenario({'text': 'This is a test.', 'text_chunk': 1}), Scenario({'text': '', 'text_chunk': 2}), Scenario({'text': 'This is a test.', 'text_chunk': 3})])

        >>> s.chunk("text", num_words = 2)
        ScenarioList([Scenario({'text': 'This is', 'text_chunk': 0}), Scenario({'text': 'a test.', 'text_chunk': 1}), Scenario({'text': 'This is', 'text_chunk': 2}), Scenario({'text': 'a test.', 'text_chunk': 3}), Scenario({'text': 'This is', 'text_chunk': 4}), Scenario({'text': 'a test.', 'text_chunk': 5})])

        >>> s = Scenario({"text": "Hello World"})
        >>> s.chunk("text", num_words = 1, include_original = True)
        ScenarioList([Scenario({'text': 'Hello', 'text_chunk': 0, 'text_original': 'Hello World'}), Scenario({'text': 'World', 'text_chunk': 1, 'text_original': 'Hello World'})])

        >>> s = Scenario({"text": "Hello World"})
        >>> s.chunk("text", num_words = 1, include_original = True, hash_original = True)
        ScenarioList([Scenario({'text': 'Hello', 'text_chunk': 0, 'text_original': 'b10a8db164e0754105b7a99be72e3fe5'}), Scenario({'text': 'World', 'text_chunk': 1, 'text_original': 'b10a8db164e0754105b7a99be72e3fe5'})])

        >>> s.chunk("text")
        Traceback (most recent call last):
        ...
        ValueError: You must specify either num_words or num_lines.

        >>> s.chunk("text", num_words = 1, num_lines = 1)
        Traceback (most recent call last):
        ...
        ValueError: You must specify either num_words or num_lines, but not both.
        """
        from edsl.scenarios.DocumentChunker import DocumentChunker

        return DocumentChunker(self).chunk(
            field, num_words, num_lines, include_original, hash_original
        )

    @classmethod
    @remove_edsl_version
    def from_dict(cls, d: dict) -> "Scenario":
        """Convert a dictionary to a scenario.

        Example:

        >>> Scenario.from_dict({"food": "wood chips"})
        Scenario({'food': 'wood chips'})
        """
        from edsl.scenarios.FileStore import FileStore

        for key, value in d.items():
            # TODO: we should check this better if its a FileStore + add remote security check against path traversal
            if (
                isinstance(value, dict) and "base64_string" in value and "path" in value
            ) or isinstance(value, FileStore):
                d[key] = FileStore.from_dict(value)
        return cls(d)

    def _table(self) -> tuple[dict, list]:
        """Prepare generic table data."""
        table_data = []
        for attr_name, attr_value in self.__dict__.items():
            table_data.append({"Attribute": attr_name, "Value": repr(attr_value)})
        column_names = ["Attribute", "Value"]
        return table_data, column_names

    @classmethod
    def example(cls, randomize: bool = False, has_image=False) -> Scenario:
        """
        Returns an example Scenario instance.

        :param randomize: If True, adds a random string to the value of the example key.
        """
        if not has_image:
            addition = "" if not randomize else str(uuid4())
            return cls(
                {
                    "persona": f"A reseacher studying whether LLMs can be used to generate surveys.{addition}",
                }
            )
        else:
            return cls.from_image(cls.example_image())

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
