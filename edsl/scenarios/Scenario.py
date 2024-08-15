"""A Scenario is a dictionary with a key/value to parameterize a question."""

from __future__ import annotations
import copy
import base64
import hashlib
import os
from collections import UserDict
from typing import Union, List, Optional, Generator
from uuid import uuid4
from edsl.Base import Base
from edsl.scenarios.ScenarioImageMixin import ScenarioImageMixin
from edsl.scenarios.ScenarioHtmlMixin import ScenarioHtmlMixin
from edsl.utilities.decorators import add_edsl_version, remove_edsl_version


class Scenario(Base, UserDict, ScenarioImageMixin, ScenarioHtmlMixin):
    """A Scenario is a dictionary of keys/values.

    They can be used parameterize edsl questions."""

    def __init__(self, data: Union[dict, None] = None, name: str = None):
        """Initialize a new Scenario.

        :param data: A dictionary of keys/values for parameterizing questions.
        """
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
    def has_image(self) -> bool:
        """Return whether the scenario has an image."""
        if not hasattr(self, "_has_image"):
            self._has_image = False
        return self._has_image

    @has_image.setter
    def has_image(self, value):
        self._has_image = value

    def __add__(self, other_scenario: "Scenario") -> "Scenario":
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
            if self.has_image or other_scenario.has_image:
                s._has_image = True
            return s

    def rename(self, replacement_dict: dict) -> "Scenario":
        """Rename the keys of a scenario.

        :param replacement_dict: A dictionary of old keys to new keys.

        Example:

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

    def _to_dict(self) -> dict:
        """Convert a scenario to a dictionary.

        Example:

        >>> s = Scenario({"food": "wood chips"})
        >>> s.to_dict()
        {'food': 'wood chips', 'edsl_version': '...', 'edsl_class_name': 'Scenario'}
        """
        return self.data.copy()

    @add_edsl_version
    def to_dict(self) -> dict:
        """Convert a scenario to a dictionary.

        Example:

        >>> s = Scenario({"food": "wood chips"})
        >>> s.to_dict()
        {'food': 'wood chips', 'edsl_version': '...', 'edsl_class_name': 'Scenario'}
        """
        return self._to_dict()

    def __hash__(self) -> int:
        """
        Return a hash of the scenario.

        Example:

        >>> s = Scenario({"food": "wood chips"})
        >>> hash(s)
        1153210385458344214
        """
        from edsl.utilities.utilities import dict_hash

        return dict_hash(self._to_dict())

    def print(self):
        from rich import print_json
        import json

        print_json(json.dumps(self.to_dict()))

    def __repr__(self):
        return "Scenario(" + repr(self.data) + ")"

    def _repr_html_(self):
        from edsl.utilities.utilities import data_to_html

        return data_to_html(self.to_dict())

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
    def from_image(cls, image_path: str) -> str:
        """Creates a scenario with a base64 encoding of an image.

        Example:

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

    @classmethod
    def from_pdf(cls, pdf_path):
        import fitz  # PyMuPDF
        from edsl import Scenario

        # Ensure the file exists
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"The file {pdf_path} does not exist.")

        # Open the PDF file
        document = fitz.open(pdf_path)

        # Get the filename from the path
        filename = os.path.basename(pdf_path)

        # Iterate through each page and extract text
        text = ""
        for page_num in range(len(document)):
            page = document.load_page(page_num)
            text = text + page.get_text()

        # Create a dictionary for the combined text
        page_info = {"filename": filename, "text": text}
        return Scenario(page_info)

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
        from docx import Document

        doc = Document(docx_path)

        # Extract all text
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)

        # Join the text from all paragraphs
        text = "\n".join(full_text)
        return Scenario({"file_path": docx_path, "text": text})

    @staticmethod
    def _line_chunks(text, num_lines: int) -> Generator[str, None, None]:
        """Split a text into chunks of a given size.

        :param text: The text to split.
        :param num_lines: The number of lines in each chunk.

        Example:

        >>> list(Scenario._line_chunks("This is a test.\\nThis is a test. This is a test.", 1))
        ['This is a test.', 'This is a test. This is a test.']
        """
        lines = text.split("\n")
        for i in range(0, len(lines), num_lines):
            chunk = "\n".join(lines[i : i + num_lines])
            yield chunk

    @staticmethod
    def _word_chunks(text, num_words: int) -> Generator[str, None, None]:
        """Split a text into chunks of a given size.

        :param text: The text to split.
        :param num_words: The number of words in each chunk.

        Example:

        >>> list(Scenario._word_chunks("This is a test.", 2))
        ['This is', 'a test.']
        """
        words = text.split()
        for i in range(0, len(words), num_words):
            chunk = " ".join(words[i : i + num_words])
            yield chunk

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
        from edsl.scenarios.ScenarioList import ScenarioList

        if num_words is not None:
            chunks = list(self._word_chunks(self[field], num_words))

        if num_lines is not None:
            chunks = list(self._line_chunks(self[field], num_lines))

        if num_words is None and num_lines is None:
            raise ValueError("You must specify either num_words or num_lines.")

        if num_words is not None and num_lines is not None:
            raise ValueError(
                "You must specify either num_words or num_lines, but not both."
            )

        scenarios = []
        for i, chunk in enumerate(chunks):
            new_scenario = copy.deepcopy(self)
            new_scenario[field] = chunk
            new_scenario[field + "_chunk"] = i
            if include_original:
                if hash_original:
                    new_scenario[field + "_original"] = hashlib.md5(
                        self[field].encode()
                    ).hexdigest()
                else:
                    new_scenario[field + "_original"] = self[field]
            scenarios.append(new_scenario)
        return ScenarioList(scenarios)

    @classmethod
    @remove_edsl_version
    def from_dict(cls, d: dict) -> "Scenario":
        """Convert a dictionary to a scenario.

        Example:

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
    def example(cls, randomize: bool = False) -> Scenario:
        """
        Returns an example Scenario instance.

        :param randomize: If True, adds a random string to the value of the example key.
        """
        addition = "" if not randomize else str(uuid4())
        return cls(
            {
                "persona": f"A reseacher studying whether LLMs can be used to generate surveys.{addition}",
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
