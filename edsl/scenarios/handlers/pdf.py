import os
import base64

from edsl.scenarios.file_methods import FileMethods


class PdfMethods(FileMethods):

    suffix = "pdf"

    def view_system(self):
        import os
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

    def view_notebook(self):
        from IPython.display import HTML, display

        with open(self.path, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode("utf-8")

        html = f"""
        <iframe
            src="data:application/pdf;base64,{base64_pdf}"
            width="800px"
            height="800px"
            type="application/pdf"
        ></iframe>
        """
        display(HTML(html))
        return

    def example(self):
        import textwrap

        pdf_string = textwrap.dedent(
            """\
        %PDF-1.4
        1 0 obj
        << /Type /Catalog /Pages 2 0 R >>
        endobj
        2 0 obj
        << /Type /Pages /Kids [3 0 R] /Count 1 >>
        endobj
        3 0 obj
        << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>
        endobj
        4 0 obj
        << /Length 44 >>
        stream
        BT
        /F1 24 Tf
        100 700 Td
        (Hello, World!) Tj
        ET
        endstream
        endobj
        5 0 obj
        << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
        endobj
        6 0 obj
        << /ProcSet [/PDF /Text] /Font << /F1 5 0 R >> >>
        endobj
        xref
        0 7
        0000000000 65535 f 
        0000000010 00000 n 
        0000000053 00000 n 
        0000000100 00000 n 
        0000000173 00000 n 
        0000000232 00000 n 
        0000000272 00000 n 
        trailer
        << /Size 7 /Root 1 0 R >>
        startxref
        318
        %%EOF"""
        )
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_string.encode())

        return f.name
