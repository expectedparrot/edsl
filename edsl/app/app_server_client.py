"""Client module for deploying and listing apps from FastAPI server."""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .app import App


class AppServerClient:
    """Handles communication with the EDSL App FastAPI server."""

    @staticmethod
    def deploy(app: "App", server_url: str = "http://localhost:8000") -> str:
        """Deploy an app to a FastAPI server.

        Args:
            app: The App instance to deploy.
            server_url: URL of the FastAPI server (default: http://localhost:8000)

        Returns:
            The app_id assigned by the server.

        Raises:
            ImportError: If requests library is not installed.
            requests.HTTPError: If the server request fails.

        Example:
            >>> from edsl.app.app import App
            >>> app = App.example()
            >>> app_id = AppServerClient.deploy(app)  # doctest: +SKIP
        """
        try:
            import requests
        except ImportError:
            raise ImportError(
                "requests is required for deploy(). Install with: pip install requests"
            )

        app_data = app.to_dict()
        response = requests.post(f"{server_url.rstrip('/')}/apps", json=app_data)
        response.raise_for_status()
        result = response.json()
        return result["app_id"]

    @staticmethod
    def list_apps(server_url: str = "http://localhost:8000") -> list[dict]:
        """List all apps from a FastAPI server.

        Args:
            server_url: URL of the FastAPI server (default: http://localhost:8000)

        Returns:
            List of app metadata dictionaries.

        Raises:
            ImportError: If requests library is not installed.
            requests.HTTPError: If the server request fails.

        Example:
            >>> apps = AppServerClient.list_apps()  # doctest: +SKIP
        """
        try:
            import requests
        except ImportError:
            raise ImportError(
                "requests is required for list_apps(). Install with: pip install requests"
            )

        response = requests.get(f"{server_url.rstrip('/')}/apps")
        response.raise_for_status()
        return response.json()

    @staticmethod
    def get_app(app_id: str, server_url: str = "http://localhost:8000") -> "App":
        """Retrieve an app from a FastAPI server by ID.

        Args:
            app_id: The app ID to retrieve.
            server_url: URL of the FastAPI server (default: http://localhost:8000)

        Returns:
            The App instance.

        Raises:
            ImportError: If requests library is not installed.
            requests.HTTPError: If the server request fails.

        Example:
            >>> app = AppServerClient.get_app("some-app-id")  # doctest: +SKIP
        """
        try:
            import requests
        except ImportError:
            raise ImportError(
                "requests is required for get_app(). Install with: pip install requests"
            )

        response = requests.get(f"{server_url.rstrip('/')}/apps/{app_id}/data")
        response.raise_for_status()
        app_data = response.json()

        # Import here to avoid circular imports
        from .app import App
        return App.from_dict(app_data)

    @staticmethod
    def delete_app(app_id: str, server_url: str = "http://localhost:8000") -> dict:
        """Delete an app from a FastAPI server.

        Args:
            app_id: The app ID to delete.
            server_url: URL of the FastAPI server (default: http://localhost:8000)

        Returns:
            Response dictionary from the server.

        Raises:
            ImportError: If requests library is not installed.
            requests.HTTPError: If the server request fails.

        Example:
            >>> result = AppServerClient.delete_app("some-app-id")  # doctest: +SKIP
        """
        try:
            import requests
        except ImportError:
            raise ImportError(
                "requests is required for delete_app(). Install with: pip install requests"
            )

        response = requests.delete(f"{server_url.rstrip('/')}/apps/{app_id}")
        response.raise_for_status()
        return response.json()

    @staticmethod
    def execute_app(
        app_id: str,
        answers: dict,
        formatter_name: Optional[str] = None,
        server_url: str = "http://localhost:8000",
        api_payload: Optional[bool] = True,
        return_results: Optional[bool] = None,
    ) -> dict:
        """Execute an app remotely on the FastAPI server.

        Args:
            app_id: The app ID to execute.
            answers: Dictionary of answers keyed by question names.
            formatter_name: Optional output formatter name.
            server_url: URL of the FastAPI server (default: http://localhost:8000)

        Returns:
            Execution response dictionary with execution_id, status, result, error.

        Raises:
            ImportError: If requests library is not installed.
            requests.HTTPError: If the server request fails.

        Example:
            >>> result = AppServerClient.execute_app("app-id", {"text": "hello"})  # doctest: +SKIP
        """
        try:
            import requests
        except ImportError:
            raise ImportError(
                "requests is required for execute_app(). Install with: pip install requests"
            )

        request_data = {
            "answers": answers,
            "formatter_name": formatter_name,
            "api_payload": api_payload,
            "return_results": return_results,
        }
        response = requests.post(
            f"{server_url.rstrip('/')}/apps/{app_id}/execute",
            json=request_data
        )
        response.raise_for_status()
        return response.json()


if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
