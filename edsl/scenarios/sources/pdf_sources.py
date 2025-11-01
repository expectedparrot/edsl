"""PDF-based sources for ScenarioList creation."""

from __future__ import annotations
from typing import Literal, TYPE_CHECKING

from .base import Source
from ..scenario import Scenario
from ..exceptions import ScenarioError

if TYPE_CHECKING:
    from ..scenario_list import ScenarioList


class PDFSource(Source):
    """Create ScenarioList from PDF files by extracting text."""
    
    source_type = "pdf"

    def __init__(
        self,
        file_path: str,
        chunk_type: Literal["page", "text"] = "page",
        chunk_size: int = 1,
        chunk_overlap: int = 0,
    ):
        """
        Initialize a PDFSource with a path to a PDF file.

        Args:
            file_path: Path to the PDF file or URL to a PDF.
            chunk_type: Type of chunking to use ("page" or "text").
            chunk_size: Size of chunks to create.
            chunk_overlap: Number of overlapping chunks.
        """
        self.file_path = file_path
        self.chunk_type = chunk_type
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    @classmethod
    def example(cls) -> "PDFSource":
        """Return an example PDFSource instance."""
        # Skip actual file creation and just use a mock instance
        instance = cls(
            file_path="/path/to/nonexistent/file.pdf",
            chunk_type="page",
            chunk_size=1,
            chunk_overlap=0,
        )

        # Override the to_scenario_list method just for the example
        def mock_to_scenario_list(self):
            from ..scenario_list import ScenarioList

            # Create a simple mock ScenarioList with sample PDF data
            scenarios = [
                Scenario(
                    {
                        "filename": "example.pdf",
                        "page": 1,
                        "text": "This is page 1 content",
                    }
                ),
                Scenario(
                    {
                        "filename": "example.pdf",
                        "page": 2,
                        "text": "This is page 2 content",
                    }
                ),
            ]
            return ScenarioList(scenarios)

        # Replace the method on this instance only
        import types

        instance.to_scenario_list = types.MethodType(mock_to_scenario_list, instance)

        return instance

    def to_scenario_list(self):
        """Create a ScenarioList from a PDF file."""
        from ..scenario_list import ScenarioList
        from ..scenario_list_pdf_tools import PdfTools

        try:
            # Check if it's a URL
            if PdfTools.is_url(self.file_path):
                # Download the PDF file
                if "drive.google.com" in self.file_path:
                    # It's a Google Drive URL
                    local_path = PdfTools.GoogleDriveDownloader.fetch_from_drive(
                        self.file_path, "temp_pdf.pdf"
                    )
                else:
                    # It's a regular URL
                    local_path = PdfTools.fetch_and_save_pdf(
                        self.file_path, "temp_pdf.pdf"
                    )
            else:
                # It's a local file path
                local_path = self.file_path

            # Extract scenarios from the PDF
            scenarios = list(PdfTools.extract_text_from_pdf(local_path))

            # Handle chunking based on the specified parameters
            if self.chunk_type == "page":
                # Default behavior - one scenario per page
                return ScenarioList(scenarios)
            elif self.chunk_type == "text":
                # Combine all text
                combined_text = ""
                for scenario in scenarios:
                    combined_text += scenario["text"]

                # Create a single scenario with all text
                base_scenario = scenarios[0].copy()
                base_scenario["text"] = combined_text
                return ScenarioList([base_scenario])
            else:
                raise ValueError(
                    f"Invalid chunk_type: {self.chunk_type}. Must be 'page' or 'text'."
                )

        except Exception as e:
            raise ScenarioError(f"Error processing PDF: {str(e)}")


class PDFImageSource(Source):
    """Create ScenarioList from PDF files by converting pages to images."""
    
    source_type = "pdf_to_image"

    def __init__(
        self, file_path: str, base_width: int = 2000, include_text: bool = True
    ):
        """
        Initialize a PDFImageSource with a path to a PDF file.

        Args:
            file_path: Path to the PDF file.
            base_width: Width to use for the generated images.
            include_text: Whether to include extracted text with the images.
        """
        self.file_path = file_path
        self.base_width = base_width
        self.include_text = include_text

    @classmethod
    def example(cls) -> "PDFImageSource":
        """Return an example PDFImageSource instance."""
        # Skip actual file creation and just use a mock instance
        instance = cls(
            file_path="/path/to/nonexistent/file.pdf",
            base_width=2000,
            include_text=True,
        )

        # Override the to_scenario_list method just for the example
        def mock_to_scenario_list(self):
            from ..scenario_list import ScenarioList

            # Create a simple mock ScenarioList with sample PDF image data
            scenarios = [
                Scenario(
                    {
                        "filepath": "/tmp/page_1.jpeg",
                        "page": 0,
                        "text": "This is page 1 content",
                    }
                ),
                Scenario(
                    {
                        "filepath": "/tmp/page_2.jpeg",
                        "page": 1,
                        "text": "This is page 2 content",
                    }
                ),
            ]
            return ScenarioList(scenarios)

        # Replace the method on this instance only
        import types

        instance.to_scenario_list = types.MethodType(mock_to_scenario_list, instance)

        return instance

    def to_scenario_list(self):
        """Create a ScenarioList from a PDF file, converting pages to images."""
        from ..scenario_list import ScenarioList
        from ..scenario_list_pdf_tools import PdfTools

        try:
            # Import pdf2image library
            try:
                from pdf2image import convert_from_path  # noqa: F401
            except ImportError:
                raise ImportError(
                    "pdf2image is required to convert PDF to images. Install it with 'pip install pdf2image'."
                )

            # Convert PDF pages to images
            scenarios = PdfTools.from_pdf_to_image(self.file_path, image_format="jpeg")
            return ScenarioList(scenarios)

        except Exception as e:
            raise ScenarioError(f"Error converting PDF to images: {str(e)}")

