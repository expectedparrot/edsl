"""
A Scenario is a dictionary-like object that stores key-value pairs for parameterizing questions.

Scenarios are a fundamental concept in EDSL, providing a mechanism to parameterize
questions with dynamic values. Each Scenario contains key-value pairs that can be 
referenced within question templates using Jinja syntax. This allows for creating
questions that vary based on the specific scenario being presented.

Key features include:
- Dictionary-like behavior (inherits from UserDict)
- Support for combination operations (addition, multiplication)
- Conversion to/from various formats (dict, dataset)
- Methods for file and data source integration

Scenarios can be created from various sources including files, URLs, PDFs, images,
and HTML content. They serve as the primary mechanism for providing context or variable
information to questions in surveys.
"""

from __future__ import annotations
import copy
import os
from collections import UserDict
from typing import Union, List, Optional, TYPE_CHECKING, Collection
from uuid import uuid4

from ..base import Base
from ..utilities import remove_edsl_version
from .exceptions import ScenarioError

if TYPE_CHECKING:
    from .scenario_list import ScenarioList
    from ..dataset import Dataset



class Scenario(Base, UserDict):
    """
    A dictionary-like object that stores key-value pairs for parameterizing questions.
    
    A Scenario inherits from both the EDSL Base class and Python's UserDict, allowing
    it to function as a dictionary while providing additional functionality. Scenarios
    are used to parameterize questions by providing variable data that can be referenced
    within question templates using Jinja syntax.
    
    Scenarios can be created directly with dictionary data or constructed from various
    sources using class methods (from_file, from_url, from_pdf, etc.). They support
    operations like addition (combining scenarios) and multiplication (creating cross
    products with other scenarios or scenario lists).
    
    Attributes:
        data (dict): The underlying dictionary data.
        name (str, optional): A name for the scenario.
    
    Examples:
        Create a simple scenario:
        >>> s = Scenario({"product": "coffee", "price": 4.99})
        
        Combine scenarios:
        >>> s1 = Scenario({"product": "coffee"})
        >>> s2 = Scenario({"price": 4.99})
        >>> s3 = s1 + s2
        >>> s3
        Scenario({'product': 'coffee', 'price': 4.99})
        
        Create a scenario from a file:
        >>> import tempfile
        >>> with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        ...     _ = f.write("Hello World")
        ...     data_path = f.name
        >>> s = Scenario.from_file(data_path, "document")
        >>> import os
        >>> os.unlink(data_path) # Clean up temp file
    """

    __documentation__ = "https://docs.expectedparrot.com/en/latest/scenarios.html"

    def __init__(self, data: Optional[dict] = None, name: Optional[str] = None):
        """
        Initialize a new Scenario.

        Args:
            data: A dictionary of key-value pairs for parameterizing questions.
                  Any dictionary-like object that can be converted to a dict is accepted.
            name: An optional name for the scenario to aid in identification.

        Raises:
            ScenarioError: If the data cannot be converted to a dictionary.

        Examples:
            >>> s = Scenario({"product": "coffee", "price": 4.99})
            >>> s = Scenario({"question": "What is your favorite color?"}, name="color_question")
        """
        if not isinstance(data, dict) and data is not None:
            try:
                data = dict(data)
            except Exception as e:
                raise ScenarioError(
                    f"You must pass in a dictionary to initialize a Scenario. You passed in {data}" +   "Exception message:" + str(e),
                )

        super().__init__()
        self.data = data if data is not None else {}
        self.name = name

    def __mul__(self, scenario_list_or_scenario: Union["ScenarioList", "Scenario"]) -> "ScenarioList":
        """Takes the cross product of a Scenario with another Scenario or ScenarioList.

        Args:
            scenario_list_or_scenario: A Scenario or ScenarioList to multiply with.

        Returns:
            A ScenarioList containing the cross product.

        Example:
            >>> s1 = Scenario({'a': 1})
            >>> s2 = Scenario({'b': 2})
            >>> s1 * s2
            ScenarioList([Scenario({'a': 1, 'b': 2})])

            >>> from edsl.scenarios import ScenarioList
            >>> sl = ScenarioList([Scenario({'b': 2}), Scenario({'b': 3})])
            >>> new_s = s1 * sl
            >>> new_s == ScenarioList([Scenario({'a': 1, 'b': 2}), Scenario({'a': 1, 'b': 3})])
            True
        """
        from .scenario_list import ScenarioList
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
    def from_url(cls, url: str, field_name: Optional[str] = "text", testing: bool = False) -> "Scenario":
        """
        Creates a Scenario from the content of a URL.
        
        This method fetches content from a web URL and creates a Scenario containing the URL 
        and the extracted text. When available, BeautifulSoup is used for better HTML parsing
        and text extraction, otherwise a basic requests approach is used.
        
        Args:
            url: The URL to fetch content from.
            field_name: The key name to use for storing the extracted text in the Scenario.
                        Defaults to "text".
            testing: If True, uses a simplified requests method instead of BeautifulSoup.
                    This is primarily for testing purposes.
                    
        Returns:
            A Scenario containing the URL and extracted text.
            
        Raises:
            requests.exceptions.RequestException: If the URL cannot be accessed.
            
        Examples:
            >>> s = Scenario.from_url("https://example.com", testing=True)
            >>> "url" in s and "text" in s
            True
            
            >>> s = Scenario.from_url("https://example.com", field_name="content", testing=True)
            >>> "url" in s and "content" in s
            True
            
        Notes:
            - The method attempts to use BeautifulSoup and fake_useragent for better
              HTML parsing and to mimic a real browser.
            - If these packages are not available, it falls back to basic requests.
            - When using BeautifulSoup, it extracts text from paragraph and heading tags.
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
        """
        Creates a Scenario containing a FileStore object from a file.
        
        This method creates a Scenario with a single key-value pair where the value
        is a FileStore object that encapsulates the specified file. The FileStore
        handles appropriate file loading, encoding, and extraction based on the file type.
        
        Args:
            file_path: Path to the file to be incorporated into the Scenario.
            field_name: Key name to use for storing the FileStore in the Scenario.
            
        Returns:
            A Scenario containing a FileStore object linked to the specified file.
            
        Raises:
            FileNotFoundError: If the specified file does not exist.
            
        Examples:
            >>> import tempfile
            >>> with tempfile.NamedTemporaryFile(suffix=".txt", mode="w") as f:
            ...     _ = f.write("This is a test.")
            ...     _ = f.flush()
            ...     s = Scenario.from_file(f.name, "file")
            >>> s
            Scenario({'file': FileStore(path='...', ...)})
            
        Notes:
            - The FileStore object handles various file formats differently
            - FileStore provides methods to access file content, extract text, 
              and manage file operations appropriate to the file type
        """
        from edsl.scenarios import FileStore

        fs = FileStore(file_path)
        return cls({field_name: fs})

    @classmethod
    def from_image(
        cls, image_path: str, image_name: Optional[str] = None
    ) -> "Scenario":
        """
        Creates a Scenario containing an image file as a FileStore object.
        
        This method creates a Scenario with a single key-value pair where the value
        is a FileStore object that encapsulates the specified image file. The image
        is stored as a base64-encoded string, allowing it to be easily serialized
        and transmitted.
        
        Args:
            image_path: Path to the image file to be incorporated into the Scenario.
            image_name: Key name to use for storing the FileStore in the Scenario.
                       If not provided, uses the filename without extension.
            
        Returns:
            A Scenario containing a FileStore object with the image data.
            
        Raises:
            FileNotFoundError: If the specified image file does not exist.
            
        Examples:
            >>> import os
            >>> # Assuming an image file exists
            >>> if os.path.exists("image.jpg"):
            ...     s = Scenario.from_image("image.jpg")
            ...     s_named = Scenario.from_image("image.jpg", "picture")
            
        Notes:
            - The resulting FileStore can be displayed in notebooks or used in questions
            - Supported image formats include JPG, PNG, GIF, etc.
            - The image is stored as a base64-encoded string for portability
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")

        if image_name is None:
            image_name = os.path.basename(image_path).split(".")[0]

        return cls.from_file(image_path, image_name)

    @classmethod
    def from_pdf(cls, pdf_path: str) -> "Scenario":
        """
        Creates a Scenario containing text extracted from a PDF file.
        
        This method extracts text and metadata from a PDF file and creates a Scenario
        containing this information. It uses the PdfExtractor class which provides
        access to text content, metadata, and structure from PDF files.
        
        Args:
            pdf_path: Path to the PDF file to extract content from.
            
        Returns:
            A Scenario containing extracted text and metadata from the PDF.
            
        Raises:
            FileNotFoundError: If the specified PDF file does not exist.
            ImportError: If the required PDF extraction libraries are not installed.
            
        Examples:
            >>> import os
            >>> # Assuming a PDF file exists
            >>> if os.path.exists("document.pdf"):
            ...     s = Scenario.from_pdf("document.pdf")
            
        Notes:
            - The returned Scenario contains various keys with PDF content and metadata
            - PDF extraction requires the PyMuPDF library
            - The extraction process parses the PDF to maintain structure where possible
        """
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
        """
        Creates a Scenario containing both HTML content and extracted text from a URL.
        
        This method fetches HTML content from a URL, extracts readable text from it,
        and creates a Scenario containing the original URL, the raw HTML, and the
        extracted text. Unlike from_url, this method preserves the raw HTML content.
        
        Args:
            url: URL to fetch HTML content from.
            field_name: Key name to use for the extracted text in the Scenario.
                       If not provided, defaults to "text".
            
        Returns:
            A Scenario containing the URL, raw HTML, and extracted text.
            
        Raises:
            requests.exceptions.RequestException: If the URL cannot be accessed.
            
        Examples:
            >>> s = Scenario.from_html("https://example.com")
            >>> all(key in s for key in ["url", "html", "text"])
            True
            
            >>> s = Scenario.from_html("https://example.com", field_name="content")
            >>> all(key in s for key in ["url", "html", "content"])
            True
            
        Notes:
            - Uses BeautifulSoup for HTML parsing when available
            - Stores both the raw HTML and the extracted text
            - Provides a more comprehensive representation than from_url
            - Useful when the HTML structure or specific elements are needed
        """
        html = cls.fetch_html(url)
        text = cls.extract_text(html)
        if not field_name:
            field_name = "text"
        return cls({"url": url, "html": html, field_name: text})

    @staticmethod
    def fetch_html(url: str) -> Optional[str]:
        """
        Fetches HTML content from a URL with robust error handling and retries.
        
        This method creates a session with configurable retries to fetch HTML content
        from a URL. It uses a realistic user agent to avoid being blocked by websites
        that filter bot traffic.
        
        Args:
            url: The URL to fetch HTML content from.
            
        Returns:
            The HTML content as a string, or None if the request failed.
            
        Raises:
            requests.exceptions.RequestException: If a request error occurs.
        """
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
    def extract_text(html: Optional[str]) -> str:
        """
        Extracts readable text from HTML content using BeautifulSoup.
        
        This method parses HTML content and extracts the readable text while
        removing HTML tags and script content.
        
        Args:
            html: The HTML content to extract text from.
            
        Returns:
            The extracted text content as a string. Returns an empty string
            if the input is None or if parsing fails.
        """
        if html is None:
            return ""
            
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            
            # Remove script and style elements that might contain non-readable content
            for element in soup(["script", "style"]):
                element.extract()
                
            text = soup.get_text()
            
            # Normalize whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            
            return text
        except Exception as e:
            print(f"Error extracting text from HTML: {e}")
            return ""


    @classmethod
    def from_pdf_to_image(cls, pdf_path: str, image_format: str = "jpeg") -> "Scenario":
        """
        Converts each page of a PDF into an image and creates a Scenario containing them.
        
        This method takes a PDF file, converts each page to an image in the specified
        format, and creates a Scenario containing the original file path and FileStore
        objects for each page image. This is particularly useful for visualizing PDF
        content or for image-based processing of PDF documents.
        
        Args:
            pdf_path: Path to the PDF file to convert to images.
            image_format: Format of the output images (default is 'jpeg').
                         Other formats include 'png', 'tiff', etc.
            
        Returns:
            A Scenario containing the original PDF file path and FileStore objects
            for each page image, with keys like "page_0", "page_1", etc.
            
        Raises:
            FileNotFoundError: If the specified PDF file does not exist.
            ImportError: If pdf2image is not installed.
            
        Examples:
            >>> import os
            >>> # Assuming a PDF file exists
            >>> if os.path.exists("document.pdf"):
            ...     s = Scenario.from_pdf_to_image("document.pdf")
            ...     s_png = Scenario.from_pdf_to_image("document.pdf", "png")
            
        Notes:
            - Requires the pdf2image library which depends on poppler
            - Creates a separate image for each page of the PDF
            - Images are stored in FileStore objects for easy display and handling
            - Images are created in a temporary directory which is automatically cleaned up
        """
        import tempfile
        from pdf2image import convert_from_path
        from edsl.scenarios import Scenario

        with tempfile.TemporaryDirectory() as output_folder:
            # Convert PDF to images
            images = convert_from_path(pdf_path)

            scenario_dict = {"filepath": pdf_path}

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
        """
        Creates a Scenario containing text extracted from a Microsoft Word document.
        
        This method extracts text and structure from a DOCX file and creates a Scenario
        containing this information. It uses the DocxScenario class to handle the 
        extraction process and maintain document structure where possible.
        
        Args:
            docx_path: Path to the DOCX file to extract content from.
            
        Returns:
            A Scenario containing the file path and extracted text from the DOCX file.
            
        Raises:
            FileNotFoundError: If the specified DOCX file does not exist.
            ImportError: If the python-docx library is not installed.
            
        Examples:
            >>> from docx import Document
            >>> doc = Document()
            >>> _ = doc.add_heading("EDSL Survey")
            >>> _ = doc.add_paragraph("This is a test.")
            >>> doc.save("test.docx")
            >>> s = Scenario.from_docx("test.docx")
            >>> s
            Scenario({'file_path': 'test.docx', 'text': 'EDSL Survey\\nThis is a test.'})
            >>> import os; os.remove("test.docx")
            
        Notes:
            - The returned Scenario typically contains the file path and extracted text
            - The extraction process attempts to maintain document structure
            - Requires the python-docx library to be installed
        """
        from edsl.scenarios.DocxScenario import DocxScenario

        return Scenario(DocxScenario(docx_path).get_scenario_dict())

    def chunk(
        self,
        field: str,
        num_words: Optional[int] = None,
        num_lines: Optional[int] = None,
        include_original: bool = False,
        hash_original: bool = False,
    ) -> "ScenarioList":
        """
        Splits a text field into chunks of a specified size, creating a ScenarioList.
        
        This method takes a field containing text and divides it into smaller chunks
        based on either word count or line count. It's particularly useful for processing
        large text documents in manageable pieces, such as for summarization, analysis,
        or when working with models that have token limits.
        
        Args:
            field: The key name of the field in the Scenario to split.
            num_words: The number of words to include in each chunk. Mutually exclusive
                      with num_lines.
            num_lines: The number of lines to include in each chunk. Mutually exclusive
                      with num_words.
            include_original: If True, includes the original complete text in each chunk
                             with a "_original" suffix.
            hash_original: If True and include_original is True, stores a hash of the
                          original text instead of the full text.
        
        Returns:
            A ScenarioList containing multiple Scenarios, each with a chunk of the
            original text. Each Scenario includes the chunk text, chunk index, character
            count, and word count.
            
        Raises:
            ValueError: If neither num_words nor num_lines is specified, or if both are.
            KeyError: If the specified field doesn't exist in the Scenario.
            
        Examples:
            Split by lines (1 line per chunk):
            >>> s = Scenario({"text": "This is a test.\\nThis is a test.\\n\\nThis is a test."})
            >>> s.chunk("text", num_lines=1)
            ScenarioList([Scenario({'text': 'This is a test.', 'text_chunk': 0, 'text_char_count': 15, 'text_word_count': 4}), Scenario({'text': 'This is a test.', 'text_chunk': 1, 'text_char_count': 15, 'text_word_count': 4}), Scenario({'text': '', 'text_chunk': 2, 'text_char_count': 0, 'text_word_count': 0}), Scenario({'text': 'This is a test.', 'text_chunk': 3, 'text_char_count': 15, 'text_word_count': 4})])

            Split by words (2 words per chunk):
            >>> s.chunk("text", num_words=2)
            ScenarioList([Scenario({'text': 'This is', 'text_chunk': 0, 'text_char_count': 7, 'text_word_count': 2}), Scenario({'text': 'a test.', 'text_chunk': 1, 'text_char_count': 7, 'text_word_count': 2}), Scenario({'text': 'This is', 'text_chunk': 2, 'text_char_count': 7, 'text_word_count': 2}), Scenario({'text': 'a test.', 'text_chunk': 3, 'text_char_count': 7, 'text_word_count': 2}), Scenario({'text': 'This is', 'text_chunk': 4, 'text_char_count': 7, 'text_word_count': 2}), Scenario({'text': 'a test.', 'text_chunk': 5, 'text_char_count': 7, 'text_word_count': 2})])

            Include original text in each chunk:
            >>> s = Scenario({"text": "Hello World"})
            >>> s.chunk("text", num_words=1, include_original=True)
            ScenarioList([Scenario({'text': 'Hello', 'text_chunk': 0, 'text_char_count': 5, 'text_word_count': 1, 'text_original': 'Hello World'}), Scenario({'text': 'World', 'text_chunk': 1, 'text_char_count': 5, 'text_word_count': 1, 'text_original': 'Hello World'})])

            Use a hash of the original text:
            >>> s.chunk("text", num_words=1, include_original=True, hash_original=True)
            ScenarioList([Scenario({'text': 'Hello', 'text_chunk': 0, 'text_char_count': 5, 'text_word_count': 1, 'text_original': 'b10a8db164e0754105b7a99be72e3fe5'}), Scenario({'text': 'World', 'text_chunk': 1, 'text_char_count': 5, 'text_word_count': 1, 'text_original': 'b10a8db164e0754105b7a99be72e3fe5'})])
            
        Notes:
            - Either num_words or num_lines must be specified, but not both
            - Each chunk is assigned a sequential index in the 'text_chunk' field
            - Character and word counts for each chunk are included
            - When include_original is True, the original text is preserved in each chunk
            - The hash_original option is useful to save space while maintaining traceability
        """
        from .document_chunker import DocumentChunker

        return DocumentChunker(self).chunk(
            field, num_words, num_lines, include_original, hash_original
        )

    @classmethod
    @remove_edsl_version
    def from_dict(cls, d: dict) -> "Scenario":
        """
        Creates a Scenario from a dictionary, with special handling for FileStore objects.
        
        This method creates a Scenario using the provided dictionary. It has special handling
        for dictionary values that represent serialized FileStore objects, which it will
        deserialize back into proper FileStore instances.
        
        Args:
            d: A dictionary to convert to a Scenario.
            
        Returns:
            A new Scenario containing the provided dictionary data.
            
        Examples:
            >>> Scenario.from_dict({"food": "wood chips"})
            Scenario({'food': 'wood chips'})
            
            >>> # Example with a serialized FileStore
            >>> from edsl import FileStore
            >>> file_dict = {"path": "example.txt", "base64_string": "SGVsbG8gV29ybGQ="}
            >>> s = Scenario.from_dict({"document": file_dict})
            >>> isinstance(s["document"], FileStore)
            True
            
        Notes:
            - Any dictionary values that match the FileStore format will be converted to FileStore objects
            - The method detects FileStore objects by looking for "base64_string" and "path" keys
            - EDSL version information is automatically removed by the @remove_edsl_version decorator
            - This method is commonly used when deserializing scenarios from JSON or other formats
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
