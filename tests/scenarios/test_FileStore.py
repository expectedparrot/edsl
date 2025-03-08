import pytest
import os
import base64
import pandas as pd
import sqlite3
from io import StringIO, BytesIO
from unittest.mock import patch, MagicMock
from edsl.scenarios import Scenario

from edsl.scenarios import FileStore

from edsl.scenarios.file_methods import FileMethods

file_types = FileMethods.supported_file_types()

import unittest
from unittest.mock import patch, MagicMock


class TestScenario(unittest.TestCase):

    def test_example(self):
        for file_format in file_types:
            try:
                fs = FileStore.example(file_format)
                assert fs is not None
            except RuntimeError as e:
                print(e)
            except ModuleNotFoundError as e:
                print(e)


# @pytest.fixture
# def sample_files(tmp_path):
#     files = {}

#     # Text file
#     text_path = tmp_path / "sample.txt"
#     with open(text_path, "w") as f:
#         f.write("Hello, World!")
#     files["txt"] = str(text_path)

#     # CSV file
#     csv_path = tmp_path / "sample.csv"
#     with open(csv_path, "w") as f:
#         f.write("a,b,c\n1,2,3\n4,5,6")
#     files["csv"] = str(csv_path)

#     # PDF file (mock content)
#     pdf_path = tmp_path / "sample.pdf"
#     with open(pdf_path, "wb") as f:
#         f.write(b"%PDF-1.4 mock content")
#     files["pdf"] = str(pdf_path)

#     # PNG file (mock content)
#     png_path = tmp_path / "sample.png"
#     with open(png_path, "wb") as f:
#         f.write(b"\x89PNG\r\n\x1a\n mock content")
#     files["png"] = str(png_path)

#     # SQLite file
#     sqlite_path = tmp_path / "sample.sqlite"
#     conn = sqlite3.connect(str(sqlite_path))
#     c = conn.cursor()
#     c.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
#     conn.commit()
#     conn.close()
#     files["sqlite"] = str(sqlite_path)

#     # HTML file
#     html_path = tmp_path / "sample.html"
#     with open(html_path, "w") as f:
#         f.write("<html><body><h1>Test</h1></body></html>")
#     files["html"] = str(html_path)

#     return files


# @pytest.mark.parametrize(
#     "file_type,FileStoreClass",
#     [
#         ("txt", FileStore),
#         ("csv", CSVFileStore),
#         ("pdf", PDFFileStore),
#         ("png", PNGFileStore),
#         ("sqlite", SQLiteFileStore),
#         ("html", HTMLFileStore),
#     ],
# )
# def test_filestore_init(sample_files, file_type, FileStoreClass):
#     file_path = sample_files[file_type]
#     fs = FileStoreClass(file_path)
#     # assert fs.filename == os.path.basename(file_path)
#     assert fs.suffix == f"{file_type}"
#     assert isinstance(fs.base64_string, str)


# @pytest.mark.parametrize(
#     "file_type,FileStoreClass",
#     [
#         ("txt", FileStore),
#         ("csv", CSVFileStore),
#         ("pdf", PDFFileStore),
#         ("png", PNGFileStore),
#         ("sqlite", SQLiteFileStore),
#         ("html", HTMLFileStore),
#     ],
# )
# def test_filestore_open(sample_files, file_type, FileStoreClass):
#     file_path = sample_files[file_type]
#     fs = FileStoreClass(file_path)
#     file_obj = fs.open()
#     assert isinstance(file_obj, (StringIO, BytesIO))


# @pytest.mark.parametrize(
#     "file_type,FileStoreClass",
#     [
#         ("txt", FileStore),
#         ("csv", CSVFileStore),
#         ("pdf", PDFFileStore),
#         ("png", PNGFileStore),
#         ("sqlite", SQLiteFileStore),
#         ("html", HTMLFileStore),
#     ],
# )
# def test_filestore_to_tempfile(sample_files, file_type, FileStoreClass):
#     file_path = sample_files[file_type]
#     fs = FileStoreClass(file_path)
#     temp_path = fs.to_tempfile()
#     assert os.path.exists(temp_path)
#     # breakpoint()
#     assert temp_path.endswith(f".{file_type}")
#     os.unlink(temp_path)


# def test_csvfilestore_view(sample_files):
#     csv_fs = CSVFileStore(sample_files["csv"])
#     df = csv_fs.view()
#     assert isinstance(df, pd.DataFrame)
#     assert df.shape == (2, 3)
#     assert list(df.columns) == ["a", "b", "c"]


# @pytest.mark.parametrize(
#     "FileStoreClass", [PDFFileStore, PNGFileStore, SQLiteFileStore, HTMLFileStore]
# )
# def test_filestore_subclasses_view(FileStoreClass):
#     fs = FileStoreClass.example()
#     assert hasattr(fs, "view")
#     assert callable(fs.view)


# @pytest.mark.parametrize(
#     "file_type,FileStoreClass",
#     [
#         ("txt", FileStore),
#         ("csv", CSVFileStore),
#         ("pdf", PDFFileStore),
#         ("png", PNGFileStore),
#         ("sqlite", SQLiteFileStore),
#         ("html", HTMLFileStore),
#     ],
# )
# def test_filestore_push_pull(sample_files, file_type, FileStoreClass):
#     file_path = sample_files[file_type]
#     fs = FileStoreClass(file_path)

#     mock_uuid = f"mock-uuid-{file_type}"
#     mock_info = {"uuid": mock_uuid}

#     # Mock the Scenario.push method
#     with patch.object(Scenario, "push", return_value=mock_info) as mock_push:
#         info = fs.push("Test push")
#         mock_push.assert_called_once()
#         assert info == mock_info

#     # Mock the Scenario.pull method
#     with patch.object(
#         Scenario, "pull", return_value=Scenario(fs.to_dict())
#     ) as mock_pull:
#         pulled_fs = FileStoreClass.pull(mock_uuid)
#         mock_pull.assert_called_once_with(mock_uuid, expected_parrot_url=None)
#         assert pulled_fs.path == fs.path
#         assert pulled_fs.base64_string == fs.base64_string
#         assert pulled_fs.suffix == fs.suffix


if __name__ == "__main__":
    pytest.main([__file__])
