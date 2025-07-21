"""
Template-based report generation for EDSL datasets.

This module provides the TemplateReportGenerator class that handles Jinja2-based
report generation with support for various output formats including text, HTML, 
PDF, and DOCX using pandoc for conversions.
"""

from typing import Optional, Union, List, TYPE_CHECKING
import warnings

if TYPE_CHECKING:
    from docx import Document
    from ..scenarios.file_store import FileStore


class TemplateReportGenerator:
    """
    Handles template-based report generation for EDSL datasets.

    This class encapsulates the logic for generating reports using Jinja2 templates,
    with support for multiple output formats using pandoc for conversions.
    """

    def __init__(self, dataset):
        """
        Initialize the report generator with a dataset.

        Args:
            dataset: The dataset object to generate reports from
        """
        self.dataset = dataset

    @staticmethod
    def _is_pandoc_available() -> bool:
        """Check if pandoc is available on the system."""
        try:
            import subprocess

            subprocess.run(["pandoc", "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def generate_report(
        self,
        template: str,
        *fields: Optional[str],
        top_n: Optional[int] = None,
        remove_prefix: bool = True,
        return_string: bool = False,
        format: str = "text",
        filename: Optional[str] = None,
        separator: str = "\n\n",
        observation_title_template: Optional[str] = None,
        explode: bool = False,
        filestore: bool = False,
    ) -> Optional[Union[str, "Document", List, "FileStore"]]:
        """Generates a report using a Jinja2 template for each row in the dataset."""
        try:
            from jinja2 import Template
        except ImportError:
            from .exceptions import DatasetImportError

            raise DatasetImportError(
                "The jinja2 package is required for template-based reports. Install it with 'pip install jinja2'."
            )

        # Validate format
        valid_formats = ["text", "html", "pdf", "docx"]
        if format.lower() not in valid_formats:
            from .exceptions import DatasetExportError

            raise DatasetExportError(
                f"Unsupported format: {format}. Supported formats are: {', '.join(valid_formats)}."
            )

        # Check pandoc availability for non-text formats
        if format.lower() != "text" and not self._is_pandoc_available():
            from .exceptions import DatasetExportError

            raise DatasetExportError(
                f"Pandoc is required for {format} output but is not installed or not available in PATH. "
                "Please install pandoc (https://pandoc.org/installing.html) or use format='text'."
            )

        # If no fields specified, use all columns
        if not fields:
            fields = self.dataset.relevant_columns()

        # Validate all fields exist
        for field in fields:
            if field not in self.dataset.relevant_columns():
                from .exceptions import DatasetKeyError

                raise DatasetKeyError(f"Field '{field}' not found in dataset")

        # Get data as list of dictionaries
        list_of_dicts = self.dataset.to_dicts(remove_prefix=remove_prefix)

        # Apply top_n limit if specified
        if top_n is not None:
            list_of_dicts = list_of_dicts[:top_n]

        # Filter to only include requested fields if specified
        list_of_dicts = self._filter_fields(list_of_dicts, fields, remove_prefix)

        # Create Jinja2 template
        jinja_template = Template(template)

        # Render template for each row
        rendered_reports = self._render_templates(jinja_template, list_of_dicts)

        # Set up observation title template
        if observation_title_template is None:
            observation_title_template = "Observation {{ index }}"

        # Create observation title Jinja2 template
        title_template = Template(observation_title_template)

        # Handle filestore logic - generate temporary filename if needed
        effective_filename = filename
        if filestore and not filename:
            # Generate a temporary filename based on format
            import tempfile
            import os

            format_extensions = {
                "text": ".txt",
                "html": ".html",
                "pdf": ".pdf",
                "docx": ".docx",
            }
            extension = format_extensions.get(format.lower(), ".txt")

            if explode:
                # For explode mode, create a template filename
                temp_dir = tempfile.mkdtemp()
                effective_filename = os.path.join(
                    temp_dir, f"report_{{index}}{extension}"
                )
            else:
                # For combined mode, create a single temporary file
                fd, effective_filename = tempfile.mkstemp(suffix=extension)
                os.close(fd)  # Close the file descriptor, we'll write to it later

        # Handle explode mode - create separate files/documents per observation
        if explode:
            result = self._handle_explode_mode(
                rendered_reports,
                list_of_dicts,
                title_template,
                format,
                effective_filename,
            )
            if filestore:
                return self._wrap_explode_result_in_filestore(
                    result, effective_filename
                )
            return result

        # Handle non-explode mode (original combined behavior)
        result = self._handle_combined_mode(
            rendered_reports,
            list_of_dicts,
            title_template,
            format,
            effective_filename,
            separator,
            return_string,
        )
        if filestore:
            return self._wrap_combined_result_in_filestore(
                result, effective_filename, format
            )
        return result

    def _filter_fields(
        self, list_of_dicts: List[dict], fields: tuple, remove_prefix: bool
    ) -> List[dict]:
        """Filter the list of dictionaries to only include requested fields."""
        if fields and remove_prefix:
            # Remove prefixes from field names for filtering
            filter_fields = [
                field.split(".")[-1] if "." in field else field for field in fields
            ]
            return [
                {k: v for k, v in row.items() if k in filter_fields}
                for row in list_of_dicts
            ]
        elif fields:
            # Use exact field names for filtering
            return [
                {k: v for k, v in row.items() if k in fields} for row in list_of_dicts
            ]
        return list_of_dicts

    def _render_templates(self, jinja_template, list_of_dicts: List[dict]) -> List[str]:
        """Render the Jinja2 template for each row of data."""
        rendered_reports = []
        for i, row_data in enumerate(list_of_dicts):
            try:
                # Add index variables to template context
                template_data = row_data.copy()
                template_data["index"] = i + 1
                template_data["index0"] = i
                rendered = jinja_template.render(**template_data)
                rendered_reports.append(rendered)
            except Exception as e:
                from .exceptions import DatasetValueError

                raise DatasetValueError(
                    f"Error rendering template with data {row_data}: {e}"
                )
        return rendered_reports

    def _convert_with_pandoc(
        self, markdown_content: str, output_format: str, temp_dir: str = None
    ) -> Union[str, "Document"]:
        """Use pandoc to convert markdown content to specified format."""
        import subprocess
        import tempfile
        import os

        # Create temporary files
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, dir=temp_dir
        ) as md_file:
            md_file.write(markdown_content)
            md_filename = md_file.name

        # Determine output file extension
        format_extensions = {"html": ".html", "pdf": ".pdf", "docx": ".docx"}

        output_extension = format_extensions.get(
            output_format.lower(), f".{output_format.lower()}"
        )
        output_filename = md_filename.replace(".md", output_extension)

        try:
            # Build pandoc command
            pandoc_cmd = [
                "pandoc",
                md_filename,
                "-o",
                output_filename,
                "--from",
                "markdown",
            ]

            # Add format-specific options
            if output_format.lower() == "pdf":
                pandoc_cmd.extend(["--to", "pdf", "--pdf-engine=xelatex"])
            elif output_format.lower() == "html":
                pandoc_cmd.extend(["--to", "html", "--standalone"])
            elif output_format.lower() == "docx":
                pandoc_cmd.extend(["--to", "docx"])

            # Run pandoc conversion
            subprocess.run(pandoc_cmd, check=True, capture_output=True)

            # Read the result based on format
            if output_format.lower() in ["html"]:
                # Return content as string
                with open(output_filename, "r", encoding="utf-8") as f:
                    result = f.read()
            elif output_format.lower() == "pdf":
                # Return file path or bytes depending on use case
                with open(output_filename, "rb") as f:
                    result = f.read()
            elif output_format.lower() == "docx":
                # Load the generated DOCX
                from docx import Document

                result = Document(output_filename)

            # Clean up temporary files
            os.unlink(md_filename)
            os.unlink(output_filename)

            return result

        except subprocess.CalledProcessError as e:
            # Clean up on error
            if os.path.exists(md_filename):
                os.unlink(md_filename)
            if os.path.exists(output_filename):
                os.unlink(output_filename)
            from .exceptions import DatasetExportError

            stderr_output = (
                e.stderr.decode() if e.stderr else "No error details available"
            )
            raise DatasetExportError(
                f"Pandoc conversion to {output_format} failed: {stderr_output}"
            )

    def _handle_explode_mode(
        self,
        rendered_reports: List[str],
        list_of_dicts: List[dict],
        title_template,
        format: str,
        filename: Optional[str],
    ) -> List:
        """Handle explode mode - create separate files/documents per observation."""
        # Validate filename template when exploding to files
        if filename and not any(
            var in filename
            for var in ["{index}", "{index0}"] + list(list_of_dicts[0].keys())
            if list_of_dicts
        ):
            warnings.warn(
                "When explode=True, filename should contain template variables like {index} "
                "to avoid overwriting files. Example: 'report_{index}.html'"
            )

        results = []

        for i, (rendered_content, row_data) in enumerate(
            zip(rendered_reports, list_of_dicts)
        ):
            # Add index variables to row data for title template
            title_data = row_data.copy()
            title_data["index"] = i + 1
            title_data["index0"] = i

            # Render the observation title
            observation_title = title_template.render(**title_data)

            if format.lower() == "text":
                # Generate individual text content
                individual_content = f"# {observation_title}\n\n{rendered_content}"

                if filename:
                    # Generate filename from template
                    individual_filename = filename.format(
                        index=i + 1, index0=i, **row_data
                    )
                    with open(individual_filename, "w", encoding="utf-8") as f:
                        f.write(individual_content)
                    results.append(individual_filename)
                else:
                    results.append(individual_content)
            else:
                # Use pandoc for other formats
                full_markdown = f"# {observation_title}\n\n{rendered_content}"

                if filename:
                    # Generate filename from template
                    individual_filename = filename.format(
                        index=i + 1, index0=i, **row_data
                    )

                    if format.lower() == "pdf":
                        # For PDF, save bytes to file
                        pdf_data = self._convert_with_pandoc(full_markdown, format)
                        with open(individual_filename, "wb") as f:
                            f.write(pdf_data)
                        results.append(individual_filename)
                    elif format.lower() == "html":
                        # For HTML, save string to file
                        html_content = self._convert_with_pandoc(full_markdown, format)
                        with open(individual_filename, "w", encoding="utf-8") as f:
                            f.write(html_content)
                        results.append(individual_filename)
                    elif format.lower() == "docx":
                        # For DOCX, save document to file
                        doc = self._convert_with_pandoc(full_markdown, format)
                        doc.save(individual_filename)
                        results.append(individual_filename)
                else:
                    # Return converted content
                    converted_content = self._convert_with_pandoc(full_markdown, format)
                    results.append(converted_content)

        if filename:
            print(f"Created {len(results)} individual files")

        return results

    def _handle_combined_mode(
        self,
        rendered_reports: List[str],
        list_of_dicts: List[dict],
        title_template,
        format: str,
        filename: Optional[str],
        separator: str,
        return_string: bool,
    ) -> Optional[Union[str, "Document", bytes]]:
        """Handle non-explode mode (original combined behavior)."""
        if format.lower() == "text":
            return self._create_combined_text(
                rendered_reports,
                list_of_dicts,
                title_template,
                filename,
                separator,
                return_string,
            )
        else:
            return self._create_combined_with_pandoc(
                rendered_reports,
                list_of_dicts,
                title_template,
                format,
                filename,
                return_string,
            )

    def _create_combined_with_pandoc(
        self,
        rendered_reports: List[str],
        list_of_dicts: List[dict],
        title_template,
        format: str,
        filename: Optional[str],
        return_string: bool,
    ) -> Optional[Union[str, "Document", bytes]]:
        """Create a combined document using pandoc for conversion."""
        # Convert all content to one markdown document
        markdown_parts = []
        for i, (rendered_content, row_data) in enumerate(
            zip(rendered_reports, list_of_dicts)
        ):
            # Add index variables to row data for title template
            title_data = row_data.copy()
            title_data["index"] = i + 1
            title_data["index0"] = i

            # Render the observation title
            observation_title = title_template.render(**title_data)

            # Add title and content as markdown
            section_markdown = f"# {observation_title}\n\n{rendered_content}"
            markdown_parts.append(section_markdown)

        # Combine all markdown sections
        if format.lower() == "pdf":
            # Use page breaks for PDF
            full_markdown = "\n\n\\pagebreak\n\n".join(markdown_parts)
        else:
            # Use regular separators for other formats
            full_markdown = "\n\n---\n\n".join(markdown_parts)

        # Convert using pandoc
        converted_content = self._convert_with_pandoc(full_markdown, format)

        # Save to file if filename is provided
        if filename:
            if format.lower() == "pdf":
                with open(filename, "wb") as f:
                    f.write(converted_content)
            elif format.lower() == "html":
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(converted_content)
            elif format.lower() == "docx":
                converted_content.save(filename)

            print(f"Report saved to {filename}")
            return None

        # Handle display and return based on format and context
        from ..utilities.utilities import is_notebook

        is_nb = is_notebook()

        if format.lower() == "html":
            if is_nb and not return_string:
                from IPython.display import display, HTML

                display(HTML(converted_content))
                return None
            return converted_content
        elif format.lower() == "docx":
            # For DOCX, always return the document object
            return converted_content
        elif format.lower() == "pdf":
            # For PDF, return bytes
            return converted_content

    def _create_combined_text(
        self,
        rendered_reports: List[str],
        list_of_dicts: List[dict],
        title_template,
        filename: Optional[str],
        separator: str,
        return_string: bool,
    ) -> Optional[str]:
        """Create a combined text report for all observations."""
        # Handle text format with custom observation titles
        final_report_parts = []

        for i, (rendered_content, row_data) in enumerate(
            zip(rendered_reports, list_of_dicts)
        ):
            # Add index variables to row data for title template
            title_data = row_data.copy()
            title_data["index"] = i + 1
            title_data["index0"] = i

            # Render the observation title
            observation_title = title_template.render(**title_data)

            # Combine title and content
            section_content = f"# {observation_title}\n\n{rendered_content}"
            final_report_parts.append(section_content)

        final_report = separator.join(final_report_parts)

        # Save to file if filename is provided
        if filename:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(final_report)
            print(f"Report saved to {filename}")
            if not return_string:
                return None

        # In notebooks, display the content
        from ..utilities.utilities import is_notebook

        is_nb = is_notebook()
        if is_nb and not return_string:
            from IPython.display import display, HTML

            # Use HTML display to preserve formatting
            display(HTML(f"<pre>{final_report}</pre>"))
            return None

        # Return the string if requested or if not in a notebook
        return final_report

    def _wrap_explode_result_in_filestore(
        self, result: List, filename_template: Optional[str]
    ) -> List["FileStore"]:
        """Wrap exploded results in FileStore objects."""
        from ..scenarios.file_store import FileStore

        if not filename_template:
            # If no filename template was used, result contains content, not filenames
            # Create temporary files for each piece of content
            import tempfile
            import os

            filestore_list = []
            for content in result:
                if isinstance(content, str):
                    # Text content
                    fd, temp_filename = tempfile.mkstemp(suffix=".txt")
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        f.write(content)
                    filestore_list.append(FileStore(temp_filename))
                elif hasattr(content, "save"):
                    # DOCX Document object
                    fd, temp_filename = tempfile.mkstemp(suffix=".docx")
                    os.close(fd)
                    content.save(temp_filename)
                    filestore_list.append(FileStore(temp_filename))
                elif isinstance(content, bytes):
                    # PDF content
                    fd, temp_filename = tempfile.mkstemp(suffix=".pdf")
                    with os.fdopen(fd, "wb") as f:
                        f.write(content)
                    filestore_list.append(FileStore(temp_filename))
                else:
                    # HTML or other string content
                    fd, temp_filename = tempfile.mkstemp(suffix=".html")
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        f.write(str(content))
                    filestore_list.append(FileStore(temp_filename))
            return filestore_list
        else:
            # Result contains filenames, wrap each in FileStore
            return [FileStore(filepath) for filepath in result]

    def _wrap_combined_result_in_filestore(
        self, result, filename: Optional[str], format: str
    ) -> "FileStore":
        """Wrap combined result in a FileStore object."""
        from ..scenarios.file_store import FileStore

        if filename:
            # File was saved, create FileStore from the file
            return FileStore(filename)
        else:
            # Content was returned, create a temporary file
            import tempfile
            import os

            format_extensions = {
                "text": ".txt",
                "html": ".html",
                "pdf": ".pdf",
                "docx": ".docx",
            }
            extension = format_extensions.get(format.lower(), ".txt")

            if isinstance(result, str):
                # Text or HTML content
                fd, temp_filename = tempfile.mkstemp(suffix=extension)
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(result)
                return FileStore(temp_filename)
            elif hasattr(result, "save"):
                # DOCX Document object
                fd, temp_filename = tempfile.mkstemp(suffix=".docx")
                os.close(fd)
                result.save(temp_filename)
                return FileStore(temp_filename)
            elif isinstance(result, bytes):
                # PDF content
                fd, temp_filename = tempfile.mkstemp(suffix=".pdf")
                with os.fdopen(fd, "wb") as f:
                    f.write(result)
                return FileStore(temp_filename)
            else:
                # Fallback for any other content
                fd, temp_filename = tempfile.mkstemp(suffix=extension)
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(str(result))
                return FileStore(temp_filename)
