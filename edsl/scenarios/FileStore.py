import base64
import io
import tempfile
import mimetypes
import os
from typing import Dict, Any, IO, Optional

from edsl.scenarios.Scenario import Scenario
from edsl.utilities.remove_edsl_version import remove_edsl_version

from edsl.scenarios.file_methods import FileMethods
from typing import Union
from uuid import UUID

class FileStore(Scenario):
    __documentation__ = "https://docs.expectedparrot.com/en/latest/filestore.html"

    def __init__(
        self,
        path: Optional[str] = None,
        mime_type: Optional[str] = None,
        binary: Optional[bool] = None,
        suffix: Optional[str] = None,
        base64_string: Optional[str] = None,
        external_locations: Optional[Dict[str, str]] = None,
        extracted_text: Optional[str] = None,
        **kwargs,
    ):
        if path is None and "filename" in kwargs:
            path = kwargs["filename"]

        # Check if path is a URL and handle download
        if path and (path.startswith('http://') or path.startswith('https://')):
            temp_filestore = self.from_url(path, mime_type=mime_type)
            path = temp_filestore._path
            mime_type = temp_filestore.mime_type

        self._path = path  # Store the original path privately
        self._temp_path = None  # Track any generated temporary file

        self.suffix = suffix or path.split(".")[-1]
        self.binary = binary or False
        self.mime_type = (
            mime_type or mimetypes.guess_type(path)[0] or "application/octet-stream"
        )
        self.base64_string = base64_string or self.encode_file_to_base64_string(path)
        self.external_locations = external_locations or {}

        self.extracted_text = (
            self.extract_text() if extracted_text is None else extracted_text
        )

        super().__init__(
            {
                "path": path,
                "base64_string": self.base64_string,
                "binary": self.binary,
                "suffix": self.suffix,
                "mime_type": self.mime_type,
                "external_locations": self.external_locations,
                "extracted_text": self.extracted_text,
            }
        )

    @property
    def path(self) -> str:
        """
        Property that returns a valid path to the file content.
        If the original path doesn't exist, generates a temporary file from the base64 content.
        """
        # Check if original path exists and is accessible
        if self._path and os.path.isfile(self._path):
            return self._path

        # If we already have a valid temporary file, use it
        if self._temp_path and os.path.isfile(self._temp_path):
            return self._temp_path

        # Generate a new temporary file from base64 content
        self._temp_path = self.to_tempfile(self.suffix)
        return self._temp_path

    def __str__(self):
        return "FileStore: self.path"

    @classmethod
    def example(cls, example_type="txt"):
        file_methods_class = FileMethods.get_handler(example_type)
        if file_methods_class:
            return cls(file_methods_class().example())
        else:
            print(f"Example for {example_type} is not supported.")

    @property
    def size(self) -> int:
        if self.base64_string != None:
            return (len(self.base64_string) / 4.0) * 3  # from base64 to char size
        return os.path.getsize(self.path)

    def upload_google(self, refresh: bool = False) -> None:
        import google.generativeai as genai

        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        google_info = genai.upload_file(self.path, mime_type=self.mime_type)
        self.external_locations["google"] = google_info.to_dict()

    @classmethod
    @remove_edsl_version
    def from_dict(cls, d):
        # return cls(d["filename"], d["binary"], d["suffix"], d["base64_string"])
        return cls(**d)

    def __repr__(self):
        import reprlib

        r = reprlib.Repr()
        r.maxstring = 20  # Limit strings to 20 chars
        r.maxother = 30  # Limit other types to 30 chars

        params = ", ".join(f"{key}={r.repr(value)}" for key, value in self.data.items())
        return f"{self.__class__.__name__}({params})"

    def _repr_html_(self):
        parent_html = super()._repr_html_()
        from edsl.scenarios.ConstructDownloadLink import ConstructDownloadLink

        link = ConstructDownloadLink(self).html_create_link(self.path, style=None)
        return f"{parent_html}<br>{link}"

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
        except FileNotFoundError:
            print(f"File not found: {file_path}")
            print("Current working directory:", os.getcwd())
            raise
        base64_string = base64_encoded_data.decode("utf-8")

        return base64_string

    def open(self) -> "IO":
        if self.binary:
            return self.base64_to_file(self.base64_string, is_binary=True)
        else:
            return self.base64_to_text_file(self.base64_string)

    def write(self, filename: Optional[str] = None) -> str:
        """
        Write the file content to disk, either to a specified filename or a temporary file.

        Args:
            filename (Optional[str]): The destination filename. If None, creates a temporary file.

        Returns:
            str: The path to the written file.
        """
        # Determine the mode based on binary flag
        mode = "wb" if self.binary else "w"

        # If no filename provided, create a temporary file
        if filename is None:
            from tempfile import NamedTemporaryFile

            with NamedTemporaryFile(delete=False, suffix="." + self.suffix) as f:
                filename = f.name

        # Write the content using the appropriate mode
        try:
            with open(filename, mode) as f:
                content = self.open().read()
                # For text mode, ensure we're writing a string
                if not self.binary and isinstance(content, bytes):
                    content = content.decode("utf-8")
                f.write(content)
                print(f"File written to {filename}")
        except Exception as e:
            print(f"Error writing file: {e}")
            raise

        # return filename

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

    @property
    def text(self):
        if self.binary:
            import warnings

            warnings.warn("This is a binary file.")
        else:
            return self.base64_to_text_file(self.base64_string).read()

    def to_tempfile(self, suffix=None):
        if suffix is None:
            suffix = self.suffix
        if self.binary:
            file_like_object = self.base64_to_file(
                self["base64_string"], is_binary=True
            )
        else:
            file_like_object = self.base64_to_text_file(self.base64_string)

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

    def view(self) -> None:
        handler = FileMethods.get_handler(self.suffix)
        if handler:
            handler(self.path).view()
        else:
            print(f"Viewing of {self.suffix} files is not supported.")

    def extract_text(self) -> str:
        handler = FileMethods.get_handler(self.suffix)
        if handler and hasattr(handler, "extract_text"):
            return handler(self.path).extract_text()

        if not self.binary:
            return self.text

        return None
        # raise TypeError("No text method found for this file type.")

    def push(
        self, 
        description: Optional[str] = None, 
        alias: Optional[str] = None,
        visibility: Optional[str] = "unlisted",
        expected_parrot_url: Optional[str] = None,

    ) -> dict:
        """
        Push the object to Coop.
        :param description: The description of the object to push.
        :param visibility: The visibility of the object to push.
        """
        scenario_version = Scenario.from_dict(self.to_dict())
        if description is None:
            description = "File: " + self.path
        info = scenario_version.push(description=description, visibility=visibility, expected_parrot_url=expected_parrot_url, alias=alias)
        return info

    @classmethod
    def pull(cls, url_or_uuid: Union[str, UUID]) -> "FileStore":
        """
        Pull a FileStore object from Coop.
        
        Args:
            url_or_uuid: Either a UUID string or a URL pointing to the object
            expected_parrot_url: Optional URL for the Parrot server
        
        Returns:
            FileStore: The pulled FileStore object
        """
        scenario_version = Scenario.pull(url_or_uuid)
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
        import requests
        from urllib.parse import urlparse

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

    def create_link(self, custom_filename=None, style=None):
        from edsl.scenarios.ConstructDownloadLink import ConstructDownloadLink

        return ConstructDownloadLink(self).create_link(custom_filename, style)

    def to_pandas(self):
        """
        Convert the file content to a pandas DataFrame if supported by the file handler.

        Returns:
            pandas.DataFrame: The data from the file as a DataFrame

        Raises:
            AttributeError: If the file type's handler doesn't support pandas conversion
        """
        handler = FileMethods.get_handler(self.suffix)
        if handler and hasattr(handler, "to_pandas"):
            return handler(self.path).to_pandas()
        raise AttributeError(
            f"Converting {self.suffix} files to pandas DataFrame is not supported"
        )

    def __getattr__(self, name):
        """
        Delegate pandas DataFrame methods to the underlying DataFrame if this is a CSV file
        """
        if self.suffix == "csv":
            # Get the pandas DataFrame
            df = self.to_pandas()
            # Check if the requested attribute exists in the DataFrame
            if hasattr(df, name):
                return getattr(df, name)
        # If not a CSV or attribute doesn't exist in DataFrame, raise AttributeError
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )

    def html_snippet(self, width: str = "100%", height: str = "500px", file_path_root: Optional[str] = None, **kwargs) -> str:
        """
        Returns an HTML string with an <object> tag for embedding the file in a web page.
        
        Args:
            width (str): Width of the object element. Default is "100%".
            height (str): Height of the object element. Default is "500px".
            file_path_root (Optional[str]): If provided, uses this as the root path instead of self.path.
                The filename will be appended to this root.
            **kwargs: Additional HTML attributes to add to the object tag.
        
        Returns:
            str: HTML string with an <object> tag.
        """
        # Determine the file path to use
        if file_path_root is not None:
            # Use the provided root with the original filename
            filename = os.path.basename(self.path)
            file_path = os.path.join(file_path_root, filename)
        else:
            # Use the default path
            file_path = self.path
        
        # Create attributes string from kwargs
        extra_attrs = " ".join([f'{k}="{v}"' for k, v in kwargs.items()])
        
        # Create the HTML object tag
        html = f'<object data="{file_path}" type="{self.mime_type}" width="{width}" height="{height}" {extra_attrs}>'
        html += f'<p>Unable to display: <a href="{file_path}">Download {os.path.basename(file_path)}</a></p>'
        html += '</object>'
        
        return html


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
    import doctest

    doctest.testmod()

    # fs = FileStore.example("pdf")
    # fs.view()

    formats = FileMethods.supported_file_types()
    for file_type in formats:
        print("Now testinging", file_type)
        fs = FileStore.example(file_type)
        fs.view()
        input("Press Enter to continue...")

    # pdf_example.view()
    # FileStore(pdf_example).view()

    # pdf_methods = methods.get("pdf")
    # file = pdf_methods().example()
    # pdf_methods(file).view()

    # print(FileMethods._handlers)
