import pytest
import tempfile
from unittest.mock import patch, MagicMock
from edsl.scenarios.DocxScenario import DocxScenario

class TestDocxScenario:
    def test_init(self):
        # Test initialization with mocked Document
        mock_document = MagicMock()
        with patch('docx.Document', return_value=mock_document):
            docx_scenario = DocxScenario("dummy.docx")
            assert docx_scenario.docx_path == "dummy.docx"
            assert docx_scenario.doc == mock_document
    
    def test_get_scenario_dict(self):
        # Create mock paragraphs
        mock_paragraph1 = MagicMock()
        mock_paragraph1.text = "Paragraph 1 content"
        mock_paragraph2 = MagicMock()
        mock_paragraph2.text = "Paragraph 2 content"
        
        # Create mock document with paragraphs
        mock_document = MagicMock()
        mock_document.paragraphs = [mock_paragraph1, mock_paragraph2]
        
        # Test get_scenario_dict method
        with patch('docx.Document', return_value=mock_document):
            docx_scenario = DocxScenario("test.docx")
            result = docx_scenario.get_scenario_dict()
            
            # Verify results
            assert result["file_path"] == "test.docx"
            assert result["text"] == "Paragraph 1 content\nParagraph 2 content"
    
    def test_get_scenario_dict_empty_document(self):
        # Create mock document without paragraphs
        mock_document = MagicMock()
        mock_document.paragraphs = []
        
        # Test get_scenario_dict method with empty document
        with patch('docx.Document', return_value=mock_document):
            docx_scenario = DocxScenario("empty.docx")
            result = docx_scenario.get_scenario_dict()
            
            # Verify results
            assert result["file_path"] == "empty.docx"
            assert result["text"] == ""

if __name__ == "__main__":
    pytest.main()