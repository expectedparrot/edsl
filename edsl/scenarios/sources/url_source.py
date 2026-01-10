"""URL-based source for ScenarioList creation."""

from __future__ import annotations
import warnings
from typing import TYPE_CHECKING

from .base import Source
from ..scenario import Scenario

if TYPE_CHECKING:
    pass


class URLSource(Source):
    """Create ScenarioList from a list of URLs by fetching their content."""

    source_type = "urls"

    def __init__(self, urls: list[str], field_name: str):
        self.urls = urls
        self.field_name = field_name

    @classmethod
    def example(cls) -> "URLSource":
        """Return an example URLSource instance with a local test server."""
        import threading
        import time
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import socket

        # Find an available port
        sock = socket.socket()
        sock.bind(("", 0))
        port = sock.getsockname()[1]
        sock.close()

        class TestHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"This is sample web content for testing")

            def log_message(self, format, *args):
                # Suppress log messages
                pass

        # Start the server in a daemon thread
        server = HTTPServer(("localhost", port), TestHandler)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()

        # Give the server a moment to start
        time.sleep(0.1)

        # Create the URLSource instance
        instance = cls(urls=[f"http://localhost:{port}"], field_name="text")

        # Store server reference for cleanup if needed
        instance._test_server = server

        return instance

    def to_scenario_list(self):
        """Create a ScenarioList from a list of URLs."""
        from ..scenario_list import ScenarioList
        import requests

        result = ScenarioList()
        for url in self.urls:
            try:
                response = requests.get(url)
                response.raise_for_status()
                scenario = Scenario({self.field_name: response.text})
                result = result.append(scenario)  # Capture returned instance
            except requests.RequestException as e:
                warnings.warn(f"Failed to fetch URL {url}: {str(e)}")
                continue

        return result
