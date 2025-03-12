import pytest
import csv
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from io import StringIO
from urllib.parse import urljoin

from edsl.scenarios import ScenarioList  # Adjust this import as necessary


class CSVRequestHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/test.csv":
            self.send_response(200)
            self.send_header("Content-type", "text/csv")
            self.end_headers()
            csv_content = "name,age,location\nAlice,30,New York\nBob,25,Los Angeles\n"
            self.wfile.write(csv_content.encode())
        else:
            self.send_error(404, "File not found")


@pytest.fixture(scope="module")
def http_server():
    server = HTTPServer(("localhost", 0), CSVRequestHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    yield f"http://localhost:{server.server_port}"
    server.shutdown()
    server.server_close()


def test_from_csv_url(http_server):
    url = urljoin(http_server, "/test.csv")
    scenario_list = ScenarioList.from_csv(url)

    assert len(scenario_list) == 2
    assert scenario_list[0]["name"] == "Alice"
    assert scenario_list[0]["age"] == "30"
    assert scenario_list[0]["location"] == "New York"
    assert scenario_list[1]["name"] == "Bob"
    assert scenario_list[1]["age"] == "25"
    assert scenario_list[1]["location"] == "Los Angeles"


def test_from_csv_file(tmp_path):
    csv_file = tmp_path / "test.csv"
    csv_content = "name,age,location\nCharlie,35,Chicago\nDiana,28,Boston\n"
    csv_file.write_text(csv_content)
    scenario_list = ScenarioList.from_csv(str(csv_file))

    assert len(scenario_list) == 2
    assert scenario_list[0]["name"] == "Charlie"
    assert scenario_list[0]["age"] == "35"
    assert scenario_list[0]["location"] == "Chicago"
    assert scenario_list[1]["name"] == "Diana"
    assert scenario_list[1]["age"] == "28"
    assert scenario_list[1]["location"] == "Boston"
