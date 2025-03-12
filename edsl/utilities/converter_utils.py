"""Utilities for converting between file formats."""

from typing import Optional
import subprocess
import os
from pathlib import Path
import tempfile


class MarkdownToDocx:
    """Convert Markdown content to DOCX format using Pandoc."""
    
    def __init__(self, markdown_content: str, filename: Optional[str] = None):
        """
        Initialize the converter with markdown content.

        Args:
            markdown_content (str): The markdown content to be converted
            filename (str, optional): The filename to save the output to
        """
        self.markdown_content = markdown_content
        self.filename = filename
        self._check_pandoc()

    def _check_pandoc(self):
        """Check if pandoc is installed."""
        try:
            result = subprocess.run(
                ["pandoc", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            return True
        except FileNotFoundError:
            print(
                "Warning: pandoc not found. Please install pandoc to convert markdown to docx."
            )
            print("You can install it from https://pandoc.org/installing.html")
            return False

    def convert(self):
        """Convert the markdown content to docx and save it to a file."""
        # Create a temporary file for the markdown content
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as md_file:
            md_file.write(self.markdown_content)
            md_file_path = md_file.name

        # Determine the output filename
        if self.filename is None:
            docx_file_path = Path(md_file_path).with_suffix(".docx").as_posix()
        else:
            docx_file_path = self.filename
            if not docx_file_path.endswith(".docx"):
                docx_file_path += ".docx"

        # Convert the markdown to docx
        result = subprocess.run(
            ["pandoc", md_file_path, "-o", docx_file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Clean up the temporary file
        os.unlink(md_file_path)

        if result.returncode != 0:
            print(f"Error converting markdown to docx: {result.stderr.decode()}")
            return None
        else:
            print(f"Markdown converted to docx and saved to {docx_file_path}")
            return docx_file_path


class MarkdownToPDF:
    """Convert Markdown content to PDF format using Pandoc."""
    
    def __init__(self, markdown_content: str, filename: Optional[str] = None):
        """
        Initialize the converter with markdown content.

        Args:
            markdown_content (str): The markdown content to be converted
            filename (str, optional): The filename to save the output to
        """
        self.markdown_content = markdown_content
        self.filename = filename
        self.has_pandoc = self._check_pandoc()

    def _check_pandoc(self):
        """Check if pandoc is installed."""
        try:
            result = subprocess.run(
                ["pandoc", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            return True
        except FileNotFoundError:
            print(
                "Warning: pandoc not found. Please install pandoc to convert markdown to PDF."
            )
            print("You can install it from https://pandoc.org/installing.html")
            return False

    def convert(self):
        """Convert the markdown content to PDF and save it to a file."""
        if not self.has_pandoc:
            print("Cannot convert to PDF: pandoc is not installed.")
            return None

        # Create a temporary file for the markdown content
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as md_file:
            md_file.write(self.markdown_content)
            md_file_path = md_file.name

        # Determine the output filename
        if self.filename is None:
            pdf_file_path = Path(md_file_path).with_suffix(".pdf").as_posix()
        else:
            pdf_file_path = self.filename
            if not pdf_file_path.endswith(".pdf"):
                pdf_file_path += ".pdf"

        # Convert the markdown to PDF
        result = subprocess.run(
            ["pandoc", md_file_path, "-o", pdf_file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Clean up the temporary file
        os.unlink(md_file_path)

        if result.returncode != 0:
            print(f"Error converting markdown to PDF: {result.stderr.decode()}")
            return None
        else:
            print(f"Markdown converted to PDF and saved to {pdf_file_path}")
            return pdf_file_path