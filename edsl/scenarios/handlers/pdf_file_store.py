import os
import base64

from ..file_methods import FileMethods


class PdfMethods(FileMethods):
    suffix = "pdf"

    def extract_text(self):
        from PyPDF2 import PdfReader

        # Create a PDF reader object
        reader = PdfReader(self.path)

        # Get number of pages
        num_pages = len(reader.pages)

        # Extract text from all pages
        text = ""
        for page_num in range(num_pages):
            # Get the page object
            page = reader.pages[page_num]
            # Extract text from page
            text += page.extract_text()

        return text

    def view_system(self, width: int = None, height: int = None):
        import subprocess

        if os.path.exists(self.path):
            try:
                if (os_name := os.name) == "posix":
                    subprocess.run(["open", self.path], check=True)  # macOS
                elif os_name == "nt":
                    os.startfile(self.path)  # Windows
                else:
                    subprocess.run(["xdg-open", self.path], check=True)  # Linux
            except Exception as e:
                print(f"Error opening PDF: {e}")
        else:
            print("PDF file was not found.")

    def view_notebook(self, width: int = None, height: int = None):
        from IPython.display import HTML, display

        _width = width if width is not None else 800
        _height = height if height is not None else 800

        with open(self.path, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode("utf-8")

        html = f"""
        <iframe
            src="data:application/pdf;base64,{base64_pdf}"
            width="{_width}px"
            height="{_height}px"
            type="application/pdf"
        ></iframe>
        """
        display(HTML(html))
        return

    def example(self):
        from ...results import Results

        return (
            Results.example().select("answer.how_feeling").first().pdf().to_tempfile()
        )
