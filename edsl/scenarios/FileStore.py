import base64
import io
import tempfile
import mimetypes
import os
from typing import Dict, Any, IO, Optional
import requests
from urllib.parse import urlparse

import google.generativeai as genai

from edsl import Scenario
from edsl.utilities.decorators import add_edsl_version, remove_edsl_version
from edsl.utilities.utilities import is_notebook


def view_pdf(pdf_path):
    import os
    import subprocess

    if is_notebook():
        from IPython.display import IFrame
        from IPython.display import display, HTML

        # Replace 'path/to/your/file.pdf' with the actual path to your PDF file
        IFrame(pdf_path, width=700, height=600)
        display(HTML(f'<a href="{pdf_path}" target="_blank">Open PDF</a>'))
        return

    if os.path.exists(pdf_path):
        try:
            if (os_name := os.name) == "posix":
                # for cool kids
                subprocess.run(["open", pdf_path], check=True)  # macOS
            elif os_name == "nt":
                os.startfile(pdf_path)  # Windows
            else:
                subprocess.run(["xdg-open", pdf_path], check=True)  # Linux
        except Exception as e:
            print(f"Error opening PDF: {e}")
    else:
        print("PDF file was not created successfully.")


class FileStore(Scenario):
    def __init__(
        self,
        path: Optional[str] = None,
        mime_type: Optional[str] = None,
        binary: Optional[bool] = None,
        suffix: Optional[str] = None,
        base64_string: Optional[str] = None,
        external_locations: Optional[Dict[str, str]] = None,
        **kwargs,
    ):
        if path is None and "filename" in kwargs:
            path = kwargs["filename"]
        self.path = path
        self.suffix = suffix or path.split(".")[-1]
        self.binary = binary or False
        self.mime_type = (
            mime_type or mimetypes.guess_type(path)[0] or "application/octet-stream"
        )
        self.base64_string = base64_string or self.encode_file_to_base64_string(path)
        self.external_locations = external_locations or {}
        super().__init__(
            {
                "path": self.path,
                "base64_string": self.base64_string,
                "binary": self.binary,
                "suffix": self.suffix,
                "mime_type": self.mime_type,
                "external_locations": self.external_locations,
            }
        )

    def __str__(self):
        return "FileStore: self.path"

    @classmethod
    def example(self):
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Hello, World!")

        return self(path=f.name)

    @property
    def size(self) -> int:
        return os.path.getsize(self.path)

    def upload_google(self, refresh: bool = False) -> None:
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        google_info = genai.upload_file(self.path, mime_type=self.mime_type)
        self.external_locations["google"] = google_info.to_dict()

    @classmethod
    @remove_edsl_version
    def from_dict(cls, d):
        # return cls(d["filename"], d["binary"], d["suffix"], d["base64_string"])
        return cls(**d)

    def __repr__(self):
        return f"FileStore(path='{self.path}')"

    def encode_file_to_base64_string(self, file_path: str):
        try:
            # Attempt to open the file in text mode
            with open(file_path, "r") as text_file:
                # Read the text data
                text_data = text_file.read()
                # Encode the text data to a base64 string
                base64_encoded_data = base64.b64encode(text_data.encode("utf-8"))
        except UnicodeDecodeError:
            # If reading as text fails, open the file in binary mode
            with open(file_path, "rb") as binary_file:
                # Read the binary data
                binary_data = binary_file.read()
                # Encode the binary data to a base64 string
                base64_encoded_data = base64.b64encode(binary_data)
                self.binary = True
        # Convert the base64 bytes to a string
        base64_string = base64_encoded_data.decode("utf-8")

        return base64_string

    def open(self) -> "IO":
        if self.binary:
            return self.base64_to_file(self["base64_string"], is_binary=True)
        else:
            return self.base64_to_text_file(self["base64_string"])

    @staticmethod
    def base64_to_text_file(base64_string) -> "IO":
        # Decode the base64 string to bytes
        text_data_bytes = base64.b64decode(base64_string)

        # Convert bytes to string
        text_data = text_data_bytes.decode("utf-8")

        # Create a StringIO object from the text data
        text_file = io.StringIO(text_data)

        return text_file

    @staticmethod
    def base64_to_file(base64_string, is_binary=True):
        # Decode the base64 string to bytes
        file_data = base64.b64decode(base64_string)

        if is_binary:
            # Create a BytesIO object for binary data
            return io.BytesIO(file_data)
        else:
            # Convert bytes to string for text data
            text_data = file_data.decode("utf-8")
            # Create a StringIO object for text data
            return io.StringIO(text_data)

    def to_tempfile(self, suffix=None):
        if suffix is None:
            suffix = self.suffix
        if self.binary:
            file_like_object = self.base64_to_file(
                self["base64_string"], is_binary=True
            )
        else:
            file_like_object = self.base64_to_text_file(self["base64_string"])

        # Create a named temporary file
        mode = "wb" if self.binary else "w"
        temp_file = tempfile.NamedTemporaryFile(
            delete=False, suffix="." + suffix, mode=mode
        )

        if self.binary:
            temp_file.write(file_like_object.read())
        else:
            temp_file.write(file_like_object.read())

        temp_file.close()

        return temp_file.name

    def view(self, max_size: int = 300) -> None:
        if self.suffix == "pdf":
            view_pdf(self.path)

        if self.suffix == "png" or self.suffix == "jpg" or self.suffix == "jpeg":
            if is_notebook():
                from IPython.display import Image
                from PIL import Image as PILImage

                if max_size:
                    # Open the image using Pillow
                    with PILImage.open(self.path) as img:
                        # Get original width and height
                        original_width, original_height = img.size

                        # Calculate the scaling factor
                        scale = min(
                            max_size / original_width, max_size / original_height
                        )

                        # Calculate new dimensions
                        new_width = int(original_width * scale)
                        new_height = int(original_height * scale)

                        return Image(self.path, width=new_width, height=new_height)
                else:
                    return Image(self.path)

    def push(
        self, description: Optional[str] = None, visibility: str = "unlisted"
    ) -> dict:
        """
        Push the object to Coop.
        :param description: The description of the object to push.
        :param visibility: The visibility of the object to push.
        """
        scenario_version = Scenario.from_dict(self.to_dict())
        if description is None:
            description = "File: " + self.path
        info = scenario_version.push(description=description, visibility=visibility)
        return info

    @classmethod
    def pull(cls, uuid: str, expected_parrot_url: Optional[str] = None) -> "FileStore":
        """
        :param uuid: The UUID of the object to pull.
        :param expected_parrot_url: The URL of the Parrot server to use.
        :return: The object pulled from the Parrot server.
        """
        scenario_version = Scenario.pull(uuid, expected_parrot_url=expected_parrot_url)
        return cls.from_dict(scenario_version.to_dict())

    @classmethod
    def from_url(
        cls,
        url: str,
        download_path: Optional[str] = None,
        mime_type: Optional[str] = None,
    ) -> "FileStore":
        """
        :param url: The URL of the file to download.
        :param download_path: The path to save the downloaded file.
        :param mime_type: The MIME type of the file. If None, it will be guessed from the file extension.
        """

        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raises an HTTPError for bad responses

        # Get the filename from the URL if download_path is not provided
        if download_path is None:
            filename = os.path.basename(urlparse(url).path)
            if not filename:
                filename = "downloaded_file"
            # download_path = filename
            download_path = os.path.join(os.getcwd(), filename)

        # Ensure the directory exists
        os.makedirs(os.path.dirname(download_path), exist_ok=True)

        # Write the file
        with open(download_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)

        # Create and return a new File instance
        return cls(download_path, mime_type=mime_type)


class CSVFileStore(FileStore):
    @classmethod
    def example(cls):
        from edsl.results.Results import Results

        r = Results.example()
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            r.to_csv(filename=f.name)

        return cls(f.name)

    def view(self):
        import pandas as pd

        return pd.read_csv(self.to_tempfile())


class PDFFileStore(FileStore):
    def view(self):
        pdf_path = self.to_tempfile()
        print(f"PDF path: {pdf_path}")  # Print the path to ensure it exists
        import os
        import subprocess

        if os.path.exists(pdf_path):
            try:
                if os.name == "posix":
                    # for cool kids
                    subprocess.run(["open", pdf_path], check=True)  # macOS
                elif os.name == "nt":
                    os.startfile(pdf_path)  # Windows
                else:
                    subprocess.run(["xdg-open", pdf_path], check=True)  # Linux
            except Exception as e:
                print(f"Error opening PDF: {e}")
        else:
            print("PDF file was not created successfully.")

    @classmethod
    def example(cls):
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

        return cls(f.name)


class PNGFileStore(FileStore):
    @classmethod
    def example(cls):
        import textwrap

        png_string = textwrap.dedent(
            """\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x01\x00\x00\x00\x01\x00\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0cIDAT\x08\xd7c\x00\x01"""
        )
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(png_string.encode())

        return cls(f.name)

    def view(self):
        import matplotlib.pyplot as plt
        import matplotlib.image as mpimg

        img = mpimg.imread(self.to_tempfile())
        plt.imshow(img)
        plt.show()


class SQLiteFileStore(FileStore):
    @classmethod
    def example(cls):
        import sqlite3
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
            conn = sqlite3.connect(f.name)
            c = conn.cursor()
            c.execute("""CREATE TABLE stocks (date text)""")
            conn.commit()

            return cls(f.name)

    def view(self):
        import subprocess
        import os

        sqlite_path = self.to_tempfile()
        os.system(f"sqlite3 {sqlite_path}")


class HTMLFileStore(FileStore):
    @classmethod
    def example(cls):
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            f.write("<html><body><h1>Test</h1></body></html>".encode())

        return cls(f.name)

    def view(self):
        import webbrowser

        html_path = self.to_tempfile()
        webbrowser.open("file://" + html_path)


if __name__ == "__main__":
    # file_path = "../conjure/examples/Ex11-2.sav"
    # fs = FileStore(file_path)
    # info = fs.push()
    # print(info)

    # fs = CSVFileStore.example()
    # fs.to_tempfile()
    # print(fs.view())

    # fs = PDFFileStore.example()
    # fs.view()

    # fs = PDFFileStore("paper.pdf")
    # fs.view()
    # from edsl import Conjure
    pass
    # fs = PNGFileStore("logo.png")
    # fs.view()
    # fs.upload_google()

    # c = Conjure(datafile_name=fs.to_tempfile())
    # f = PDFFileStore("paper.pdf")
    # print(f.to_tempfile())
    # f.push()
