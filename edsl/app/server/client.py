"""Client helper for interacting with EDSL App FastAPI server."""

import sys
from pathlib import Path

# Add parent directories to path to import edsl
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import requests
from typing import Optional, Dict, Any, List
import logging
from edsl.app.app import App

logger = logging.getLogger(__name__)

class EDSLAppClient:
    """Client for interacting with EDSL App FastAPI server."""

    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url.rstrip('/')
        self.session = requests.Session()

    def health_check(self) -> dict:
        """Check server health."""
        response = self.session.get(f"{self.server_url}/health")
        response.raise_for_status()
        return response.json()

    def push_app(self, app: App) -> str:
        """Push an app to the server and return app_id."""
        app_data = app.to_dict()
        response = self.session.post(f"{self.server_url}/apps", json=app_data)
        response.raise_for_status()
        result = response.json()
        logger.info(f"Pushed app: {result['message']}")
        return result["app_id"]

    def list_apps(self) -> List[dict]:
        """List all apps on the server."""
        response = self.session.get(f"{self.server_url}/apps")
        response.raise_for_status()
        return response.json()

    def get_app_metadata(self, app_id: str) -> dict:
        """Get app metadata."""
        response = self.session.get(f"{self.server_url}/apps/{app_id}")
        response.raise_for_status()
        return response.json()

    def get_app_parameters(self, app_id: str) -> dict:
        """Get app parameters."""
        response = self.session.get(f"{self.server_url}/apps/{app_id}/parameters")
        response.raise_for_status()
        return response.json()

    def execute_app(self, app_id: str, answers: Dict[str, Any], formatter_name: Optional[str] = None) -> dict:
        """Execute an app remotely."""
        request_data = {
            "answers": answers,
            "formatter_name": formatter_name
        }
        response = self.session.post(f"{self.server_url}/apps/{app_id}/execute", json=request_data)
        response.raise_for_status()
        return response.json()

    def get_execution_status(self, execution_id: str) -> dict:
        """Get execution status and results."""
        response = self.session.get(f"{self.server_url}/executions/{execution_id}")
        response.raise_for_status()
        return response.json()

    def delete_app(self, app_id: str) -> dict:
        """Delete an app from the server."""
        response = self.session.delete(f"{self.server_url}/apps/{app_id}")
        response.raise_for_status()
        return response.json()

    def get_stats(self) -> dict:
        """Get server statistics."""
        response = self.session.get(f"{self.server_url}/stats")
        response.raise_for_status()
        return response.json()

# Extend AppBase with server methods
def push_to_server(self, server_url: str = "http://localhost:8000") -> str:
    """Push this app to a FastAPI server."""
    client = EDSLAppClient(server_url)
    return client.push_app(self)

def pull_from_server(cls, server_url: str, app_id: str) -> 'App':
    """Pull an app from a FastAPI server."""
    client = EDSLAppClient(server_url)
    response = client.session.get(f"{client.server_url}/apps/{app_id}/data")
    response.raise_for_status()
    app_data = response.json()
    return App.from_dict(app_data)

# Monkey patch the methods onto App
App.push_to_server = push_to_server
App.pull_from_server = classmethod(pull_from_server)