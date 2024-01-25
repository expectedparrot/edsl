import os
from edsl.agents import AgentList
from docx import Document
from tempfile import NamedTemporaryFile


def test_writing_to_docx():
    a = AgentList().example()

    with NamedTemporaryFile(suffix=".docx", delete=False) as f:
        doc = a.docx()
        doc.save(f.name)

        # Check if the file exists
        assert os.path.exists(f.name), "The file does not exist"

        # Check if the file is a docx
        assert f.name.endswith(".docx"), "The file is not a .docx file"

        # Check if the file is not empty
        doc_size = os.path.getsize(f.name)
        assert doc_size > 0, "The file is empty"

        # Optional: Check for specific content
        # You need to know what content to expect
    # Clean up: delete the file after test
    os.remove(f.name)
