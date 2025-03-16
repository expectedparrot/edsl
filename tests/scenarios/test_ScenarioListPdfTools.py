import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
from edsl.scenarios import Scenario
from edsl.scenarios.scenario_list_pdf_tools import GoogleDriveDownloader, PdfTools, fetch_and_save_pdf

class TestGoogleDriveDownloader:
    def test_extract_file_id_file_d_format(self):
        # Test extracting file ID from '/file/d/' format
        url = "https://drive.google.com/file/d/1abc123XYZ_-xyz/view?usp=sharing"
        file_id = GoogleDriveDownloader._extract_file_id(url)
        assert file_id == "1abc123XYZ_-xyz"
    
    def test_extract_file_id_open_format(self):
        # Test extracting file ID from 'open?id=' format
        url = "https://drive.google.com/open?id=1abc123XYZ_-xyz"
        file_id = GoogleDriveDownloader._extract_file_id(url)
        assert file_id == "1abc123XYZ_-xyz"
    
    def test_extract_file_id_invalid_url(self):
        # Test with invalid URL format
        url = "https://example.com/not-google-drive"
        file_id = GoogleDriveDownloader._extract_file_id(url)
        assert file_id is None
    
    @patch('requests.Session')
    @patch('tempfile.TemporaryDirectory')
    def test_fetch_from_drive(self, mock_temp_dir, mock_session):
        # Setup mocks
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance
        mock_response = MagicMock()
        mock_response.cookies = {}
        mock_session_instance.get.return_value = mock_response
        
        mock_temp_dir_instance = MagicMock()
        mock_temp_dir_instance.name = "/tmp/mock_temp_dir"
        mock_temp_dir.return_value = mock_temp_dir_instance
        
        # Test fetch_from_drive method
        with patch('builtins.open', MagicMock()), \
             patch('os.path.join', return_value="/tmp/mock_temp_dir/test.pdf"):
            
            url = "https://drive.google.com/file/d/1abc123XYZ_-xyz/view?usp=sharing"
            result = GoogleDriveDownloader.fetch_from_drive(url, "test.pdf")
            
            # Verify the result and method calls
            assert result == "/tmp/mock_temp_dir/test.pdf"
            mock_session_instance.get.assert_called_with(
                "https://drive.google.com/uc?export=download&id=1abc123XYZ_-xyz", 
                stream=True
            )
    
    @patch('requests.Session')
    @patch('tempfile.TemporaryDirectory')
    def test_fetch_from_drive_with_warning(self, mock_temp_dir, mock_session):
        # Setup mocks for the case with download warning
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance
        mock_response = MagicMock()
        mock_response.cookies = {"download_warning": "warning_token"}
        mock_session_instance.get.return_value = mock_response
        
        mock_temp_dir_instance = MagicMock()
        mock_temp_dir_instance.name = "/tmp/mock_temp_dir"
        mock_temp_dir.return_value = mock_temp_dir_instance
        
        # Test fetch_from_drive method with warning cookie
        with patch('builtins.open', MagicMock()), \
             patch('os.path.join', return_value="/tmp/mock_temp_dir/test.pdf"):
            
            url = "https://drive.google.com/file/d/1abc123XYZ_-xyz/view?usp=sharing"
            result = GoogleDriveDownloader.fetch_from_drive(url, "test.pdf")
            
            # Verify the result and method calls
            assert result == "/tmp/mock_temp_dir/test.pdf"
            # Verify the second call for confirmed download
            mock_session_instance.get.assert_called_with(
                "https://drive.google.com/uc?export=download&id=1abc123XYZ_-xyz",
                params={"id": "1abc123XYZ_-xyz", "confirm": "warning_token"},
                stream=True
            )
    
    def test_invalid_url(self):
        # Test with invalid URL
        with pytest.raises(ValueError, match="Invalid Google Drive URL"):
            GoogleDriveDownloader.fetch_from_drive("https://example.com/not-google-drive")

class TestFetchAndSavePdf:
    @patch('requests.get')
    def test_fetch_and_save_pdf(self, mock_get):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.content = b"PDF content"
        mock_get.return_value = mock_response
        
        # Mock tempfile operations
        with patch('tempfile.TemporaryDirectory'), \
             patch('os.path.join', return_value="/tmp/test.pdf"), \
             patch('builtins.open', MagicMock()):
            
            # Call function and check result
            result = fetch_and_save_pdf("https://example.com/test.pdf", "test.pdf")
            mock_get.assert_called_once_with("https://example.com/test.pdf")

class TestPdfTools:
    def test_is_url_valid(self):
        # Test with valid URLs
        assert PdfTools.is_url("https://example.com") is True
        assert PdfTools.is_url("http://example.com/path/to/file.pdf") is True
    
    def test_is_url_invalid(self):
        # Test with invalid URLs and non-URLs
        assert PdfTools.is_url("not-a-url") is False
        assert PdfTools.is_url("") is False
        assert PdfTools.is_url("file.pdf") is False
    
    @patch.object(PdfTools, 'extract_text_from_pdf')
    def test_from_pdf_local_file(self, mock_extract):
        # Setup mock for extract_text_from_pdf
        mock_extract.return_value = [
            Scenario({"filename": "test.pdf", "page": 1, "text": "Page 1 content"}),
            Scenario({"filename": "test.pdf", "page": 2, "text": "Page 2 content"})
        ]
        
        # Test from_pdf with local file
        result = PdfTools.from_pdf("test.pdf", collapse_pages=False)
        mock_extract.assert_called_once_with("test.pdf")
        assert len(result) == 2
        assert result[0]["text"] == "Page 1 content"
        assert result[1]["text"] == "Page 2 content"
    
    @patch.object(PdfTools, 'extract_text_from_pdf')
    def test_from_pdf_collapsed(self, mock_extract):
        # Setup mock for extract_text_from_pdf
        mock_extract.return_value = [
            Scenario({"filename": "test.pdf", "page": 1, "text": "Page 1 content"}),
            Scenario({"filename": "test.pdf", "page": 2, "text": "Page 2 content"})
        ]
        
        # Test from_pdf with collapsed pages
        result = PdfTools.from_pdf("test.pdf", collapse_pages=True)
        assert result["text"] == "Page 1 contentPage 2 content"
    
    @patch.object(PdfTools, 'is_url')
    @patch.object(PdfTools, 'extract_text_from_pdf')
    @patch('edsl.scenarios.scenario_list_pdf_tools.fetch_and_save_pdf')
    def test_from_pdf_url(self, mock_fetch, mock_extract, mock_is_url):
        # Setup mocks
        mock_is_url.return_value = True
        mock_fetch.return_value = "/tmp/test.pdf"
        mock_extract.return_value = [
            Scenario({"filename": "test.pdf", "page": 1, "text": "Page 1 content"})
        ]
        
        # Test from_pdf with URL
        result = PdfTools.from_pdf("https://example.com/test.pdf")
        mock_fetch.assert_called_once_with("https://example.com/test.pdf", "temp_pdf.pdf")
        mock_extract.assert_called_once_with("/tmp/test.pdf")
        assert result[0]["text"] == "Page 1 content"
    
    @patch.object(PdfTools, 'is_url')
    @patch.object(PdfTools, 'extract_text_from_pdf')
    @patch('edsl.scenarios.scenario_list_pdf_tools.GoogleDriveDownloader')
    def test_from_pdf_google_drive(self, mock_downloader, mock_extract, mock_is_url):
        # Setup mocks
        mock_is_url.return_value = True
        mock_downloader.fetch_from_drive.return_value = "/tmp/google_drive.pdf"
        mock_extract.return_value = [
            Scenario({"filename": "google_drive.pdf", "page": 1, "text": "Google Drive PDF"})
        ]
        
        # Test from_pdf with Google Drive URL
        url = "https://drive.google.com/file/d/abc123/view"
        result = PdfTools.from_pdf(url)
        mock_downloader.fetch_from_drive.assert_called_once_with(url, "temp_pdf.pdf")
        mock_extract.assert_called_once_with("/tmp/google_drive.pdf")
        assert result[0]["text"] == "Google Drive PDF"
    
    def test_extract_text_from_pdf(self):
        # Mock fitz module
        mock_fitz = MagicMock()
        mock_document = MagicMock()
        mock_document.__len__.return_value = 2
        mock_page1 = MagicMock()
        mock_page1.get_text.return_value = "Page 1 content"
        mock_page2 = MagicMock()
        mock_page2.get_text.return_value = "Page 2 content"
        mock_document.load_page.side_effect = [mock_page1, mock_page2]
        mock_fitz.open.return_value = mock_document
        
        # Patch dependencies
        with patch.dict('sys.modules', {'fitz': mock_fitz}), \
             patch('os.path.exists', return_value=True), \
             patch('os.path.basename', return_value="test.pdf"), \
             patch('importlib.util.find_spec', return_value=MagicMock()):
            
            # Test extract_text_from_pdf
            scenarios = list(PdfTools.extract_text_from_pdf("test.pdf"))
            
            # Verify results
            assert len(scenarios) == 2
            assert scenarios[0]["filename"] == "test.pdf"
            assert scenarios[0]["page"] == 1
            assert scenarios[0]["text"] == "Page 1 content"
            assert scenarios[1]["page"] == 2
            assert scenarios[1]["text"] == "Page 2 content"
    
    def test_extract_text_nonexistent_file(self):
        # Mock fitz module to avoid import error
        mock_fitz = MagicMock()
        
        # Test with nonexistent file
        with patch.dict('sys.modules', {'fitz': mock_fitz}), \
             patch('os.path.exists', return_value=False), \
             patch('importlib.util.find_spec', return_value=MagicMock()):
            
            with pytest.raises(FileNotFoundError):
                list(PdfTools.extract_text_from_pdf("nonexistent.pdf"))
    
    @patch('subprocess.run')
    @patch('os.remove')
    def test_create_hello_world_pdf(self, mock_remove, mock_run):
        # Mock file operations
        mock_open_obj = MagicMock()
        with patch('builtins.open', MagicMock(return_value=mock_open_obj)) as mock_open:
            # Test create_hello_world_pdf
            PdfTools.create_hello_world_pdf("hello_world")
            
            # Verify file operations
            mock_open.assert_called_once_with("hello_world.tex", "w")
            mock_run.assert_called_once_with(["pdflatex", "hello_world.tex"], check=True)
            
            # Verify cleanup attempts
            assert mock_remove.call_count == 2  # .aux and .log files

if __name__ == "__main__":
    pytest.main()