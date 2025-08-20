"""
Scenario factory functionality.

This module contains the ScenarioFactory class which handles all factory operations
for creating Scenario instances from various sources including files, URLs, PDFs,
images, HTML content, and other data sources.

The ScenarioFactory provides:
- File-based creation (from_file, from_image, from_pdf, from_docx)
- Web-based creation (from_url, from_html)
- Document processing (from_pdf_to_image)
- Example generation (example)
- Helper utilities for HTML processing
"""

from __future__ import annotations
import os
import tempfile
from typing import Optional, TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from .scenario import Scenario


class ScenarioFactory:
    """
    Factory class for creating Scenario instances from various sources.
    
    This class provides static and class methods for creating Scenario objects
    from files, URLs, documents, and other data sources. It handles the complex
    logic of extracting content, processing different file formats, and creating
    appropriately structured Scenario instances.
    """

    @classmethod
    def from_url(
        cls, url: str, field_name: Optional[str] = "text", testing: bool = False
    ) -> "Scenario":
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
            >>> s = ScenarioFactory.from_url("https://example.com", testing=True)  # doctest: +SKIP
            >>> "url" in s and "text" in s  # doctest: +SKIP
            True

            >>> s = ScenarioFactory.from_url("https://example.com", field_name="content", testing=True)  # doctest: +SKIP
            >>> "url" in s and "content" in s  # doctest: +SKIP
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
                    "User-Agent": ua.random,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                }

                response = requests.get(url, headers=headers)
                soup = BeautifulSoup(response.content, "html.parser")

                # Get text content while preserving some structure
                text = " ".join(
                    [
                        p.get_text(strip=True)
                        for p in soup.find_all(
                            ["p", "h1", "h2", "h3", "h4", "h5", "h6"]
                        )
                    ]
                )

            except ImportError:
                # Fallback to basic requests if BeautifulSoup/fake_useragent not available
                print(
                    "BeautifulSoup/fake_useragent not available. Falling back to basic requests."
                )
                response = requests.get(url)
                text = response.text

        # Import here to avoid circular imports
        try:
            from .scenario import Scenario
        except ImportError:
            from edsl.scenarios import Scenario
        
        return Scenario({"url": url, field_name: text})

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
            ...     s = ScenarioFactory.from_file(f.name, "file")  # doctest: +SKIP
            >>> s  # doctest: +SKIP
            Scenario({'file': FileStore(path='...', ...)})

        Notes:
            - The FileStore object handles various file formats differently
            - FileStore provides methods to access file content, extract text,
              and manage file operations appropriate to the file type
        """
        from edsl.scenarios import FileStore

        fs = FileStore(file_path)
        
        # Import here to avoid circular imports
        try:
            from .scenario import Scenario
        except ImportError:
            from edsl.scenarios import Scenario
        
        return Scenario({field_name: fs})

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
            >>> if os.path.exists("image.jpg"):  # doctest: +SKIP
            ...     s = ScenarioFactory.from_image("image.jpg")  # doctest: +SKIP
            ...     s_named = ScenarioFactory.from_image("image.jpg", "picture")  # doctest: +SKIP

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
            >>> if os.path.exists("document.pdf"):  # doctest: +SKIP
            ...     s = ScenarioFactory.from_pdf("document.pdf")  # doctest: +SKIP

        Notes:
            - The returned Scenario contains various keys with PDF content and metadata
            - PDF extraction requires the PyMuPDF library
            - The extraction process parses the PDF to maintain structure where possible
        """
        try:
            from edsl.scenarios.PdfExtractor import PdfExtractor

            extractor = PdfExtractor(pdf_path)
            
            # Import here to avoid circular imports
            try:
                from .scenario import Scenario
            except ImportError:
                from edsl.scenarios import Scenario
                
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
            >>> s = ScenarioFactory.from_html("https://example.com")  # doctest: +SKIP
            >>> all(key in s for key in ["url", "html", "text"])  # doctest: +SKIP
            True

            >>> s = ScenarioFactory.from_html("https://example.com", field_name="content")  # doctest: +SKIP
            >>> all(key in s for key in ["url", "html", "content"])  # doctest: +SKIP
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
            
        # Import here to avoid circular imports
        try:
            from .scenario import Scenario
        except ImportError:
            from edsl.scenarios import Scenario
            
        return Scenario({"url": url, "html": html, field_name: text})

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
            text = "\n".join(chunk for chunk in chunks if chunk)

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
            >>> if os.path.exists("document.pdf"):  # doctest: +SKIP
            ...     s = ScenarioFactory.from_pdf_to_image("document.pdf")  # doctest: +SKIP
            ...     s_png = ScenarioFactory.from_pdf_to_image("document.pdf", "png")  # doctest: +SKIP

        Notes:
            - Requires the pdf2image library which depends on poppler
            - Creates a separate image for each page of the PDF
            - Images are stored in FileStore objects for easy display and handling
            - Images are created in a temporary directory which is automatically cleaned up
        """
        from pdf2image import convert_from_path
        from edsl.scenarios import FileStore

        with tempfile.TemporaryDirectory() as output_folder:
            # Convert PDF to images
            images = convert_from_path(pdf_path)

            scenario_dict = {"filepath": pdf_path}

            # Save each page as an image and create Scenario instances
            for i, image in enumerate(images):
                image_path = os.path.join(output_folder, f"page_{i}.{image_format}")
                image.save(image_path, image_format.upper())

                scenario_dict[f"page_{i}"] = FileStore(image_path)

            # Import here to avoid circular imports
            try:
                from .scenario import Scenario
            except ImportError:
                from edsl.scenarios import Scenario

            return Scenario(scenario_dict)

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
            >>> from docx import Document  # doctest: +SKIP
            >>> doc = Document()  # doctest: +SKIP
            >>> _ = doc.add_heading("EDSL Survey")  # doctest: +SKIP
            >>> _ = doc.add_paragraph("This is a test.")  # doctest: +SKIP
            >>> doc.save("test.docx")  # doctest: +SKIP
            >>> s = ScenarioFactory.from_docx("test.docx")  # doctest: +SKIP
            >>> s  # doctest: +SKIP
            Scenario({'file_path': 'test.docx', 'text': 'EDSL Survey\\nThis is a test.'})
            >>> import os; os.remove("test.docx")  # doctest: +SKIP

        Notes:
            - The returned Scenario typically contains the file path and extracted text
            - The extraction process attempts to maintain document structure
            - Requires the python-docx library to be installed
        """
        from edsl.scenarios.DocxScenario import DocxScenario

        # Import here to avoid circular imports
        try:
            from .scenario import Scenario
        except ImportError:
            from edsl.scenarios import Scenario

        return Scenario(DocxScenario(docx_path).get_scenario_dict())

    @classmethod
    def example(cls, randomize: bool = False) -> "Scenario":
        """
        Returns an example Scenario instance.

        Args:
            randomize: If True, adds a random string to the value of the example key.

        Returns:
            A Scenario instance with example data.

        Examples:
            >>> s = ScenarioFactory.example()
            >>> 'persona' in s
            True
            
            >>> s1 = ScenarioFactory.example(randomize=True)
            >>> s2 = ScenarioFactory.example(randomize=True)
            >>> s1['persona'] != s2['persona']  # Should be different due to randomization
            True
        """
        addition = "" if not randomize else str(uuid4())
        
        # Import here to avoid circular imports
        try:
            from .scenario import Scenario
        except ImportError:
            from edsl.scenarios import Scenario
            
        return Scenario(
            {
                "persona": f"A reseacher studying whether LLMs can be used to generate surveys.{addition}",
            }
        ) 