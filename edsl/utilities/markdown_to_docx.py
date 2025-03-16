from typing import Optional
import subprocess
import os
from pathlib import Path
import tempfile


class MarkdownToDocx:
    def __init__(self, markdown_content: str, filename: Optional[str] = None):
        """
        Initialize the converter with markdown content.

        Args:
            markdown_content (str): The markdown content to be converted
        """
        self.markdown_content = markdown_content
        self.filename = filename
        self._check_pandoc()

    def _check_pandoc(self):
        """Check if pandoc is installed and accessible."""
        try:
            subprocess.run(["pandoc", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError(
                "Pandoc is not installed or not found in PATH. "
                "Please install pandoc before using this converter."
            )

    def convert(self, output_path: str, **options) -> bool:
        """
        Convert the markdown content to DOCX.

        Args:
            output_path (str): Path where the DOCX should be saved
            **options: Additional conversion options
                reference_doc (str): Path to reference docx for styling
                toc (bool): Include table of contents (default: False)
                number_sections (bool): Number sections (default: False)
                highlight_style (str): Code highlighting style (default: "tango")

        Returns:
            bool: True if conversion was successful, False otherwise
        """
        # Ensure output directory exists
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build pandoc command
        cmd = ["pandoc", "-f", "markdown", "-t", "docx", "-o", str(output_path)]

        # Add reference doc if provided
        if "reference_doc" in options:
            ref_doc = Path(options["reference_doc"])
            if ref_doc.exists():
                cmd.extend(["--reference-doc", str(ref_doc)])
            else:
                print(f"Warning: Reference document {ref_doc} not found")

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
            print(f"Error converting markdown to DOCX: {e.stderr}")
            return False

    def preview(self) -> str:
        """
        Generate a temporary DOCX and return its path.

        Returns:
            str: Path to the temporary DOCX file
        """
        temp_dir = tempfile.mkdtemp()
        if self.filename:
            temp_docx = os.path.join(temp_dir, self.filename)
        else:
            temp_docx = os.path.join(temp_dir, "preview.docx")

        if self.convert(temp_docx):
            from edsl.scenarios.FileStore import FileStore

            return FileStore(path=temp_docx)

        return None

    def create_template(self, output_path: str) -> bool:
        """
        Create a reference DOCX template that can be modified for styling.

        Args:
            output_path (str): Path where the template should be saved

        Returns:
            bool: True if template was created successfully, False otherwise
        """
        try:
            cmd = ["pandoc", "--print-default-data-file", "reference.docx"]

            with open(output_path, "wb") as f:
                subprocess.run(cmd, stdout=f, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error creating template: {e.stderr}")
            return False
