"""
Template-based report generation for EDSL datasets.

This module provides the TemplateReportGenerator class that handles Jinja2-based
report generation with support for various output formats including text and DOCX,
with optional markdown formatting.
"""

from typing import Optional, Union, List, TYPE_CHECKING
import warnings

if TYPE_CHECKING:
    from docx import Document


class TemplateReportGenerator:
    """
    Handles template-based report generation for EDSL datasets.
    
    This class encapsulates the logic for generating reports using Jinja2 templates,
    with support for multiple output formats and advanced features like markdown
    conversion to DOCX.
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
        markdown_to_docx: bool = True,
        use_pandoc: bool = True,
    ) -> Optional[Union[str, "Document", List]]:
        """Generates a report using a Jinja2 template for each row in the dataset."""
        try:
            from jinja2 import Template
        except ImportError:
            from .exceptions import DatasetImportError
            raise DatasetImportError(
                "The jinja2 package is required for template-based reports. Install it with 'pip install jinja2'."
            )

        from ..utilities.utilities import is_notebook

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

        # Handle explode mode - create separate files/documents per observation
        if explode:
            return self._handle_explode_mode(
                rendered_reports, list_of_dicts, title_template, format, 
                filename, markdown_to_docx, use_pandoc
            )

        # Handle non-explode mode (original combined behavior)
        return self._handle_combined_mode(
            rendered_reports, list_of_dicts, title_template, format, 
            filename, separator, return_string, markdown_to_docx, use_pandoc
        )

    def _filter_fields(self, list_of_dicts: List[dict], fields: tuple, remove_prefix: bool) -> List[dict]:
        """Filter the list of dictionaries to only include requested fields."""
        if fields and remove_prefix:
            # Remove prefixes from field names for filtering
            filter_fields = [field.split(".")[-1] if "." in field else field for field in fields]
            return [
                {k: v for k, v in row.items() if k in filter_fields}
                for row in list_of_dicts
            ]
        elif fields:
            # Use exact field names for filtering
            return [
                {k: v for k, v in row.items() if k in fields}
                for row in list_of_dicts
            ]
        return list_of_dicts

    def _render_templates(self, jinja_template, list_of_dicts: List[dict]) -> List[str]:
        """Render the Jinja2 template for each row of data."""
        rendered_reports = []
        for i, row_data in enumerate(list_of_dicts):
            try:
                # Add index variables to template context
                template_data = row_data.copy()
                template_data['index'] = i + 1
                template_data['index0'] = i
                rendered = jinja_template.render(**template_data)
                rendered_reports.append(rendered)
            except Exception as e:
                from .exceptions import DatasetValueError
                raise DatasetValueError(f"Error rendering template with data {row_data}: {e}")
        return rendered_reports

    def _convert_markdown_to_docx(self, markdown_content: str, use_pandoc: bool, temp_dir: str = None) -> "Document":
        """Convert markdown content to a DOCX document."""
        if use_pandoc:
            return self._convert_with_pandoc(markdown_content, temp_dir)
        else:
            return self._convert_with_python(markdown_content)

    def _convert_with_pandoc(self, markdown_content: str, temp_dir: str = None) -> "Document":
        """Use pandoc for markdown to DOCX conversion."""
        import subprocess
        import tempfile
        import os
        
        # Check if pandoc is available
        if not self._is_pandoc_available():
            from .exceptions import DatasetExportError
            raise DatasetExportError(
                "Pandoc is not installed or not available in PATH. "
                "To fix this: 1) Install pandoc (https://pandoc.org/installing.html), "
                "2) Set use_pandoc=False to use Python-based conversion, or "
                "3) Use format='text' instead of 'docx' for simple text output."
            )
        
        # Create temporary files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, dir=temp_dir) as md_file:
            md_file.write(markdown_content)
            md_filename = md_file.name
        
        docx_filename = md_filename.replace('.md', '.docx')
        
        try:
            # Run pandoc conversion
            subprocess.run([
                "pandoc", 
                md_filename, 
                "-o", docx_filename,
                "--from", "markdown",
                "--to", "docx"
            ], check=True)
            
            # Load the generated DOCX
            from docx import Document
            doc = Document(docx_filename)
            
            # Clean up temporary files
            os.unlink(md_filename)
            os.unlink(docx_filename)
            
            return doc
            
        except subprocess.CalledProcessError as e:
            # Clean up on error
            if os.path.exists(md_filename):
                os.unlink(md_filename)
            if os.path.exists(docx_filename):
                os.unlink(docx_filename)
            from .exceptions import DatasetExportError
            raise DatasetExportError(f"Pandoc conversion failed: {e}")

    def _convert_with_python(self, markdown_content: str) -> "Document":
        """Use Python-based conversion for markdown to DOCX."""
        try:
            import markdown
            from markdown.extensions import codehilite, fenced_code, tables
            from docx import Document
            from docx.shared import Pt, RGBColor
            from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
            import re
            import html
        except ImportError:
            from .exceptions import DatasetImportError
            raise DatasetImportError(
                "Python-based markdown conversion requires 'markdown' and 'python-docx' packages. "
                "Install with 'pip install markdown python-docx' or set use_pandoc=True to use pandoc."
            )
        
        # Convert markdown to HTML first
        md = markdown.Markdown(extensions=['codehilite', 'fenced_code', 'tables', 'nl2br'])
        html_content = md.convert(markdown_content)
        
        # Create a new document
        doc = Document()
        
        # Parse HTML and convert to DOCX elements
        lines = html_content.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Handle headers
            if line.startswith('<h1>') and line.endswith('</h1>'):
                text = html.unescape(re.sub(r'<[^>]+>', '', line))
                doc.add_heading(text, level=1)
            elif line.startswith('<h2>') and line.endswith('</h2>'):
                text = html.unescape(re.sub(r'<[^>]+>', '', line))
                doc.add_heading(text, level=2)
            elif line.startswith('<h3>') and line.endswith('</h3>'):
                text = html.unescape(re.sub(r'<[^>]+>', '', line))
                doc.add_heading(text, level=3)
            # Handle paragraphs
            elif line.startswith('<p>') and line.endswith('</p>'):
                text = html.unescape(re.sub(r'<[^>]+>', '', line))
                if text.strip():
                    p = doc.add_paragraph()
                    # Handle basic formatting within paragraphs
                    parts = re.split(r'(<strong>.*?</strong>|<em>.*?</em>|<code>.*?</code>)', text)
                    for part in parts:
                        if part.startswith('<strong>') and part.endswith('</strong>'):
                            clean_text = html.unescape(re.sub(r'<[^>]+>', '', part))
                            run = p.add_run(clean_text)
                            run.bold = True
                        elif part.startswith('<em>') and part.endswith('</em>'):
                            clean_text = html.unescape(re.sub(r'<[^>]+>', '', part))
                            run = p.add_run(clean_text)
                            run.italic = True
                        elif part.startswith('<code>') and part.endswith('</code>'):
                            clean_text = html.unescape(re.sub(r'<[^>]+>', '', part))
                            run = p.add_run(clean_text)
                            run.font.name = 'Courier New'
                            run.font.size = Pt(10)
                        else:
                            if part.strip():
                                p.add_run(html.unescape(part))
            # Handle code blocks
            elif '<pre>' in line or '<code>' in line:
                text = html.unescape(re.sub(r'<[^>]+>', '', line))
                if text.strip():
                    p = doc.add_paragraph()
                    run = p.add_run(text)
                    run.font.name = 'Courier New'
                    run.font.size = Pt(10)
            # Handle other content
            else:
                text = html.unescape(re.sub(r'<[^>]+>', '', line))
                if text.strip():
                    doc.add_paragraph(text)
        
        return doc

    def _handle_explode_mode(
        self, rendered_reports: List[str], list_of_dicts: List[dict], 
        title_template, format: str, filename: Optional[str], 
        markdown_to_docx: bool, use_pandoc: bool
    ) -> List:
        """Handle explode mode - create separate files/documents per observation."""
        # Validate filename template when exploding to files
        if filename and not any(var in filename for var in ['{index}', '{index0}'] + list(list_of_dicts[0].keys()) if list_of_dicts):
            warnings.warn(
                "When explode=True, filename should contain template variables like {index} "
                "to avoid overwriting files. Example: 'report_{index}.docx'"
            )
        
        results = []
        
        for i, (rendered_content, row_data) in enumerate(zip(rendered_reports, list_of_dicts)):
            # Add index variables to row data for title template
            title_data = row_data.copy()
            title_data['index'] = i + 1
            title_data['index0'] = i
            
            # Render the observation title
            observation_title = title_template.render(**title_data)
            
            if format.lower() == "docx":
                doc = self._create_docx_document(
                    observation_title, rendered_content, markdown_to_docx, use_pandoc
                )
                
                if filename:
                    # Generate filename from template
                    individual_filename = filename.format(index=i+1, index0=i, **row_data)
                    doc.save(individual_filename)
                    results.append(individual_filename)
                else:
                    results.append(doc)
                    
            elif format.lower() == "text":
                # Generate individual text content
                individual_content = f"# {observation_title}\n\n{rendered_content}"
                
                if filename:
                    # Generate filename from template
                    individual_filename = filename.format(index=i+1, index0=i, **row_data)
                    with open(individual_filename, 'w', encoding='utf-8') as f:
                        f.write(individual_content)
                    results.append(individual_filename)
                else:
                    results.append(individual_content)
        
        if filename:
            print(f"Created {len(results)} individual files")
        
        return results

    def _handle_combined_mode(
        self, rendered_reports: List[str], list_of_dicts: List[dict], 
        title_template, format: str, filename: Optional[str], 
        separator: str, return_string: bool, markdown_to_docx: bool, use_pandoc: bool
    ) -> Optional[Union[str, "Document"]]:
        """Handle non-explode mode (original combined behavior)."""
        if format.lower() == "docx":
            return self._create_combined_docx(
                rendered_reports, list_of_dicts, title_template, 
                filename, markdown_to_docx, use_pandoc
            )
        elif format.lower() == "text":
            return self._create_combined_text(
                rendered_reports, list_of_dicts, title_template, 
                filename, separator, return_string
            )
        else:
            from .exceptions import DatasetExportError
            raise DatasetExportError(
                f"Unsupported format: {format}. Use 'text' or 'docx'."
            )

    def _create_docx_document(
        self, observation_title: str, rendered_content: str, 
        markdown_to_docx: bool, use_pandoc: bool
    ) -> "Document":
        """Create a single DOCX document for an observation."""
        try:
            from docx import Document
            from docx.shared import Pt
        except ImportError:
            from .exceptions import DatasetImportError
            raise DatasetImportError(
                "The python-docx package is required for DOCX export. Install it with 'pip install python-docx'."
            )

        if markdown_to_docx:
            # Convert markdown content to DOCX with proper formatting
            full_markdown = f"# {observation_title}\n\n{rendered_content}"
            return self._convert_markdown_to_docx(full_markdown, use_pandoc)
        else:
            # Use plain text approach (original behavior)
            doc = Document()
            doc.add_heading(observation_title, level=1)
            
            # Add the rendered template content
            lines = rendered_content.split('\n')
            for line in lines:
                if line.strip():
                    doc.add_paragraph(line)
                else:
                    doc.add_paragraph()
            return doc

    def _create_combined_docx(
        self, rendered_reports: List[str], list_of_dicts: List[dict], 
        title_template, filename: Optional[str], markdown_to_docx: bool, use_pandoc: bool
    ) -> Optional["Document"]:
        """Create a combined DOCX document for all observations."""
        try:
            from docx import Document
            from docx.shared import Pt
        except ImportError:
            from .exceptions import DatasetImportError
            raise DatasetImportError(
                "The python-docx package is required for DOCX export. Install it with 'pip install python-docx'."
            )

        if markdown_to_docx:
            # Convert all content to one markdown document
            markdown_parts = []
            for i, (rendered_content, row_data) in enumerate(zip(rendered_reports, list_of_dicts)):
                # Add index variables to row data for title template
                title_data = row_data.copy()
                title_data['index'] = i + 1
                title_data['index0'] = i
                
                # Render the observation title
                observation_title = title_template.render(**title_data)
                
                # Add title and content as markdown
                section_markdown = f"# {observation_title}\n\n{rendered_content}"
                markdown_parts.append(section_markdown)
            
            # Combine all markdown sections
            full_markdown = "\n\n\\pagebreak\n\n".join(markdown_parts)
            doc = self._convert_markdown_to_docx(full_markdown, use_pandoc)
        else:
            # Use plain text approach (original behavior)
            doc = Document()

            for i, (rendered_content, row_data) in enumerate(zip(rendered_reports, list_of_dicts)):
                # Add index variables to row data for title template
                title_data = row_data.copy()
                title_data['index'] = i + 1
                title_data['index0'] = i
                
                # Render the observation title
                observation_title = title_template.render(**title_data)
                
                # Add a heading for each observation
                doc.add_heading(observation_title, level=1)
                
                # Add the rendered template content
                lines = rendered_content.split('\n')
                for line in lines:
                    if line.strip():
                        doc.add_paragraph(line)
                    else:
                        doc.add_paragraph()

                # Add page break between observations except for the last one
                if i < len(rendered_reports) - 1:
                    doc.add_page_break()

        # Save to file if filename is provided
        if filename:
            doc.save(filename)
            print(f"Report saved to {filename}")
            return None

        return doc

    def _create_combined_text(
        self, rendered_reports: List[str], list_of_dicts: List[dict], 
        title_template, filename: Optional[str], separator: str, return_string: bool
    ) -> Optional[str]:
        """Create a combined text report for all observations."""
        # Handle text format with custom observation titles
        final_report_parts = []
        
        for i, (rendered_content, row_data) in enumerate(zip(rendered_reports, list_of_dicts)):
            # Add index variables to row data for title template
            title_data = row_data.copy()
            title_data['index'] = i + 1
            title_data['index0'] = i
            
            # Render the observation title
            observation_title = title_template.render(**title_data)
            
            # Combine title and content
            section_content = f"# {observation_title}\n\n{rendered_content}"
            final_report_parts.append(section_content)
        
        final_report = separator.join(final_report_parts)

        # Save to file if filename is provided
        if filename:
            with open(filename, 'w', encoding='utf-8') as f:
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
