from typing import Optional, Dict
import os
import nbformat
from nbconvert.exporters import LatexExporter


class NotebookToLaTeX:
    """
    A class for converting Jupyter notebooks to LaTeX with proper directory structure.
    """

    def __init__(self, notebook):
        """
        Initialize with a Notebook instance.

        :param notebook: An instance of the Notebook class
        """
        self.notebook = notebook
        self.latex_exporter = LatexExporter()
        self._configure_exporter()

    def _configure_exporter(self):
        """Configure the LaTeX exporter with default settings."""
        self.latex_exporter.exclude_input_prompt = True
        self.latex_exporter.exclude_output_prompt = True
        self.latex_exporter.template_name = "classic"

    def _create_makefile(self, filename: str, output_dir: str):
        """Create a Makefile for the LaTeX project."""
        makefile_content = f"""# Makefile for {filename}
all: pdf

pdf: {filename}.pdf

{filename}.pdf: {filename}.tex
\tpdflatex {filename}.tex
\tpdflatex {filename}.tex  # Run twice for references
\tbibtex {filename}       # Run bibtex if needed
\tpdflatex {filename}.tex  # Run one more time for bibtex

clean:
\trm -f *.aux *.log *.out *.toc *.pdf *.bbl *.blg
"""
        makefile_path = os.path.join(output_dir, "Makefile")
        with open(makefile_path, "w") as f:
            f.write(makefile_content)

    def _create_readme(self, filename: str, output_dir: str):
        """Create a README file with usage instructions."""
        readme_content = f"""# {filename}

This folder contains the LaTeX version of your Jupyter notebook.

Files:
- {filename}.tex: Main LaTeX file
- Makefile: Build automation

To compile the PDF:
1. Make sure you have a LaTeX distribution installed (e.g., TexLive)
2. Run `make` in this directory
3. The output will be {filename}.pdf

To clean up build files:
- Run `make clean`
"""
        readme_path = os.path.join(output_dir, "README.md")
        with open(readme_path, "w") as f:
            f.write(readme_content)

    def convert(self, filename: str, output_dir: Optional[str] = None):
        """
        Convert the notebook to LaTeX and create a project directory.

        :param filename: Name for the output files (without extension)
        :param output_dir: Optional directory path. If None, uses filename as directory
        """
        # Use filename as directory if no output_dir specified
        output_dir = output_dir or filename

        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

        # Convert notebook to nbformat
        notebook_node = nbformat.from_dict(self.notebook.data)

        # Convert to LaTeX
        body, resources = self.latex_exporter.from_notebook_node(notebook_node)

        # Write the main tex file
        output_file_path = os.path.join(output_dir, f"{filename}.tex")
        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write(body)

        # Write additional resources (images, etc.)
        if resources.get("outputs"):
            for fname, data in resources["outputs"].items():
                resource_path = os.path.join(output_dir, fname)
                with open(resource_path, "wb") as f:
                    f.write(data)

        # Create supporting files
        self._create_makefile(filename, output_dir)
        self._create_readme(filename, output_dir)

    def set_template(self, template_name: str):
        """
        Set the LaTeX template to use.

        :param template_name: Name of the template (e.g., 'classic', 'article')
        """
        self.latex_exporter.template_name = template_name

    def set_template_options(self, options: Dict):
        """
        Set additional template options.

        :param options: Dictionary of template options
        """
        for key, value in options.items():
            setattr(self.latex_exporter, key, value)


# Example usage:
if __name__ == "__main__":
    from .. import Notebook

    # Create or load a notebook
    notebook = Notebook.example()

    # Create converter and convert
    converter = NotebookToLaTeX(notebook)
    converter.convert("example_output")

    # Example with custom template options
    converter.set_template_options(
        {
            "exclude_input": True,  # Hide input cells
            "exclude_output": False,  # Show output cells
        }
    )
    converter.convert("example_output_custom")
