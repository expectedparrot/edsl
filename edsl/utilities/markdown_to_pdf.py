from typing import Optional
import subprocess
import os
from pathlib import Path
import tempfile


class MarkdownToPDF:
    def __init__(self, markdown_content: str, filename: Optional[str] = None):
        """
        Initialize the converter with markdown content.

        Args:
            markdown_content (str): The markdown content to be converted
        """
        self.markdown_content = markdown_content
        self.filename = filename
        self.has_pandoc = self._check_pandoc()
        # self.convert()

    def _check_pandoc(self):
        """
        Check if pandoc is installed and accessible.
        
        Returns:
            bool: True if pandoc is available, False otherwise
        """
        try:
            subprocess.run(["pandoc", "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            import warnings
            warnings.warn(
                "Pandoc is not installed or not found in PATH. "
                "PDF conversion will not be available."
            )
            return False

    def convert(self, output_path: str, **options) -> bool:
        """
        Convert the markdown content to PDF.

        Args:
            output_path (str): Path where the PDF should be saved
            **options: Additional conversion options
                margin (str): Page margin (default: "1in")
                font_size (str): Font size (default: "12pt")
                toc (bool): Include table of contents (default: False)
                number_sections (bool): Number sections (default: False)
                highlight_style (str): Code highlighting style (default: "tango")

        Returns:
            bool: True if conversion was successful, False otherwise
        """
        # Ensure output directory exists
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build pandoc command with default options
        cmd = [
            "pandoc",
            "-f",
            "markdown",
            "-o",
            str(output_path),
            "--pdf-engine=xelatex",
            "--variable",
            f'geometry:margin={options.get("margin", "1in")}',
            "--variable",
            f'fontsize={options.get("font_size", "12pt")}',
        ]

        # Add font only if specifically provided
        if "font" in options:
            cmd.extend(["--variable", f'mainfont={options["font"]}'])

        # Add optional parameters
        if options.get("toc", False):
            cmd.append("--toc")

        if options.get("number_sections", False):
            cmd.append("--number-sections")

        if "highlight_style" in options:
            cmd.extend(["--highlight-style", options["highlight_style"]])

        try:
            # Run pandoc command
            subprocess.run(
                cmd,
                input=self.markdown_content,
                text=True,
                capture_output=True,
                check=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error converting markdown to PDF: {e.stderr}")
            return False

    def preview(self) -> str:
        """
        Generate a temporary PDF and return its path.

        Returns:
            str: Path to the temporary PDF file
        """
        temp_dir = tempfile.mkdtemp()
        if self.filename:
            temp_pdf = os.path.join(temp_dir, f"{self.filename}.pdf")
        else:
            temp_pdf = os.path.join(temp_dir, "preview.pdf")

        if self.convert(temp_pdf):
            from ..scenarios import FileStore

            return FileStore(temp_pdf)

        return None
