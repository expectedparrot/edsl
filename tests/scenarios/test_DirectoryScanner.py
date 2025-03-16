import pytest
import os
import tempfile
from edsl.scenarios.directory_scanner import DirectoryScanner

class TestDirectoryScanner:
    def setup_method(self):
        # Create a temporary directory structure for testing
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = self.temp_dir.name
        
        # Create test files
        self.create_test_files()
        
        # Initialize DirectoryScanner
        self.scanner = DirectoryScanner(self.dir_path)
    
    def teardown_method(self):
        # Clean up temporary directory
        self.temp_dir.cleanup()
    
    def create_test_files(self):
        # Create various test files with different extensions
        open(os.path.join(self.dir_path, "file1.txt"), "w").write("Text content")
        open(os.path.join(self.dir_path, "file2.txt"), "w").write("More text")
        open(os.path.join(self.dir_path, "document.pdf"), "w").write("PDF content")
        open(os.path.join(self.dir_path, "image.jpg"), "w").write("Image data")
        open(os.path.join(self.dir_path, "noextension"), "w").write("No extension file")
        
        # Create a subdirectory with more files
        os.mkdir(os.path.join(self.dir_path, "subdir"))
        open(os.path.join(self.dir_path, "subdir", "subfile1.txt"), "w").write("Subdir text")
        open(os.path.join(self.dir_path, "subdir", "subfile2.pdf"), "w").write("Subdir PDF")
        open(os.path.join(self.dir_path, "subdir", "example_suffix.txt.example"), "w").write("Example suffix")
    
    def test_scan_all_files(self):
        # Test scanning for all files in the top level directory
        files = self.scanner.scan(lambda p: p)
        assert len(files) == 5  # All files in top directory
        
        # Verify all top-level files are included
        assert os.path.join(self.dir_path, "file1.txt") in files
        assert os.path.join(self.dir_path, "file2.txt") in files
        assert os.path.join(self.dir_path, "document.pdf") in files
        assert os.path.join(self.dir_path, "image.jpg") in files
        assert os.path.join(self.dir_path, "noextension") in files
    
    def test_scan_recursive(self):
        # Test recursive scanning
        files = self.scanner.scan(lambda p: p, recursive=True)
        assert len(files) == 8  # All files including subdirectory
        
        # Verify subdirectory files are included
        assert os.path.join(self.dir_path, "subdir", "subfile1.txt") in files
        assert os.path.join(self.dir_path, "subdir", "subfile2.pdf") in files
        assert os.path.join(self.dir_path, "subdir", "example_suffix.txt.example") in files
    
    def test_scan_with_factory(self):
        # Test using a factory function
        def get_filename(path):
            return os.path.basename(path)
        
        filenames = self.scanner.scan(get_filename)
        assert len(filenames) == 5
        assert "file1.txt" in filenames
        assert "file2.txt" in filenames
        assert "document.pdf" in filenames
        assert "image.jpg" in filenames
        assert "noextension" in filenames
    
    def test_scan_suffix_allow_list(self):
        # Test filtering by allowed suffixes
        txt_files = self.scanner.scan(lambda p: p, suffix_allow_list=["txt"], include_no_extension=False)
        assert len(txt_files) == 2
        assert os.path.join(self.dir_path, "file1.txt") in txt_files
        assert os.path.join(self.dir_path, "file2.txt") in txt_files
        
        # Test with multiple allowed suffixes
        txt_pdf_files = self.scanner.scan(lambda p: p, suffix_allow_list=["txt", "pdf"], include_no_extension=False)
        assert len(txt_pdf_files) == 3
        assert os.path.join(self.dir_path, "document.pdf") in txt_pdf_files
    
    def test_scan_suffix_exclude_list(self):
        # Test filtering by excluded suffixes
        no_txt_files = self.scanner.scan(lambda p: p, suffix_exclude_list=["txt"])
        assert len(no_txt_files) == 3
        assert os.path.join(self.dir_path, "document.pdf") in no_txt_files
        assert os.path.join(self.dir_path, "image.jpg") in no_txt_files
        assert os.path.join(self.dir_path, "noextension") in no_txt_files
        
        # Test excluding multiple suffixes
        no_txt_pdf_files = self.scanner.scan(lambda p: p, suffix_exclude_list=["txt", "pdf"])
        assert len(no_txt_pdf_files) == 2
        assert os.path.join(self.dir_path, "image.jpg") in no_txt_pdf_files
        assert os.path.join(self.dir_path, "noextension") in no_txt_pdf_files
    
    def test_scan_example_suffix(self):
        # Test filtering by example suffix, should only work in subdirectory with recursive=True
        example_files = self.scanner.scan(
            lambda p: p, recursive=True, example_suffix=".txt.example", include_no_extension=False
        )
        assert len(example_files) == 1
        assert os.path.join(self.dir_path, "subdir", "example_suffix.txt.example") in example_files
    
    def test_scan_include_no_extension(self):
        # Test including/excluding files with no extension
        with_no_ext = self.scanner.scan(lambda p: p, include_no_extension=True)
        assert os.path.join(self.dir_path, "noextension") in with_no_ext
        
        without_no_ext = self.scanner.scan(lambda p: p, include_no_extension=False)
        assert os.path.join(self.dir_path, "noextension") not in without_no_ext
        assert len(without_no_ext) == 4  # All top-level files except the one without extension
    
    def test_iter_scan(self):
        # Test lazy iteration
        file_count = 0
        for _ in self.scanner.iter_scan(lambda p: p):
            file_count += 1
        assert file_count == 5  # Should find all top-level files
        
        # Test lazy iteration with filtering
        txt_files = []
        for file_path in self.scanner.iter_scan(lambda p: p, suffix_allow_list=["txt"], include_no_extension=False):
            txt_files.append(file_path)
        assert len(txt_files) == 2
        assert os.path.join(self.dir_path, "file1.txt") in txt_files
        assert os.path.join(self.dir_path, "file2.txt") in txt_files
    
    def test_combined_filters(self):
        # Test combining different filters
        files = self.scanner.scan(
            lambda p: p,
            recursive=True,
            suffix_allow_list=["txt", "pdf"],
            suffix_exclude_list=["pdf"],
            include_no_extension=False
        )
        # Should only include .txt files, excluding .pdf due to exclude_list
        assert len(files) == 3
        assert os.path.join(self.dir_path, "file1.txt") in files
        assert os.path.join(self.dir_path, "file2.txt") in files
        assert os.path.join(self.dir_path, "subdir", "subfile1.txt") in files
        
        # Exclude list takes precedence over allow list
        assert os.path.join(self.dir_path, "document.pdf") not in files
        assert os.path.join(self.dir_path, "subdir", "subfile2.pdf") not in files

if __name__ == "__main__":
    pytest.main()