import nbformat
from nbconvert import HTMLExporter
from nbconvert.preprocessors import ExecutePreprocessor


def convert_notebook_to_pdf(notebook_path):
    with open(notebook_path) as f:
        nb = nbformat.read(f, as_version=4)

    # Run the notebook
    ep = ExecutePreprocessor(timeout=600, kernel_name="python")
    ep.preprocess(nb)

    html_exporter = HTMLExporter()
    html_data, resources = html_exporter.from_notebook_node(nb)

    import tempfile

    temporary_file = tempfile.NamedTemporaryFile(suffix=".html")

    with open(temporary_file.name, "w", encoding="utf-8") as f:
        f.write(html_data)

    # open the HTML file
    import webbrowser

    webbrowser.open(temporary_file.name)


if __name__ == "__main__":
    import os
    from edsl import ROOT_DIR

    notebook_path = os.path.join(ROOT_DIR, "integration/notebooks/check_printing.ipynb")
    convert_notebook_to_pdf(notebook_path)
