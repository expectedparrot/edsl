"""Client module for deploying and listing apps from FastAPI server."""

from __future__ import annotations
import requests
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .app import App


class AppServerClient:
    """Handles communication with the EDSL App FastAPI server."""

    @staticmethod
    def deploy(
        app: "App",
        owner: str,
        server_url: str = "http://localhost:8000",
        source_available: bool = False,
        force: bool = False,
    ) -> str:
        """Deploy an app to a FastAPI server.

        Args:
            app: The App instance to deploy.
            server_url: URL of the FastAPI server (default: http://localhost:8000)
            owner: Required owner string used for global uniqueness.
            source_available: If True, the source code is available to future users.
            force: If True, overwrite any existing app with the same owner/alias.

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

        app_data = app.to_dict()
        app_data = dict(app_data)
        app_data["owner"] = owner
        app_data["source_available"] = source_available
        app_data["force"] = force
        alias = app_data["application_name"]["alias"]

        from .exceptions import DuplicateAppException

        response = requests.post(f"{server_url.rstrip('/')}/apps", json=app_data)
        if response.status_code == 409:
            detail = response.json().get("detail")
            raise DuplicateAppException(
                detail or f"Duplicate app: owner/alias '{owner}/{alias}' already exists"
            )

        response.raise_for_status()
        result = response.json()
        return result

    @staticmethod
    def list_apps(
        server_url: str = "http://localhost:8000", search: str | None = None, owner: str | None = None
    ) -> list[dict]:
        """List all apps from a FastAPI server.

        Args:
            server_url: URL of the FastAPI server (default: http://localhost:8000)
            search: Optional search string to filter apps.
            owner: Optional owner string to filter apps by owner.

        Returns:
            List of app metadata dictionaries.

        Raises:
            ImportError: If requests library is not installed.
            requests.HTTPError: If the server request fails.

        Example:
            >>> apps = AppServerClient.list_apps()  # doctest: +SKIP
        """
        params = {}
        if search:
            params["search"] = search
        if owner:
            params["owner"] = owner
        response = requests.get(f"{server_url.rstrip('/')}/apps", params=params if params else None)
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
            requests.HTTPError: If the server request fails.

        Example:
            >>> app = AppServerClient.get_app("some-app-id")  # doctest: +SKIP
        """
        response = requests.get(f"{server_url.rstrip('/')}/apps/{app_id}/data")
        response.raise_for_status()
        app_data = response.json()

        # Import here to avoid circular imports
        from .app import App

        return App.from_dict(app_data)

    @staticmethod
    def delete_app(
        app_id: str, owner: str, server_url: str = "http://localhost:8000"
    ) -> dict:
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
        response = requests.delete(
            f"{server_url.rstrip('/')}/apps/{app_id}", params={"owner": owner}
        )
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
        request_data = {
            "answers": answers,
            "formatter_name": formatter_name,
            "api_payload": api_payload,
            "return_results": return_results,
        }
        response = requests.post(
            f"{server_url.rstrip('/')}/apps/{app_id}/execute", json=request_data
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def instantiate_remote_app_client(
        app_id: str, server_url: str = "http://localhost:8000"
    ) -> dict:
        """Fetch app dict for client-side instantiation (without jobs_object).

        Args:
            app_id: The app ID to retrieve.
            server_url: URL of the FastAPI server (default: http://localhost:8000)

        Returns:
            Dictionary suitable for constructing an App client locally.

        Raises:
            ImportError: If requests library is not installed.
            requests.HTTPError: If the server request fails.
        """
        response = requests.get(
            f"{server_url.rstrip('/')}/instantiate_remote_app_client/{app_id}"
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def resolve_app_id(
        qualified_name: str, server_url: str = "http://localhost:8000"
    ) -> str:
        """Resolve a qualified name 'owner/alias' to an app_id via the server.

        Args:
            qualified_name: The string in the format 'owner/alias'.
            server_url: URL of the FastAPI server.

        Returns:
            The resolved app_id string.
        """

        params = {"qualified_name": qualified_name}
        response = requests.get(f"{server_url.rstrip('/')}/apps/resolve", params=params)
        response.raise_for_status()
        data = response.json()
        return data["app_id"]


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
