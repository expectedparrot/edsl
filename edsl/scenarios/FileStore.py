from edsl import Scenario
import base64
import io
import tempfile
from typing import Optional


class FileStore(Scenario):
    def __init__(
        self,
        filename: str,
        binary: Optional[bool] = None,
        suffix: Optional[str] = None,
        base64_string: Optional[str] = None,
    ):
        self.filename = filename
        self.suffix = suffix or "." + filename.split(".")[-1]
        self.binary = binary or False
        self.base64_string = base64_string or self.encode_file_to_base64_string(
            filename
        )
        super().__init__(
            {
                "filename": self.filename,
                "base64_string": self.base64_string,
                "binary": self.binary,
                "suffix": self.suffix,
            }
        )

    @classmethod
    def from_dict(cls, d):
        return cls(d["filename"], d["binary"], d["suffix"], d["base64_string"])

    def __repr__(self):
        return f"FileStore(filename='{self.filename}', binary='{self.binary}', 'suffix'={self.suffix})"

    def encode_file_to_base64_string(self, file_path):
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

    def open(self):
        if self.binary:
            return self.base64_to_file(self["base64_string"], is_binary=True)
        else:
            return self.base64_to_text_file(self["base64_string"])

    @staticmethod
    def base64_to_text_file(base64_string):
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
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, mode=mode)

        if self.binary:
            temp_file.write(file_like_object.read())
        else:
            temp_file.write(file_like_object.read())

        temp_file.close()

        return temp_file.name

    def push(self, description=None):
        scenario_version = Scenario.from_dict(self.to_dict())
        if description is None:
            description = "File: " + self["filename"]
        info = scenario_version.push(description=description)
        return info

    @classmethod
    def pull(cls, uuid):
        scenario_version = Scenario.pull(uuid)
        return cls.from_dict(scenario_version.to_dict())


class CSVFileStore(FileStore):
    def __init__(
        self,
        filename,
        binary: Optional[bool] = None,
        suffix: Optional[str] = None,
        base64_string: Optional[str] = None,
    ):
        super().__init__(
            filename, binary=binary, base64_string=base64_string, suffix=".csv"
        )

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
    def __init__(self, filename):
        super().__init__(filename, suffix=".pdf")

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
    def __init__(self, filename):
        super().__init__(filename, suffix=".png")

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
    def __init__(self, filename):
        super().__init__(filename, suffix=".sqlite")

    @classmethod
    def example(cls):
        import sqlite3
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
            conn = sqlite3.connect(f.name)
            c = conn.cursor()
            c.execute("""CREATE TABLE stocks (date text)""")
            conn.commit()

    def view(self):
        import subprocess
        import os

        sqlite_path = self.to_tempfile()
        os.system(f"sqlite3 {sqlite_path}")


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

    fs = PNGFileStore("robot.png")
    fs.view()

    # c = Conjure(datafile_name=fs.to_tempfile())
    # f = PDFFileStore("paper.pdf")
    # print(f.to_tempfile())
    # f.push()
