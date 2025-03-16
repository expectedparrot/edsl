import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
from edsl.scenarios.PdfExtractor import PdfExtractor

class TestPdfExtractor:
    def test_init(self):
        # Test initialization with a valid path
        with tempfile.NamedTemporaryFile(suffix='.pdf') as temp_file:
            extractor = PdfExtractor(temp_file.name)
            assert extractor.pdf_path == temp_file.name
    
    def test_check_pymupdf_missing(self):
        # Test when pymupdf is not installed
        with tempfile.NamedTemporaryFile(suffix='.pdf') as temp_file:
            with patch('importlib.util.find_spec', return_value=None):
                extractor = PdfExtractor(temp_file.name)
                assert extractor._has_pymupdf is False
    
    def test_check_pymupdf_present(self):
        # Test when pymupdf is installed
        with tempfile.NamedTemporaryFile(suffix='.pdf') as temp_file:
            with patch('importlib.util.find_spec', return_value=MagicMock()):
                extractor = PdfExtractor(temp_file.name)
                assert extractor._has_pymupdf is True
    
    def test_get_pdf_dict_missing_file(self):
        # Test with non-existent file
        extractor = PdfExtractor("nonexistent.pdf")
        with pytest.raises(FileNotFoundError, match="The file .* does not exist"):
            extractor.get_pdf_dict()
    
    def test_get_pdf_dict_missing_pymupdf(self):
        # Test when pymupdf is not installed
        with tempfile.NamedTemporaryFile(suffix='.pdf') as temp_file:
            with patch.object(PdfExtractor, '_check_pymupdf', return_value=False), \
                 patch('os.path.exists', return_value=True):
                extractor = PdfExtractor(temp_file.name)
                with pytest.raises(ImportError, match="The 'fitz' module .* is required"):
                    extractor.get_pdf_dict()
    
    def test_get_pdf_dict_success(self):
        # Test successful PDF extraction
        with tempfile.NamedTemporaryFile(suffix='.pdf') as temp_file:
            # Create a mock for fitz and its Document object
            mock_document = MagicMock()
            # Setup blocks format for 'blocks' mode in get_text
            mock_blocks = [
                (0, 0, 100, 100, "Test text block 1", 0, 0, 0),
                (0, 200, 100, 300, "Test text block 2", 0, 0, 0)
            ]
            mock_document.load_page.return_value.get_text.return_value = mock_blocks
            mock_document.__len__.return_value = 1
            
            # Create a mock for fitz module
            mock_fitz = MagicMock()
            mock_fitz.open.return_value = mock_document
            
            # Patch imports and methods
            with patch.dict('sys.modules', {'fitz': mock_fitz}), \
                 patch.object(PdfExtractor, '_check_pymupdf', return_value=True), \
                 patch('importlib.util.find_spec', return_value=MagicMock()), \
                 patch('os.path.exists', return_value=True), \
                 patch('os.path.basename', return_value="test.pdf"):
                
                extractor = PdfExtractor(temp_file.name)
                result = extractor.get_pdf_dict()
                
                # Verify results
                assert result['filename'] == "test.pdf"
                assert "Test text block 1" in result['text']
                assert "Test text block 2" in result['text']
                
                # Verify method calls
                mock_document.load_page.assert_called_once_with(0)
                mock_document.load_page.return_value.get_text.assert_called_once_with("blocks")

if __name__ == "__main__":
    pytest.main()