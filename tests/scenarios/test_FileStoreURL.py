import unittest
import http.server
import socketserver
import threading
import os
import tempfile
from edsl.scenarios.FileStore import FileStore

class TestFileStore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create a temporary directory to serve files from
        cls.temp_dir = tempfile.mkdtemp()
        
        # Create a test file
        cls.test_content = "Hello, this is a test file!"
        cls.test_filename = "test.txt"
        cls.test_filepath = os.path.join(cls.temp_dir, cls.test_filename)
        
        with open(cls.test_filepath, 'w') as f:
            f.write(cls.test_content)
        
        # Set up a simple HTTP server
        cls.PORT = 8000
        Handler = http.server.SimpleHTTPRequestHandler
        cls.httpd = socketserver.TCPServer(("", cls.PORT), Handler)
        
        # Change directory to serve files from temp directory
        os.chdir(cls.temp_dir)
        
        # Start the server in a separate thread
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever)
        cls.server_thread.daemon = True
        cls.server_thread.start()

    def test_url_download(self):
        # Create FileStore with URL
        url = f"http://localhost:{self.PORT}/{self.test_filename}"
        fs = FileStore(url)
        
        # Verify the content
        self.assertEqual(fs.text, self.test_content)
        
        # Verify the file exists
        self.assertTrue(os.path.exists(fs.path))

    @classmethod
    def tearDownClass(cls):
        # Shutdown the server
        cls.httpd.shutdown()
        cls.httpd.server_close()
        
        # Clean up temporary directory
        import shutil
        shutil.rmtree(cls.temp_dir)

if __name__ == '__main__':
    unittest.main()