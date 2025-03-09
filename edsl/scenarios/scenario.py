"""A Scenario is a dictionary with a key/value to parameterize a question."""

from __future__ import annotations
import copy
import os
import json
from collections import UserDict
from typing import Union, List, Optional, TYPE_CHECKING, Collection
from uuid import uuid4

from ..base import Base
from edsl.utilities.remove_edsl_version import remove_edsl_version
from edsl.exceptions.scenarios import ScenarioError

if TYPE_CHECKING:
    from .scenario_list import ScenarioList
    from ..dataset import Dataset

class DisplayJSON:
    """Display a dictionary as JSON."""

    def __init__(self, input_dict: dict):
        self.text = json.dumps(input_dict, indent=4)

    def __repr__(self):
        return self.text


class DisplayYAML:
    """Display a dictionary as YAML."""

    def __init__(self, input_dict: dict):
        import yaml

        self.text = yaml.dump(input_dict)

    def __repr__(self):
        return self.text


class Scenario(Base, UserDict):
    """A Scenario is a dictionary of keys/values that can be used to parameterize questions."""

    __documentation__ = "https://docs.expectedparrot.com/en/latest/scenarios.html"

    def __init__(self, data: Optional[dict] = None, name: Optional[str] = None):
        """Initialize a new Scenario.

        :param data: A dictionary of keys/values for parameterizing questions.
        :param name: The name of the scenario.
        """
        if not isinstance(data, dict) and data is not None:
            try:
                data = dict(data)
            except Exception as e:
                raise ScenarioError(
                    f"You must pass in a dictionary to initialize a Scenario. You passed in {data}",
                    "Exception message:" + str(e),
                )

        super().__init__()
        self.data = data if data is not None else {}
        self.name = name

    def __mul__(self, scenario_list_or_scenario: Union["ScenarioList", "Scenario"]) -> "ScenarioList":
        from edsl.scenarios.ScenarioList import ScenarioList
        if isinstance(scenario_list_or_scenario, ScenarioList):
            return scenario_list_or_scenario * self
        elif isinstance(scenario_list_or_scenario, Scenario):
            return ScenarioList([self]) * scenario_list_or_scenario
        else:
            raise TypeError(f"Cannot multiply Scenario with {type(scenario_list_or_scenario)}")

    def replicate(self, n: int) -> "ScenarioList":
        """Replicate a scenario n times to return a ScenarioList.

        :param n: The number of times to replicate the scenario.

        Example:
        >>> s = Scenario({"food": "wood chips"})
        >>> s.replicate(2)
        ScenarioList([Scenario({'food': 'wood chips'}), Scenario({'food': 'wood chips'})])
        """
        from .scenario_list import ScenarioList

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

    def _convert_jinja_braces(
        self, replacement_left: str = "<<", replacement_right: str = ">>"
    ) -> Scenario:
        """Convert Jinja braces to some other character.

        >>> s = Scenario({"food": "I love {{wood chips}}"})
        >>> s._convert_jinja_braces()
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
        self,
        old_name_or_replacement_dict: Union[str, dict[str, str]],
        new_name: Optional[str] = None,
    ) -> Scenario:
        """Rename the keys of a scenario.

        :param old_name_or_replacement_dict: A dictionary of old keys to new keys *OR* a string of the old key.
        :param new_name: The new name of the key.

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

    def to_dict(self, add_edsl_version: bool = True) -> dict:
        """Convert a scenario to a dictionary.

        Example:

        >>> s = Scenario({"food": "wood chips"})
        >>> s.to_dict()
        {'food': 'wood chips', 'edsl_version': '...', 'edsl_class_name': 'Scenario'}

        >>> s.to_dict(add_edsl_version = False)
        {'food': 'wood chips'}

        """
        from edsl.scenarios import FileStore

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
        """Return a hash of the scenario.

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
        from ..dataset import Dataset

        keys = list(self.keys())
        values = list(self.values())
        return Dataset([{"key": keys}, {"value": values}])

    def select(self, list_of_keys: Collection[str]) -> "Scenario":
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

    def drop(self, list_of_keys: Collection[str]) -> "Scenario":
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
    def from_url(cls, url: str, field_name: Optional[str] = "text", testing:bool = False) -> "Scenario":
        """Creates a scenario from a URL. Will use BeautifulSoup if available for better parsing,
        otherwise falls back to basic requests.

        :param url: The URL to create the scenario from.
        :param field_name: The field name to use for the text.
        :param testing: If True, uses simple requests method instead of BeautifulSoup

        """
        import requests

        if testing:
            # Use simple requests method for testing
            response = requests.get(url)
            text = response.text
        else:
            try:
                from bs4 import BeautifulSoup
                from fake_useragent import UserAgent
                
                # Configure request headers to appear more like a regular browser
                ua = UserAgent()
                headers = {
                    'User-Agent': ua.random,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5'
                }

                response = requests.get(url, headers=headers)
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Get text content while preserving some structure
                text = ' '.join([p.get_text(strip=True) for p in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])])

            except ImportError:
                # Fallback to basic requests if BeautifulSoup/fake_useragent not available
                print("BeautifulSoup/fake_useragent not available. Falling back to basic requests.")
                response = requests.get(url)
                text = response.text

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
        from edsl.scenarios import FileStore

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
    def from_pdf(cls, pdf_path: str):
        """Create a Scenario from a PDF file."""
        try:
            from edsl.scenarios.PdfExtractor import PdfExtractor
            extractor = PdfExtractor(pdf_path)
            return Scenario(extractor.get_pdf_dict())
        except ImportError as e:
            raise ImportError(
                f"Could not extract text from PDF: {str(e)}. "
                "PDF extraction requires the PyMuPDF library. "
                "Install it with: pip install pymupdf"
            )

    @classmethod
    def from_html(cls, url: str, field_name: Optional[str] = None) -> "Scenario":
        """Create a scenario from HTML content.

        :param html: The HTML content.
        :param field_name: The name of the field containing the HTML content.


        """
        html = cls.fetch_html(url)
        text = cls.extract_text(html)
        if not field_name:
            field_name = "text"
        return cls({"url": url, "html": html, field_name: text})

    @staticmethod
    def fetch_html(url):
        # Define the user-agent to mimic a browser
        import requests
        from requests.adapters import HTTPAdapter
        from requests.packages.urllib3.util.retry import Retry

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        # Create a session to manage cookies and retries
        session = requests.Session()
        retries = Retry(
            total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504]
        )
        session.mount("http://", HTTPAdapter(max_retries=retries))
        session.mount("https://", HTTPAdapter(max_retries=retries))

        try:
            # Make the request
            response = session.get(url, headers=headers, timeout=10)
            response.raise_for_status()  # Raise an exception for HTTP errors
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")
            return None

    @staticmethod
    def extract_text(html):
        # Extract text from HTML using BeautifulSoup
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text()
        return text


    @classmethod
    def from_pdf_to_image(cls, pdf_path, image_format="jpeg"):
        """
        Convert each page of a PDF into an image and create key/value for it.

        :param pdf_path: Path to the PDF file.
        :param image_format: Format of the output images (default is 'jpeg').
        :return: ScenarioList instance containing the Scenario instances.

        The scenario has a key "filepath" and one or more keys "page_{i}" for each page.
        """
        import tempfile
        from pdf2image import convert_from_path
        from edsl.scenarios import Scenario

        with tempfile.TemporaryDirectory() as output_folder:
            # Convert PDF to images
            images = convert_from_path(pdf_path)

            scenario_dict = {"filepath":pdf_path}

            # Save each page as an image and create Scenario instances
            for i, image in enumerate(images):
                image_path = os.path.join(output_folder, f"page_{i}.{image_format}")
                image.save(image_path, image_format.upper())

                from edsl.scenarios import FileStore
                scenario_dict[f"page_{i}"] = FileStore(image_path)

            scenario = Scenario(scenario_dict)

            return cls(scenario)

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
        ScenarioList([Scenario({'text': 'This is a test.', 'text_chunk': 0, 'text_char_count': 15, 'text_word_count': 4}), Scenario({'text': 'This is a test.', 'text_chunk': 1, 'text_char_count': 15, 'text_word_count': 4}), Scenario({'text': '', 'text_chunk': 2, 'text_char_count': 0, 'text_word_count': 0}), Scenario({'text': 'This is a test.', 'text_chunk': 3, 'text_char_count': 15, 'text_word_count': 4})])

        >>> s.chunk("text", num_words = 2)
        ScenarioList([Scenario({'text': 'This is', 'text_chunk': 0, 'text_char_count': 7, 'text_word_count': 2}), Scenario({'text': 'a test.', 'text_chunk': 1, 'text_char_count': 7, 'text_word_count': 2}), Scenario({'text': 'This is', 'text_chunk': 2, 'text_char_count': 7, 'text_word_count': 2}), Scenario({'text': 'a test.', 'text_chunk': 3, 'text_char_count': 7, 'text_word_count': 2}), Scenario({'text': 'This is', 'text_chunk': 4, 'text_char_count': 7, 'text_word_count': 2}), Scenario({'text': 'a test.', 'text_chunk': 5, 'text_char_count': 7, 'text_word_count': 2})])

        >>> s = Scenario({"text": "Hello World"})
        >>> s.chunk("text", num_words = 1, include_original = True)
        ScenarioList([Scenario({'text': 'Hello', 'text_chunk': 0, 'text_char_count': 5, 'text_word_count': 1, 'text_original': 'Hello World'}), Scenario({'text': 'World', 'text_chunk': 1, 'text_char_count': 5, 'text_word_count': 1, 'text_original': 'Hello World'})])

        >>> s = Scenario({"text": "Hello World"})
        >>> s.chunk("text", num_words = 1, include_original = True, hash_original = True)
        ScenarioList([Scenario({'text': 'Hello', 'text_chunk': 0, 'text_char_count': 5, 'text_word_count': 1, 'text_original': 'b10a8db164e0754105b7a99be72e3fe5'}), Scenario({'text': 'World', 'text_chunk': 1, 'text_char_count': 5, 'text_word_count': 1, 'text_original': 'b10a8db164e0754105b7a99be72e3fe5'})])

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
        from edsl.scenarios import FileStore

        for key, value in d.items():
            # TODO: we should check this better if its a FileStore + add remote security check against path traversal
            if (
                isinstance(value, dict) and "base64_string" in value and "path" in value
            ) or isinstance(value, FileStore):
                d[key] = FileStore.from_dict(value)
        return cls(d)

    def _table(self) -> tuple[dict, list]:
        """Prepare generic table data.
        >>> s = Scenario({"food": "wood chips"})
        >>> s._table()
        ([{'Attribute': 'data', 'Value': "{'food': 'wood chips'}"}, {'Attribute': 'name', 'Value': 'None'}], ['Attribute', 'Value'])
        """
        table_data = []
        for attr_name, attr_value in self.__dict__.items():
            table_data.append({"Attribute": attr_name, "Value": repr(attr_value)})
        column_names = ["Attribute", "Value"]
        return table_data, column_names

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
