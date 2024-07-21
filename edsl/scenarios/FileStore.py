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
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
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
    def __init__(self, filename):
        super().__init__(filename, suffix=".csv")


class PDFFileStore(FileStore):
    def __init__(self, filename):
        super().__init__(filename, suffix=".pdf")


if __name__ == "__main__":
    # file_path = "../conjure/examples/Ex11-2.sav"
    # fs = FileStore(file_path)
    # info = fs.push()
    # print(info)

    # from edsl import Conjure

    # c = Conjure(datafile_name=fs.to_tempfile())
    f = PDFFileStore("paper.pdf")
    # print(f.to_tempfile())
    f.push()
