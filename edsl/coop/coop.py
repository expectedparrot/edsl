import aiohttp
import base64
import json
import os
import requests
import time

from typing import (
    Any,
    Dict,
    Optional,
    Union,
    Literal,
    List,
    Tuple,
    TypedDict,
    TYPE_CHECKING,
)
from uuid import UUID

from .. import __version__

from ..config import CONFIG
from ..caching import CacheEntry
from ..logger import get_logger

if TYPE_CHECKING:
    from ..jobs import Jobs
    from ..scenarios import Scenario, ScenarioList
    from ..surveys import Survey
    from ..results import Results

from .exceptions import (
    CoopInvalidURLError,
    CoopNoUUIDError,
    CoopServerResponseError,
    CoopValueError,
)
from .utils import (
    EDSLObject,
    ObjectRegistry,
    ObjectType,
    RemoteJobStatus,
    VisibilityType,
)

from .coop_functions import CoopFunctionsMixin
from .coop_regular_objects import CoopRegularObjects
from .coop_jobs_objects import CoopJobsObjects
from .coop_prolific_filters import CoopProlificFilters
from .ep_key_handling import ExpectedParrotKeyHandler

# from ..inference_services.data_structures import ServiceToModelsMapping


class JobRunExpense(TypedDict):
    service: str
    model: str
    token_type: Literal["input", "output"]
    price_per_million_tokens: float
    tokens_count: int
    cost_credits: float
    cost_usd: float


class JobRunExceptionCounter(TypedDict):
    exception_type: str
    inference_service: str
    model: str
    question_name: str
    exception_count: int


class JobRunInterviewDetails(TypedDict):
    total_interviews: int
    completed_interviews: int
    interviews_with_exceptions: int
    exception_summary: List[JobRunExceptionCounter]


class LatestJobRunDetails(TypedDict):
    # For running, completed, and partially failed jobs
    interview_details: Optional[JobRunInterviewDetails] = None

    # For failed jobs only
    failure_reason: Optional[Literal["error", "insufficient funds"]] = None
    failure_description: Optional[str] = None

    # For partially failed jobs only
    error_report_uuid: Optional[UUID] = None

    # For completed and partially failed jobs
    cost_credits: Optional[float] = None
    cost_usd: Optional[float] = None
    expenses: Optional[list[JobRunExpense]] = None


class RemoteInferenceResponse(TypedDict):
    job_uuid: str
    results_uuid: str
    job_json_string: Optional[str]
    status: RemoteJobStatus
    latest_job_run_details: LatestJobRunDetails
    description: Optional[str]
    version: str
    visibility: VisibilityType
    results_url: str


class RemoteInferenceCreationInfo(TypedDict):
    uuid: str
    description: str
    status: str
    iterations: int
    visibility: str
    version: str


class Coop(CoopFunctionsMixin):
    """
    Client for the Expected Parrot API that provides cloud-based functionality for EDSL.

    The Coop class is the main interface for interacting with Expected Parrot's cloud services.
    It enables:

    1. Storing and retrieving EDSL objects (surveys, agents, models, results, etc.)
    2. Running inference jobs remotely for better performance and scalability
    3. Retrieving and caching interview results
    4. Managing API keys and authentication
    5. Accessing model availability and pricing information

    The client handles authentication, serialization/deserialization of EDSL objects,
    and communication with the Expected Parrot API endpoints. It also provides
    methods for tracking job status and managing results.

    When initialized without parameters, Coop will attempt to use an API key from:
    1. The EXPECTED_PARROT_API_KEY environment variable
    2. A stored key in the user's config directory
    3. Interactive login if needed

    Attributes:
        api_key (str): The API key used for authentication
        url (str): The base URL for the Expected Parrot API
        api_url (str): The URL for API endpoints (derived from base URL)
    """

    _logger = get_logger(__name__)

    # Class-level error cache shared across all instances
    _class_error_cache = {}  # {error_signature: last_reported_time}

    # Class-level API key - if set, this will be used as default for all instances
    _class_api_key: Optional[str] = None

    def __init__(
        self, api_key: Optional[str] = None, url: Optional[str] = None
    ) -> None:
        """
        Initialize the Expected Parrot API client.

        This constructor sets up the connection to Expected Parrot's cloud services.
        If not provided explicitly, it will attempt to obtain an API key from:
        1. The api_key parameter
        2. The class-level _class_api_key (if set via Coop._class_api_key = "key")
        3. Environment variables or stored location in user's config directory

        Parameters:
            api_key (str, optional): API key for authentication with Expected Parrot.
                If not provided, will attempt to obtain from class-level setting,
                environment, or stored location.
            url (str, optional): Base URL for the Expected Parrot service.
                If not provided, uses the default from configuration.

        Notes:
            - The API key is stored in the EXPECTED_PARROT_API_KEY environment variable
              or in a platform-specific config directory
            - The URL is determined based on whether it's a production, staging,
              or development environment
            - The api_url for actual API endpoints is derived from the base URL

        Example:
            >>> coop = Coop()  # Uses API key from environment or stored location
            >>> coop = Coop(api_key="your-api-key")  # Explicitly provide API key
            >>> Coop._class_api_key = "my-key"  # Set class-level default
            >>> coop = Coop()  # Will use "my-key"
        """
        self.ep_key_handler = ExpectedParrotKeyHandler()
        # Priority: instance parameter > class-level setting > environment/stored
        self.api_key = (
            api_key or self._class_api_key or self.ep_key_handler.get_ep_api_key()
        )

        self.url = url or CONFIG.EXPECTED_PARROT_URL
        if self.url.endswith("/"):
            self.url = self.url[:-1]
        if "chickapi.expectedparrot" in self.url:
            self.api_url = "https://chickapi.expectedparrot.com"
        elif "chick.expectedparrot" in self.url:
            # Frontend URL for staging environment - convert to API URL
            self.api_url = "https://chickapi.expectedparrot.com"
        elif "expectedparrot" in self.url:
            self.api_url = "https://api.expectedparrot.com"
        elif "localhost:1234" in self.url:
            self.api_url = "http://localhost:8000"
        else:
            self.api_url = self.url
        self._edsl_version = __version__

    def get_progress_bar_url(self):
        return f"{CONFIG.EXPECTED_PARROT_URL}"

    ################
    # BASIC METHODS
    ################
    @property
    def headers(self) -> dict:
        """
        Return the headers for the request.
        """
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        else:
            headers["Authorization"] = "Bearer None"
        return headers

    def _send_server_request(
        self,
        uri: str,
        method: str,
        payload: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
        timeout: Optional[float] = 10,
    ) -> requests.Response:
        """
        Send a request to the server and return the response.
        """
        url = f"{self.api_url}/{uri}"
        method = method.upper()
        if payload is None:
            timeout = 40
        elif (
            (method.upper() == "POST" or method.upper() == "PATCH")
            and "json_string" in payload
            and payload.get("json_string") is not None
        ):
            timeout = max(
                60, 2 * (len(payload.get("json_string", "")) // (1024 * 1024))
            )

        # Log the outgoing request
        self._logger.info(f"Sending {method} request to {url}")
        if params:
            self._logger.info(f"Request params: {params}")
        if payload:
            # Log payload but truncate large json_strings for readability
            log_payload = payload.copy() if payload else {}
            if "json_string" in log_payload and log_payload["json_string"]:
                json_str = log_payload["json_string"]
                if len(json_str) > 200:
                    log_payload["json_string"] = (
                        f"{json_str[:200]}... (truncated, total length: {len(json_str)})"
                    )
            self._logger.info(f"Request payload: {log_payload}")

        try:
            if method in ["GET", "DELETE"]:
                response = requests.request(
                    method, url, params=params, headers=self.headers, timeout=timeout
                )
            elif method in ["POST", "PATCH"]:
                response = requests.request(
                    method,
                    url,
                    params=params,
                    json=payload,
                    headers=self.headers,
                    timeout=timeout,
                )
            else:
                from .exceptions import CoopInvalidMethodError

                error_msg = f"Invalid {method=}."
                self._logger.error(f"Invalid HTTP method: {error_msg}")
                raise CoopInvalidMethodError(error_msg)

            # Log successful response
            self._logger.info(
                f"Received response: {response.status_code} from {method} {url}"
            )

        except requests.ConnectionError as e:
            error_msg = f"Could not connect to the server at {url}."
            self._logger.error(f"Connection error: {error_msg} - {str(e)}")
            raise requests.ConnectionError(error_msg)
        except requests.Timeout as e:
            error_msg = f"Request to {url} timed out after {timeout} seconds."
            self._logger.error(f"Timeout error: {error_msg} - {str(e)}")
            raise
        except requests.RequestException as e:
            error_msg = f"Request to {url} failed."
            self._logger.error(f"Request error: {error_msg} - {str(e)}")
            raise
        except Exception as e:
            error_msg = f"Unexpected error during request to {url}."
            self._logger.error(f"Unexpected error: {error_msg} - {str(e)}")
            raise

        return response

    def _get_latest_stable_version(self, version: str) -> str:
        """
        Extract the latest stable PyPI version from a version string.

        Examples:
        - Decrement the patch number of a dev version: "0.1.38.dev1" -> "0.1.37"
        - Return a stable version as is: "0.1.37" -> "0.1.37"
        """
        if "dev" not in version:
            return version
        else:
            # For 0.1.38.dev1, split into ["0", "1", "38", "dev1"]
            major, minor, patch = version.split(".")[:3]

            current_patch = int(patch)
            latest_patch = current_patch - 1
            return f"{major}.{minor}.{latest_patch}"

    def _user_version_is_outdated(
        self, user_version_str: str, server_version_str: str
    ) -> bool:
        """
        Check if the user's EDSL version is outdated compared to the server's.
        """
        server_stable_version_str = self._get_latest_stable_version(server_version_str)
        user_stable_version_str = self._get_latest_stable_version(user_version_str)

        # Turn the version strings into tuples of ints for comparison
        user_stable_version = tuple(map(int, user_stable_version_str.split(".")))
        server_stable_version = tuple(map(int, server_stable_version_str.split(".")))

        return user_stable_version < server_stable_version

    def check_for_updates(self, silent: bool = False) -> Optional[dict]:
        """
        Check if there's a newer version of EDSL available.

        Args:
            silent: If True, don't print any messages to console

        Returns:
            dict with version info if update is available, None otherwise
        """
        try:
            # Use the new /version/updates endpoint
            response = self._send_server_request(
                uri="version/updates", method="GET", timeout=5
            )

            data = response.json()

            # Extract version information from the response
            current_version = data.get("current")  # Latest version in use
            guid_message = data.get("guid_message", "")  # Message about updates
            force_update = (
                "force update" in guid_message.lower() if guid_message else False
            )
            # Check if update is needed
            if current_version and self._user_version_is_outdated(
                user_version_str=self._edsl_version,
                server_version_str=current_version,
            ):
                update_data = {
                    "current_version": self._edsl_version,
                    "latest_version": current_version,
                    "guid_message": guid_message,
                    "force_update": force_update,
                    "update_command": "pip install --upgrade edsl",
                }

                if not silent:
                    print("\n" + "=" * 60)
                    print("📦 EDSL Update Available!")
                    print(f"Your version: {self._edsl_version}")
                    print(f"Latest version: {current_version}")

                    # Display the guid message if present
                    if guid_message:
                        print(f"\n{guid_message}")

                    # Prompt user for update
                    prompt_message = "\nDo you want to update now? [Y/n] "
                    if force_update:
                        prompt_message = "\n⚠️  FORCE UPDATE REQUIRED - Do you want to update now? [Y/n] "

                    print(prompt_message, end="")

                    try:
                        user_input = input().strip().lower()
                        if user_input in ["", "y", "yes"]:
                            # Actually run the update
                            print("\nUpdating EDSL...")
                            import subprocess
                            import sys

                            try:
                                # Run pip install --upgrade edsl
                                result = subprocess.run(
                                    [
                                        sys.executable,
                                        "-m",
                                        "pip",
                                        "install",
                                        "--upgrade",
                                        "edsl",
                                    ],
                                    capture_output=True,
                                    text=True,
                                )

                                if result.returncode == 0:
                                    print(
                                        "✅ Update successful! Please restart your application."
                                    )
                                else:
                                    print(f"❌ Update failed: {result.stderr}")
                                    print(
                                        "You can try updating manually with: pip install --upgrade edsl"
                                    )
                            except Exception as e:
                                print(f"❌ Update failed: {str(e)}")
                                print(
                                    "You can try updating manually with: pip install --upgrade edsl"
                                )
                        else:
                            print(
                                "\nUpdate skipped. You can update later with: pip install --upgrade edsl"
                            )

                        print("=" * 60 + "\n")

                    except (EOFError, KeyboardInterrupt):
                        print(
                            "\nUpdate skipped. You can update later with: pip install --upgrade edsl"
                        )
                        print("=" * 60 + "\n")

                return update_data

        except Exception:
            # Silently fail if we can't check for updates
            pass

        return None

    def _resolve_server_response(
        self, response: requests.Response, check_api_key: bool = True
    ) -> None:
        """
        Check the response from the server and raise errors as appropriate.
        """
        # Get EDSL version from header
        server_edsl_version = response.headers.get("X-EDSL-Version")

        if server_edsl_version:
            if self._user_version_is_outdated(
                user_version_str=self._edsl_version,
                server_version_str=server_edsl_version,
            ):
                # Get additional info from server if available
                update_info = response.headers.get("X-EDSL-Update-Info", "")
                self._logger.info(
                    f"EDSL version update available: {self._edsl_version} -> {server_edsl_version}"
                )

                print("\n" + "=" * 60)
                print("📦 EDSL Update Available!")
                print(f"Your version: {self._edsl_version}")
                print(f"Latest version: {server_edsl_version}")
                if update_info:
                    print(f"Update info: {update_info}")
                print(
                    "\nYour version is out of date - can we update to latest version? [Y/n]"
                )

                try:
                    user_input = input().strip().lower()
                    if user_input in ["", "y", "yes"]:
                        print("To update, run: pip install --upgrade edsl")
                        print("=" * 60 + "\n")
                except (EOFError, KeyboardInterrupt):
                    # Handle non-interactive environments
                    print("To update, run: pip install --upgrade edsl")
                    print("=" * 60 + "\n")
        if response.status_code >= 400:
            error_msg = f"Server error: {response.status_code}"
            self._logger.error(f"{error_msg}: {response.text}")

            try:
                message = str(response.json().get("detail"))
            except json.JSONDecodeError:
                decode_error = (
                    f"Server returned status code {response.status_code}. "
                    f"JSON response could not be decoded. "
                    f"The server response was: {response.text}"
                )
                self._logger.error(
                    f"Failed to decode server error response: {decode_error}"
                )
                raise CoopServerResponseError(decode_error)
            # print(response.text)
            if "The API key you provided is invalid" in message and check_api_key:
                import secrets
                from ..utilities.utilities import write_api_key_to_env

                self._logger.info("Invalid API key detected, starting login flow")
                edsl_auth_token = secrets.token_urlsafe(16)

                print("Your Expected Parrot API key is invalid.")
                self._display_login_url(
                    edsl_auth_token=edsl_auth_token,
                    link_description="\n🔗 Use the link below to log in to your account and automatically update your API key.",
                )
                api_key = self._poll_for_api_key(edsl_auth_token)

                if api_key is None:
                    self._logger.error("Timed out waiting for login")
                    print("\nTimed out waiting for login. Please try again.")
                    return

                print("\n✨ API key retrieved.")
                self._logger.info("API key successfully retrieved via login")

                if self.ep_key_handler.ask_to_store(api_key):
                    pass
                else:
                    path_to_env = write_api_key_to_env(api_key)
                    print(
                        "\n✨ API key retrieved and written to .env file at the following path:"
                    )
                    print(f"    {path_to_env}")
                    print("Rerun your code to try again with a valid API key.")
                return

            elif "Authorization" in message:
                self._logger.error(f"Authorization error: {message}")
                print(message)
                message = "Please provide an Expected Parrot API key."

            self._logger.error(f"Server response error: {message}")
            raise CoopServerResponseError(message)

    def _resolve_gcs_response(self, response: requests.Response) -> None:
        """
        Check the response from uploading or downloading a file from Google Cloud Storage.
        Raise errors as appropriate.
        """
        if response.status_code >= 400:
            error_msg = f"GCS operation failed with status {response.status_code}"
            self._logger.error(f"{error_msg}: {response.text}")

            try:
                import xml.etree.ElementTree as ET

                # Extract elements from XML string
                root = ET.fromstring(response.text)

                code = root.find("Code").text
                message = root.find("Message").text
                details = root.find("Details").text

                detailed_error = f"An error occurred: {code} - {message} - {details}"
                self._logger.error(f"GCS error details: {detailed_error}")
            except Exception as parse_error:
                from .exceptions import CoopServerResponseError

                decode_error = (
                    f"Server returned status code {response.status_code}. "
                    f"XML response could not be decoded. "
                    f"The server response was: {response.text}"
                )
                self._logger.error(
                    f"Failed to parse GCS error response: {str(parse_error)}"
                )
                raise CoopServerResponseError(decode_error)

            from .exceptions import CoopServerResponseError

            raise CoopServerResponseError(detailed_error)
        else:
            self._logger.info(f"GCS operation successful: {response.status_code}")

    def _poll_for_api_key(
        self, edsl_auth_token: str, timeout: int = 120
    ) -> Union[str, None]:
        """
        Allows the user to retrieve their Expected Parrot API key by logging in with an EDSL auth token.

        :param edsl_auth_token: The EDSL auth token to use for login
        :param timeout: Maximum time to wait for login, in seconds (default: 120)
        """
        from datetime import datetime

        start_poll_time = time.time()
        waiting_for_login = True
        while waiting_for_login:
            elapsed_time = time.time() - start_poll_time
            if elapsed_time > timeout:
                # Timed out waiting for the user to log in
                print("\r" + " " * 80 + "\r", end="")
                return None

            api_key = self._get_api_key(edsl_auth_token)
            if api_key is not None:
                print("\r" + " " * 80 + "\r", end="")
                return api_key
            else:
                duration = 5
                time_checked = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
                frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
                start_time = time.time()
                i = 0
                while time.time() - start_time < duration:
                    print(
                        f"\r{frames[i % len(frames)]} Waiting for login. Last checked: {time_checked}",
                        end="",
                        flush=True,
                    )
                    time.sleep(0.1)
                    i += 1

    def _json_handle_none(self, value: Any) -> Any:
        """
        Handle None values and problematic float values during JSON serialization.
        - Return "null" if the value is None
        - Handle out-of-range float values with detailed error messages
        """
        import math

        if value is None:
            return "null"

        # Handle problematic float values
        if isinstance(value, float):
            if math.isinf(value):
                raise ValueError(
                    f"Cannot serialize infinite float value: {value}. "
                    f"Location: {self._get_value_location(value)}"
                )
            elif math.isnan(value):
                raise ValueError(
                    f"Cannot serialize NaN float value: {value}. "
                    f"Location: {self._get_value_location(value)}"
                )
            elif abs(value) > 1.7976931348623157e308:  # sys.float_info.max
                raise ValueError(
                    f"Cannot serialize out-of-range float value: {value}. "
                    f"Location: {self._get_value_location(value)}"
                )

        # For other types, let the default JSON encoder handle them
        raise TypeError(f"Object of type {type(value)} is not JSON serializable")

    def _find_problematic_floats(
        self, obj: Any, path: str = ""
    ) -> List[Tuple[str, Any]]:
        """
        Recursively find all problematic float values in a nested data structure.

        Args:
            obj: The object to search
            path: Current path in the object hierarchy

        Returns:
            List of tuples containing (path, problematic_value)
        """
        import math

        problems = []

        if isinstance(obj, float):
            if math.isinf(obj) or math.isnan(obj):
                problems.append((path, obj))
        elif isinstance(obj, dict):
            for key, value in obj.items():
                new_path = f"{path}.{key}" if path else key
                problems.extend(self._find_problematic_floats(value, new_path))
        elif isinstance(obj, (list, tuple)):
            for i, value in enumerate(obj):
                new_path = f"{path}[{i}]" if path else f"[{i}]"
                problems.extend(self._find_problematic_floats(value, new_path))
        elif hasattr(obj, "__dict__"):
            for key, value in obj.__dict__.items():
                new_path = f"{path}.{key}" if path else key
                problems.extend(self._find_problematic_floats(value, new_path))

        return problems

    @staticmethod
    def _is_url(url_or_uuid: Union[str, UUID]) -> bool:
        return "http://" in str(url_or_uuid) or "https://" in str(url_or_uuid)

    def _resolve_uuid_or_alias(
        self, url_or_uuid: Union[str, UUID]
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Resolve the uuid or alias information from a uuid or a url.
        Returns a tuple of (uuid, owner_username, alias)
        - For content/uuid URLs: returns (uuid, None, None)
        - For content/username/alias URLs: returns (None, username, alias)
        """
        if not url_or_uuid:
            raise CoopNoUUIDError("No uuid or url provided for the object.")

        if self._is_url(url_or_uuid):
            url = str(url_or_uuid)

            parts = (
                url.replace("http://", "")
                .replace("https://", "")
                .rstrip("/")
                .split("/")
            )

            # Remove domain
            parts = parts[1:]

            if len(parts) < 2 or parts[0] != "content":
                raise CoopInvalidURLError(
                    f"Invalid URL format. The URL must end with /content/<uuid> or /content/<username>/<alias>: {url}"
                )

            if len(parts) == 2:
                obj_uuid = parts[1]
                return obj_uuid, None, None
            elif len(parts) == 3:
                username, alias = parts[1], parts[2]
                return None, username, alias
            else:
                raise CoopInvalidURLError(
                    f"Invalid URL format. The URL must end with /content/<uuid> or /content/<username>/<alias>: {url}"
                )

        uuid = str(url_or_uuid)
        return uuid, None, None

    @property
    def edsl_settings(self) -> dict:
        """
        Retrieve and return the EDSL settings stored on Coop.
        If no response is received within 5 seconds, return an empty dict.
        """
        from requests.exceptions import Timeout

        try:
            response = self._send_server_request(
                uri="api/v0/edsl-settings", method="GET", timeout=20
            )
            self._resolve_server_response(response, check_api_key=False)
            return response.json()
        except Timeout:
            return {}

    def _get_widget_javascript(self, widget_name: str) -> str:
        """
        Fetches the javascript for a widget from the server using cached singleton.

        This method uses the CoopVisualization singleton to cache ESM and CSS content,
        ensuring they are only fetched once per session for improved performance.
        """
        from .coop_widgets import get_widget_javascript

        esm, css = get_widget_javascript(widget_name)
        return esm, css

    ################
    # Widgets
    ################
    def create_widget(
        self,
        short_name: str,
        display_name: str,
        esm_code: str,
        css_code: Optional[str] = None,
        description: Optional[str] = None,
    ) -> dict:
        """
        Create a new widget.

        Parameters:
            short_name (str): The short name identifier for the widget.
            Must start with a lowercase letter and contain only lowercase letters, digits, and underscores
            display_name (str): The display name of the widget
            description (str): A human-readable description of the widget
            esm_code (str): The ESM JavaScript code for the widget
            css_code (str): The CSS code for the widget

        Returns:
            dict: Information about the created widget including:
                - short_name: The widget's short name
                - display_name: The widget's display name
                - description: The widget's description

        Raises:
            CoopServerResponseError: If there's an error communicating with the server
        """
        from ..widgets.base_widget import EDSLBaseWidget

        short_name_is_valid, error_message = EDSLBaseWidget.is_widget_short_name_valid(
            short_name
        )
        if not short_name_is_valid:
            raise CoopValueError(error_message)

        response = self._send_server_request(
            uri="api/v0/widgets",
            method="POST",
            payload={
                "short_name": short_name,
                "display_name": display_name,
                "description": description,
                "esm_code": esm_code,
                "css_code": css_code,
            },
        )
        self._resolve_server_response(response)
        content = response.json()
        return {
            "short_name": content.get("short_name"),
            "display_name": content.get("display_name"),
            "description": content.get("description"),
        }

    def list_widgets(
        self,
        search_query: Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
    ) -> "ScenarioList":
        """
        Get metadata for all widgets.

        Parameters:
            page (int): Page number for pagination (default: 1)
            page_size (int): Number of widgets per page (default: 10, max: 100)

        Returns:
            List[Dict]: List of widget metadata

        Raises:
            CoopValueError: If page or page_size parameters are invalid
            CoopServerResponseError: If there's an error communicating with the server
        """
        from ..scenarios import Scenario, ScenarioList

        if page < 1:
            raise CoopValueError("The page must be greater than or equal to 1.")
        if page_size < 1:
            raise CoopValueError("The page size must be greater than or equal to 1.")
        if page_size > 100:
            raise CoopValueError("The page size must be less than or equal to 100.")

        params = {
            "page": page,
            "page_size": page_size,
        }
        if search_query:
            params["search_query"] = search_query

        response = self._send_server_request(
            uri="api/v0/widgets/list",
            method="GET",
            params=params,
        )
        self._resolve_server_response(response)
        content = response.json()
        widgets = []
        for widget in content.get("widgets", []):
            scenario = Scenario(
                {
                    "short_name": widget.get("short_name"),
                    "display_name": widget.get("display_name"),
                    "description": widget.get("description"),
                    "owner": widget.get("owner"),
                    "created_ts": widget.get("created_ts"),
                    "last_updated_ts": widget.get("last_updated_ts"),
                    "esm_code_size_bytes": widget.get("esm_code_size_bytes"),
                    "css_code_size_bytes": widget.get("css_code_size_bytes"),
                }
            )
            widgets.append(scenario)
        return ScenarioList(widgets)

    ## - App-related methods
    def list_apps(self) -> list[str]:
        """List all apps."""
        from ..app.client import EDSLAppClient

        return EDSLAppClient().list_apps()

    def get_widget_metadata(self, short_name: str) -> Dict:
        """
        Get metadata for a specific widget by short name.

        Parameters:
            short_name (str): The short name of the widget

        Returns:
            Dict: Widget metadata including size information

        Raises:
            CoopServerResponseError: If there's an error communicating with the server
        """
        response = self._send_server_request(
            uri=f"api/v0/widgets/{short_name}/metadata",
            method="GET",
        )
        self._resolve_server_response(response)
        content = response.json()
        return {
            "short_name": content.get("short_name"),
            "display_name": content.get("display_name"),
            "description": content.get("description"),
            "owner": content.get("owner"),
            "created_ts": content.get("created_ts"),
            "last_updated_ts": content.get("last_updated_ts"),
            "esm_code_size_bytes": content.get("esm_code_size_bytes"),
            "css_code_size_bytes": content.get("css_code_size_bytes"),
        }

    def get_widget(self, short_name: str) -> Dict:
        """
        Get a specific widget by short name.

        Parameters:
            short_name (str): The short name of the widget

        Returns:
            Dict: Complete widget data including ESM and CSS code

        Raises:
            CoopServerResponseError: If there's an error communicating with the server
        """
        response = self._send_server_request(
            uri=f"api/v0/widgets/{short_name}",
            method="GET",
        )
        self._resolve_server_response(response)
        content = response.json()
        return {
            "short_name": content.get("short_name"),
            "display_name": content.get("display_name"),
            "description": content.get("description"),
            "esm_code": content.get("esm_code"),
            # CSS code is optional, but should be coerced to the empty string if not present
            "css_code": content.get("css_code") or "",
            "esm_code_size_bytes": content.get("esm_code_size_bytes"),
            "css_code_size_bytes": content.get("css_code_size_bytes"),
        }

    def update_widget(
        self,
        existing_short_name: str,
        short_name: Optional[str] = None,
        display_name: Optional[str] = None,
        esm_code: Optional[str] = None,
        css_code: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict:
        """
        Update a widget by short name.

        Parameters:
            existing_short_name (str): The current short name of the widget
            short_name (str, optional): New short name for the widget.
            Must start with a lowercase letter and contain only lowercase letters, digits, and underscores
            display_name (str, optional): New display name for the widget
            description (str, optional): New description for the widget
            esm_code (str, optional): New ESM JavaScript code for the widget
            css_code (str, optional): New CSS code for the widget

        Returns:
            dict: Success status

        Raises:
            CoopServerResponseError: If there's an error communicating with the server
        """
        payload = {}
        if short_name is not None:
            from ..widgets.base_widget import EDSLBaseWidget

            (
                short_name_is_valid,
                error_message,
            ) = EDSLBaseWidget.is_widget_short_name_valid(short_name)
            if not short_name_is_valid:
                raise CoopValueError(error_message)
            payload["short_name"] = short_name
        if display_name is not None:
            payload["display_name"] = display_name
        if description is not None:
            payload["description"] = description
        if esm_code is not None:
            payload["esm_code"] = esm_code
        if css_code is not None:
            payload["css_code"] = css_code

        response = self._send_server_request(
            uri=f"api/v0/widgets/{existing_short_name}",
            method="PATCH",
            payload=payload,
        )
        self._resolve_server_response(response)
        return response.json()

    def delete_widget(self, short_name: str) -> dict:
        """
        Delete a widget by short name.

        Parameters:
            short_name (str): The short name of the widget to delete

        Returns:
            dict: Success status

        Raises:
            CoopServerResponseError: If there's an error communicating with the server
        """
        response = self._send_server_request(
            uri=f"api/v0/widgets/{short_name}",
            method="DELETE",
        )
        self._resolve_server_response(response)
        return response.json()

    ################
    # Objects
    ################
    def _get_alias_url(self, owner_username: str, alias: str) -> Union[str, None]:
        """
        Get the URL of an object by its owner username and alias.
        """
        if owner_username and alias:
            return f"{self.url}/content/{owner_username}/{alias}"
        else:
            return None

    def _scenario_is_file_store(self, scenario_dict: dict) -> bool:
        """
        Check if the scenario object is a valid FileStore.

        Matches keys in the scenario dict against the expected keys for a FileStore.
        """
        file_store_keys = [
            "path",
            "base64_string",
            "binary",
            "suffix",
            "mime_type",
            "external_locations",
            "extracted_text",
        ]
        return all(key in scenario_dict.keys() for key in file_store_keys)

    def create(
        self,
        object: EDSLObject,
        description: Optional[str] = None,
        alias: Optional[str] = None,
        visibility: Optional[VisibilityType] = "private",
    ) -> dict:
        """
        Store an EDSL object in the Expected Parrot cloud service.

        This method uploads an EDSL object (like a Survey, Agent, or Results) to the
        Expected Parrot cloud service for storage, sharing, or further processing.

        Parameters:
            object (EDSLObject): The EDSL object to store (Survey, Agent, Results, etc.)
            description (str, optional): A human-readable description of the object
            alias (str, optional): A custom alias for easier reference later
            visibility (VisibilityType, optional): Access level for the object. One of:
                - "private": Only accessible by the owner
                - "public": Accessible by anyone
                - "unlisted": Accessible with the link, but not listed publicly

        Returns:
            dict: Information about the created object including:
                - url: The URL to access the object
                - alias_url: The URL with the custom alias (if provided)
                - uuid: The unique identifier for the object
                - visibility: The visibility setting
                - version: The EDSL version used to create the object

        Raises:
            CoopServerResponseError: If there's an error communicating with the server

        Example:
            >>> survey = Survey(questions=[QuestionFreeText(question_name="name")])
            >>> result = coop.create(survey, description="Basic survey", visibility="public")
            >>> print(result["url"])  # URL to access the survey
        """
        object_type = ObjectRegistry.get_object_type_by_edsl_class(object)
        object_dict = object.to_dict()

        # Get the object hash
        object_hash = object.get_hash() if hasattr(object, "get_hash") else None

        if object_type == "scenario" and self._scenario_is_file_store(object_dict):
            file_store_metadata = {
                "suffix": object_dict["suffix"],
                "mime_type": object_dict["mime_type"],
            }
        else:
            file_store_metadata = None
        response = self._send_server_request(
            uri="api/v0/object",
            method="POST",
            payload={
                "description": description,
                "alias": alias,
                "json_string": (
                    json.dumps(
                        object_dict,
                        default=self._json_handle_none,
                        allow_nan=False,
                    )
                    if object_type != "scenario"
                    else ""
                ),
                "object_type": object_type,
                "file_store_metadata": file_store_metadata,
                "visibility": visibility,
                "version": self._edsl_version,
                "object_hash": object_hash,  # Include the object hash in the payload
            },
        )
        self._resolve_server_response(response)
        response_json = response.json()

        if object_type == "scenario":
            json_data = json.dumps(
                object_dict,
                default=self._json_handle_none,
                allow_nan=False,
            )
            headers = {"Content-Type": "application/json"}
            if response_json.get("upload_signed_url"):
                signed_url = response_json.get("upload_signed_url")
            else:
                from .exceptions import CoopResponseError

                raise CoopResponseError("No signed url was provided.")

            response = requests.put(
                signed_url, data=json_data.encode(), headers=headers
            )
            self._resolve_gcs_response(response)

            file_store_upload_signed_url = response_json.get(
                "file_store_upload_signed_url"
            )
            if file_store_metadata and not file_store_upload_signed_url:
                from .exceptions import CoopResponseError

                raise CoopResponseError("No file store signed url provided.")
            elif file_store_metadata:
                headers = {"Content-Type": file_store_metadata["mime_type"]}
                # Lint json files prior to upload
                if file_store_metadata["suffix"] == "json":
                    file_store_bytes = base64.b64decode(object_dict["base64_string"])
                    pretty_json_string = json.dumps(
                        json.loads(file_store_bytes), indent=4
                    )
                    byte_data = pretty_json_string.encode("utf-8")
                # Lint python files prior to upload
                elif file_store_metadata["suffix"] == "py":
                    import black

                    file_store_bytes = base64.b64decode(object_dict["base64_string"])
                    python_string = file_store_bytes.decode("utf-8")
                    formatted_python_string = black.format_str(
                        python_string, mode=black.Mode()
                    )
                    byte_data = formatted_python_string.encode("utf-8")
                else:
                    byte_data = base64.b64decode(object_dict["base64_string"])
                response = requests.put(
                    file_store_upload_signed_url,
                    data=byte_data,
                    headers=headers,
                )
                self._resolve_gcs_response(response)

        owner_username = response_json.get("owner_username")
        object_alias = response_json.get("alias")

        return {
            "description": response_json.get("description"),
            "object_type": object_type,
            "url": f"{self.url}/content/{response_json.get('uuid')}",
            "alias_url": self._get_alias_url(owner_username, object_alias),
            "uuid": response_json.get("uuid"),
            "version": self._edsl_version,
            "visibility": response_json.get("visibility"),
        }

    def get(
        self,
        url_or_uuid: Union[str, UUID],
        expected_object_type: Optional[ObjectType] = None,
    ) -> EDSLObject:
        """
        Retrieve an EDSL object from the Expected Parrot cloud service.

        This method downloads and deserializes an EDSL object from the cloud service
        using either its UUID, URL, or username/alias combination.

        Parameters:
            url_or_uuid (Union[str, UUID]): Identifier for the object to retrieve.
                Can be one of:
                - UUID string (e.g., "123e4567-e89b-12d3-a456-426614174000")
                - Full URL (e.g., "https://expectedparrot.com/content/123e4567...")
                - Alias URL (e.g., "https://expectedparrot.com/content/username/my-survey")
            expected_object_type (ObjectType, optional): If provided, validates that the
                retrieved object is of the expected type (e.g., "survey", "agent")

        Returns:
            EDSLObject: The retrieved object as its original EDSL class instance
            (e.g., Survey, Agent, Results)

        Raises:
            CoopNoUUIDError: If no UUID or URL is provided
            CoopInvalidURLError: If the URL format is invalid
            CoopServerResponseError: If the server returns an error (e.g., not found,
                unauthorized access)
            Exception: If the retrieved object doesn't match the expected type

        Notes:
            - If the object's visibility is set to "private", you must be the owner to access it
            - For objects stored with an alias, you can use either the UUID or the alias URL

        Example:
            >>> survey = coop.get("123e4567-e89b-12d3-a456-426614174000")
            >>> survey = coop.get("https://expectedparrot.com/content/username/my-survey")
            >>> survey = coop.get(url, expected_object_type="survey")  # Validates the type
        """
        obj_uuid, owner_username, alias = self._resolve_uuid_or_alias(url_or_uuid)

        # Handle alias-based retrieval with new/old format detection
        if not obj_uuid and owner_username and alias:
            # First, get object info to determine format and UUID
            info_response = self._send_server_request(
                uri="api/v0/object/alias/info",
                method="GET",
                params={"owner_username": owner_username, "alias": alias},
            )
            self._resolve_server_response(info_response)
            info_data = info_response.json()

            obj_uuid = info_data.get("uuid")
            is_new_format = info_data.get("is_new_format", False)

            # Validate object type if expected
            if expected_object_type:
                actual_object_type = info_data.get("object_type")
                if actual_object_type != expected_object_type:
                    from .exceptions import CoopObjectTypeError

                    raise CoopObjectTypeError(
                        f"Expected {expected_object_type=} but got {actual_object_type=}"
                    )

            # Use pull method for new format objects
            if is_new_format:
                return self.pull(obj_uuid, expected_object_type)

        # Handle UUID-based retrieval or legacy alias objects
        if obj_uuid:
            response = self._send_server_request(
                uri="api/v0/object",
                method="GET",
                params={"uuid": obj_uuid},
            )
        else:
            response = self._send_server_request(
                uri="api/v0/object/alias",
                method="GET",
                params={"owner_username": owner_username, "alias": alias},
            )

        self._resolve_server_response(response)
        json_string = response.json().get("json_string")
        if "load_from:" in json_string[0:12]:
            load_link = json_string.split("load_from:")[1]
            object_data = requests.get(load_link)
            self._resolve_gcs_response(object_data)
            json_string = object_data.text
        object_type = response.json().get("object_type")
        if expected_object_type and object_type != expected_object_type:
            from .exceptions import CoopObjectTypeError

            raise CoopObjectTypeError(
                f"Expected {expected_object_type=} but got {object_type=}"
            )
        edsl_class = ObjectRegistry.get_edsl_class_by_object_type(object_type)
        object = edsl_class.from_dict(json.loads(json_string))
        if object_type == "results":
            object.initialize_cache_from_results()
        return object

    def _validate_object_types(
        self, object_type: Union[ObjectType, List[ObjectType]]
    ) -> List[ObjectType]:
        """
        Validate object types and return a list of valid types.

        Args:
            object_type: Single object type or list of object types to validate

        Returns:
            List of validated object types

        Raises:
            CoopValueError: If any object type is invalid
        """
        valid_object_types = [o["object_type"] for o in ObjectRegistry._get_objects()]
        if isinstance(object_type, list):
            invalid_types = [t for t in object_type if t not in valid_object_types]
            if invalid_types:
                raise CoopValueError(
                    f"Invalid object type(s): {invalid_types}. "
                    f"Valid types are: {list(valid_object_types)}"
                )
            return object_type
        else:
            if object_type not in valid_object_types:
                raise CoopValueError(
                    f"Invalid object type: {object_type}. "
                    f"Valid types are: {list(valid_object_types)}"
                )
            return [object_type]

    def _validate_alias(self, alias: Optional[str]) -> None:
        """
        Validate that an alias contains only letters, numbers, and hyphens.

        Args:
            alias: The alias string to validate

        Raises:
            CoopValueError: If the alias contains invalid characters

        Example:
            >>> coop = Coop()
            >>> coop._validate_alias("my-valid-alias123")  # OK
            >>> coop._validate_alias("invalid alias!")  # Raises CoopValueError
        """
        if alias is None:
            return

        import re

        # Check if alias contains only letters, numbers, and hyphens
        if not re.match(r"^[a-zA-Z0-9-]+$", alias):
            raise CoopValueError(
                f"Invalid alias: '{alias}'. "
                "Alias must contain only letters, numbers, and hyphens."
            )

    def _validate_visibility_types(
        self, visibility: Union[VisibilityType, List[VisibilityType]]
    ) -> List[VisibilityType]:
        """
        Validate visibility types and return a list of valid types.

        Args:
            visibility: Single visibility type or list of visibility types to validate

        Returns:
            List of validated visibility types

        Raises:
            CoopValueError: If any visibility type is invalid
        """
        valid_visibility_types = ["private", "public", "unlisted"]
        if isinstance(visibility, list):
            invalid_visibilities = [
                v for v in visibility if v not in valid_visibility_types
            ]
            if invalid_visibilities:
                raise CoopValueError(
                    f"Invalid visibility type(s): {invalid_visibilities}. "
                    f"Valid types are: {valid_visibility_types}"
                )
            return visibility
        else:
            if visibility not in valid_visibility_types:
                raise CoopValueError(
                    f"Invalid visibility type: {visibility}. "
                    f"Valid types are: {valid_visibility_types}"
                )
            return [visibility]

    def list(
        self,
        object_type: Union[ObjectType, List[ObjectType], None] = None,
        visibility: Union[VisibilityType, List[VisibilityType], None] = None,
        search_query: Union[str, None] = None,
        page: int = 1,
        page_size: int = 10,
        sort_ascending: bool = False,
        community: bool = False,
    ) -> "CoopRegularObjects":
        """
        Retrieve objects either owned by the user or shared with them.

        Notes:
        - search_query only works with the description field.
        - If sort_ascending is False, then the most recently created objects are returned first.
        - If community is False, then only objects owned by the user or shared with the user are returned.
        - If community is True, then only public objects not owned by the user are returned.
        """
        from ..scenarios import Scenario

        if page < 1:
            raise CoopValueError("The page must be greater than or equal to 1.")
        if page_size < 1:
            raise CoopValueError("The page size must be greater than or equal to 1.")
        if page_size > 100:
            raise CoopValueError("The page size must be less than or equal to 100.")

        params = {
            "page": page,
            "page_size": page_size,
            "sort_ascending": sort_ascending,
        }
        if object_type:
            params["type"] = self._validate_object_types(object_type)
        if visibility:
            params["visibility"] = self._validate_visibility_types(visibility)
        if search_query:
            params["search_query"] = search_query
        if community:
            params["community"] = True

        response = self._send_server_request(
            uri="api/v0/object/list",
            method="GET",
            params=params,
        )
        self._resolve_server_response(response)
        content = response.json()
        objects = []
        for o in content.get("objects", []):
            object = Scenario(
                {
                    "uuid": o.get("uuid"),
                    "object_type": o.get("object_type"),
                    "alias": o.get("alias"),
                    "owner_username": o.get("owner_username"),
                    "description": o.get("description"),
                    "visibility": o.get("visibility"),
                    "version": o.get("version"),
                    "url": f"{self.url}/content/{o.get('uuid')}",
                    "alias_url": self._get_alias_url(
                        o.get("owner_username"), o.get("alias")
                    ),
                    "last_updated_ts": o.get("last_updated_ts"),
                    "created_ts": o.get("created_ts"),
                }
            )
            if community:
                object["view_count"] = o.get("view_count")
                object["download_count"] = o.get("download_count")
            objects.append(object)

        current_page = content.get("current_page")
        total_pages = content.get("total_pages")
        page_size = content.get("page_size")
        total_count = content.get("total_count")

        return CoopRegularObjects(
            objects,
            current_page=current_page,
            total_pages=total_pages,
            page_size=page_size,
            total_count=total_count,
        )

    def get_metadata(self, url_or_uuid: Union[str, UUID]) -> dict:
        """
        Get an object's metadata from the server.

        :param url_or_uuid: The UUID or URL of the object.
            URLs can be in the form content/uuid or content/username/alias.
        """
        obj_uuid, owner_username, alias = self._resolve_uuid_or_alias(url_or_uuid)

        if obj_uuid:
            uri = "api/v0/object/metadata"
            params = {"uuid": obj_uuid}
        else:
            uri = "api/v0/object/alias/metadata"
            params = {"owner_username": owner_username, "alias": alias}

        response = self._send_server_request(
            uri=uri,
            method="GET",
            params=params,
        )

        self._resolve_server_response(response)
        content = response.json()
        return {
            "uuid": content.get("uuid"),
            "object_type": content.get("object_type"),
            "alias": content.get("alias"),
            "owner_username": content.get("owner_username"),
            "description": content.get("description"),
            "visibility": content.get("visibility"),
            "version": content.get("version"),
            "url": f"{self.url}/content/{content.get('uuid')}",
            "alias_url": self._get_alias_url(
                content.get("owner_username"), content.get("alias")
            ),
            "last_updated_ts": content.get("last_updated_ts"),
            "created_ts": content.get("created_ts"),
        }

    def delete(self, url_or_uuid: Union[str, UUID]) -> dict:
        """
        Delete an object from the server.

        :param url_or_uuid: The UUID or URL of the object.
            URLs can be in the form content/uuid or content/username/alias.
        """
        obj_uuid, owner_username, alias = self._resolve_uuid_or_alias(url_or_uuid)

        if obj_uuid:
            uri = "api/v0/object"
            params = {"uuid": obj_uuid}
        else:
            uri = "api/v0/object/alias"
            params = {"owner_username": owner_username, "alias": alias}

        response = self._send_server_request(
            uri=uri,
            method="DELETE",
            params=params,
        )

        self._resolve_server_response(response)
        return response.json()

    def patch(
        self,
        url_or_uuid: Union[str, UUID],
        description: Optional[str] = None,
        alias: Optional[str] = None,
        value: Optional[EDSLObject] = None,
        visibility: Optional[VisibilityType] = None,
    ) -> dict:
        """
        Change the attributes of an uploaded object

        :param url_or_uuid: The UUID or URL of the object.
            URLs can be in the form content/uuid or content/username/alias.
        :param description: Optional new description
        :param alias: Optional new alias
        :param value: Optional new object value
        :param visibility: Optional new visibility setting
        """
        # Validate alias before attempting to patch
        self._validate_alias(alias)

        if (
            description is None
            and visibility is None
            and value is None
            and alias is None
        ):
            from .exceptions import CoopPatchError

            raise CoopPatchError("Nothing to patch.")

        obj_uuid, owner_username, obj_alias = self._resolve_uuid_or_alias(url_or_uuid)

        # If we're updating the value, we need to check the storage format
        if value:
            # If we don't have a UUID but have an alias, get the UUID and format info first
            if not obj_uuid and owner_username and obj_alias:
                # Get object info including UUID and format
                info_response = self._send_server_request(
                    uri="api/v0/object/alias/info",
                    method="GET",
                    params={"owner_username": owner_username, "alias": obj_alias},
                )
                self._resolve_server_response(info_response)
                info_data = info_response.json()

                obj_uuid = info_data.get("uuid")
                is_new_format = info_data.get("is_new_format", False)
            else:
                # We have a UUID, check the format
                format_check_response = self._send_server_request(
                    uri="api/v0/object/check-format",
                    method="POST",
                    payload={"object_uuid": str(obj_uuid)},
                )
                self._resolve_server_response(format_check_response)
                format_data = format_check_response.json()
                is_new_format = format_data.get("is_new_format", False)

            if is_new_format:
                # Handle new format objects: update metadata first, then upload content
                return self._patch_new_format_object(
                    obj_uuid, description, alias, value, visibility
                )

        # Handle traditional format objects or metadata-only updates
        if obj_uuid:
            uri = "api/v0/object"
            params = {"uuid": obj_uuid}
        else:
            uri = "api/v0/object/alias"
            params = {"owner_username": owner_username, "alias": obj_alias}

        response = self._send_server_request(
            uri=uri,
            method="PATCH",
            params=params,
            payload={
                "description": description,
                "alias": alias,
                "json_string": (
                    json.dumps(
                        value.to_dict(),
                        default=self._json_handle_none,
                        allow_nan=False,
                    )
                    if value
                    else None
                ),
                "visibility": visibility,
            },
        )
        self._resolve_server_response(response)
        return response.json()

    def _patch_new_format_object(
        self,
        obj_uuid: UUID,
        description: Optional[str],
        alias: Optional[str],
        value: EDSLObject,
        visibility: Optional[VisibilityType],
    ) -> dict:
        """
        Handle patching of objects stored in the new format (GCS).
        """
        # Step 1: Update metadata only (no json_string)
        if description is not None or alias is not None or visibility is not None:
            metadata_response = self._send_server_request(
                uri="api/v0/object",
                method="PATCH",
                params={"uuid": obj_uuid},
                payload={
                    "description": description,
                    "alias": alias,
                    "json_string": None,  # Don't send content to traditional endpoint
                    "visibility": visibility,
                },
            )
            self._resolve_server_response(metadata_response)

        # Step 2: Get signed upload URL for content update
        upload_url_response = self._send_server_request(
            uri="api/v0/object/upload-url",
            method="POST",
            payload={"object_uuid": str(obj_uuid)},
        )
        self._resolve_server_response(upload_url_response)
        upload_data = upload_url_response.json()

        # Step 3: Upload the object content to GCS
        signed_url = upload_data.get("signed_url")
        if not signed_url:
            raise CoopServerResponseError("Failed to get signed upload URL")

        json_content = json.dumps(
            value.to_dict(),
            default=self._json_handle_none,
            allow_nan=False,
        )

        # Upload to GCS using signed URL
        gcs_response = requests.put(
            signed_url,
            data=json_content,
            headers={"Content-Type": "application/json"},
        )

        if gcs_response.status_code != 200:
            raise CoopServerResponseError(
                f"Failed to upload object to GCS: {gcs_response.status_code}"
            )

        # Step 4: Confirm upload and trigger queue worker processing
        confirm_response = self._send_server_request(
            uri="api/v0/object/confirm-upload",
            method="POST",
            payload={"object_uuid": str(obj_uuid)},
        )
        self._resolve_server_response(confirm_response)
        confirm_data = confirm_response.json()

        return {
            "status": "success",
            "message": "Object updated successfully (new format - uploaded to GCS and processing triggered)",
            "object_uuid": str(obj_uuid),
            "processing_started": confirm_data.get("processing_started", False),
        }

    ################
    # Remote Cache
    ################
    def remote_cache_get(
        self,
        job_uuid: Optional[Union[str, UUID]] = None,
    ) -> List[CacheEntry]:
        """
        Get all remote cache entries.

        :param optional select_keys: Only return CacheEntry objects with these keys.

        >>> coop.remote_cache_get(job_uuid="...")
        [CacheEntry(...), CacheEntry(...), ...]
        """
        if job_uuid is None:
            from .exceptions import CoopValueError

            raise CoopValueError("Must provide a job_uuid.")
        response = self._send_server_request(
            uri="api/v0/remote-cache/get-many-by-job",
            method="POST",
            payload={
                "job_uuid": str(job_uuid),
            },
            timeout=40,
        )
        self._resolve_server_response(response)
        return [
            CacheEntry.from_dict(json.loads(v.get("json_string")))
            for v in response.json()
        ]

    def remote_cache_get_by_key(
        self,
        select_keys: Optional[List[str]] = None,
    ) -> List[CacheEntry]:
        """
        Get all remote cache entries.

        :param optional select_keys: Only return CacheEntry objects with these keys.

        >>> coop.remote_cache_get_by_key(selected_keys=["..."])
        [CacheEntry(...), CacheEntry(...), ...]
        """
        if select_keys is None or len(select_keys) == 0:
            from .exceptions import CoopValueError

            raise CoopValueError("Must provide a non-empty list of select_keys.")
        response = self._send_server_request(
            uri="api/v0/remote-cache/get-many-by-key",
            method="POST",
            payload={
                "selected_keys": select_keys,
            },
            timeout=40,
        )
        self._resolve_server_response(response)
        return [
            CacheEntry.from_dict(json.loads(v.get("json_string")))
            for v in response.json()
        ]

    def remote_inference_create(
        self,
        job: "Jobs",
        description: Optional[str] = None,
        status: RemoteJobStatus = "queued",
        visibility: Optional[VisibilityType] = "private",
        initial_results_visibility: Optional[VisibilityType] = "private",
        iterations: Optional[int] = 1,
        fresh: Optional[bool] = False,
    ) -> RemoteInferenceCreationInfo:
        """
        Create a remote inference job for execution in the Expected Parrot cloud.

        This method sends a job to be executed in the cloud, which can be more efficient
        for large jobs or when you want to run jobs in the background. The job execution
        is handled by Expected Parrot's infrastructure, and you can check the status
        and retrieve results later.

        Parameters:
            job (Jobs): The EDSL job to run in the cloud
            description (str, optional): A human-readable description of the job
            status (RemoteJobStatus): Initial status, should be "queued" for normal use
                Possible values: "queued", "running", "completed", "failed"
            visibility (VisibilityType): Access level for the job information. One of:
                - "private": Only accessible by the owner
                - "public": Accessible by anyone
                - "unlisted": Accessible with the link, but not listed publicly
            initial_results_visibility (VisibilityType): Access level for the job results
            iterations (int): Number of times to run each interview (default: 1)
            fresh (bool): If True, ignore existing cache entries and generate new results

        Returns:
            RemoteInferenceCreationInfo: Information about the created job including:
                - uuid: The unique identifier for the job
                - description: The job description
                - status: Current status of the job
                - iterations: Number of iterations for each interview
                - visibility: Access level for the job
                - version: EDSL version used to create the job

        Raises:
            CoopServerResponseError: If there's an error communicating with the server

        Notes:
            - Remote jobs run asynchronously and may take time to complete
            - Use remote_inference_get() with the returned UUID to check status
            - Credits are consumed based on the complexity of the job

        Example:
            >>> from edsl.jobs import Jobs
            >>> job = Jobs.example()
            >>> job_info = coop.remote_inference_create(job=job, description="My job")
            >>> print(f"Job created with UUID: {job_info['uuid']}")
        """
        self._logger.info(
            f"Creating remote inference job with description: {description}"
        )

        response = self._send_server_request(
            uri="api/v0/new-remote-inference",
            method="POST",
            payload={
                "json_string": "offloaded",
                "description": description,
                "status": status,
                "iterations": iterations,
                "visibility": visibility,
                "version": self._edsl_version,
                "initial_results_visibility": initial_results_visibility,
                "fresh": fresh,
            },
        )
        self._resolve_server_response(response)
        response_json = response.json()
        upload_signed_url = response_json.get("upload_signed_url")
        if not upload_signed_url:
            from .exceptions import CoopResponseError

            raise CoopResponseError("No signed url was provided.")

        response = requests.put(
            upload_signed_url,
            data=json.dumps(
                job.to_dict(),
                default=self._json_handle_none,
            ).encode(),
            headers={"Content-Type": "application/json"},
        )
        self._resolve_gcs_response(response)

        job_uuid = response_json.get("job_uuid")

        response = self._send_server_request(
            uri="api/v0/new-remote-inference/uploaded",
            method="POST",
            payload={
                "job_uuid": job_uuid,
                "message": "Job uploaded successfully",
                "nr_questions": job.nr_questions,
            },
        )
        response_json = response.json()

        job_uuid = response_json.get("job_uuid")
        self._logger.info(
            f"Successfully created remote inference job with UUID: {job_uuid}"
        )

        return RemoteInferenceCreationInfo(
            **{
                "uuid": job_uuid,
                "description": response_json.get("description", ""),
                "status": response_json.get("status"),
                "iterations": response_json.get("iterations", ""),
                "visibility": response_json.get("visibility", ""),
                "version": self._edsl_version,
            }
        )

    def old_remote_inference_create(
        self,
        job: "Jobs",
        description: Optional[str] = None,
        status: RemoteJobStatus = "queued",
        visibility: Optional[VisibilityType] = "private",
        initial_results_visibility: Optional[VisibilityType] = "private",
        iterations: Optional[int] = 1,
        fresh: Optional[bool] = False,
    ) -> RemoteInferenceCreationInfo:
        """
        Create a remote inference job for execution in the Expected Parrot cloud.

        This method sends a job to be executed in the cloud, which can be more efficient
        for large jobs or when you want to run jobs in the background. The job execution
        is handled by Expected Parrot's infrastructure, and you can check the status
        and retrieve results later.

        Parameters:
            job (Jobs): The EDSL job to run in the cloud
            description (str, optional): A human-readable description of the job
            status (RemoteJobStatus): Initial status, should be "queued" for normal use
                Possible values: "queued", "running", "completed", "failed"
            visibility (VisibilityType): Access level for the job information. One of:
                - "private": Only accessible by the owner
                - "public": Accessible by anyone
                - "unlisted": Accessible with the link, but not listed publicly
            initial_results_visibility (VisibilityType): Access level for the job results
            iterations (int): Number of times to run each interview (default: 1)
            fresh (bool): If True, ignore existing cache entries and generate new results

        Returns:
            RemoteInferenceCreationInfo: Information about the created job including:
                - uuid: The unique identifier for the job
                - description: The job description
                - status: Current status of the job
                - iterations: Number of iterations for each interview
                - visibility: Access level for the job
                - version: EDSL version used to create the job

        Raises:
            CoopServerResponseError: If there's an error communicating with the server

        Notes:
            - Remote jobs run asynchronously and may take time to complete
            - Use remote_inference_get() with the returned UUID to check status
            - Credits are consumed based on the complexity of the job

        Example:
            >>> from edsl.jobs import Jobs
            >>> job = Jobs.example()
            >>> job_info = coop.remote_inference_create(job=job, description="My job")
            >>> print(f"Job created with UUID: {job_info['uuid']}")
        """
        response = self._send_server_request(
            uri="api/v0/remote-inference",
            method="POST",
            payload={
                "json_string": json.dumps(
                    job.to_dict(),
                    default=self._json_handle_none,
                ),
                "description": description,
                "status": status,
                "iterations": iterations,
                "visibility": visibility,
                "version": self._edsl_version,
                "initial_results_visibility": initial_results_visibility,
                "fresh": fresh,
            },
        )
        self._resolve_server_response(response)
        response_json = response.json()

        return RemoteInferenceCreationInfo(
            **{
                "uuid": response_json.get("job_uuid"),
                "description": response_json.get("description"),
                "status": response_json.get("status"),
                "iterations": response_json.get("iterations"),
                "visibility": response_json.get("visibility"),
                "version": self._edsl_version,
            }
        )

    def remote_inference_get(
        self,
        job_uuid: Optional[str] = None,
        results_uuid: Optional[str] = None,
        include_json_string: Optional[bool] = False,
    ) -> RemoteInferenceResponse:
        """
        Get the status and details of a remote inference job.

        This method retrieves the current status and information about a remote job,
        including links to results if the job has completed successfully.

        Parameters:
            job_uuid (str, optional): The UUID of the remote job to check
            results_uuid (str, optional): The UUID of the results associated with the job
                (can be used if you only have the results UUID)
            include_json_string (bool, optional): If True, include the json string for the job in the response

        Returns:
            RemoteInferenceResponse: Information about the job including:
                job_uuid: The unique identifier for the job
                results_uuid: The UUID of the results
                results_url: URL to access the results
                status: Current status ("queued", "running", "completed", "failed")
                version: EDSL version used for the job
                job_json_string: The json string for the job (if include_json_string is True)
                latest_job_run_details: Metadata about the job status
                    interview_details: Metadata about the job interview status (for jobs that have reached running status)
                        total_interviews: The total number of interviews in the job
                        completed_interviews: The number of completed interviews
                        interviews_with_exceptions: The number of completed interviews that have exceptions
                        exception_counters: A list of exception counts for the job
                            exception_type: The type of exception
                            inference_service: The inference service
                            model: The model
                            question_name: The name of the question
                            exception_count: The number of exceptions
                    failure_reason: The reason the job failed (failed jobs only)
                    failure_description: The description of the failure (failed jobs only)
                    error_report_uuid: The UUID of the error report (partially failed jobs only)
                    cost_credits: The cost of the job run in credits
                    cost_usd: The cost of the job run in USD
                    expenses: The expenses incurred by the job run
                        service: The service
                        model: The model
                        token_type: The type of token (input or output)
                        price_per_million_tokens: The price per million tokens
                        tokens_count: The number of tokens consumed
                        cost_credits: The cost of the service/model/token type combination in credits
                        cost_usd: The cost of the service/model/token type combination in USD

        Raises:
            ValueError: If neither job_uuid nor results_uuid is provided
            CoopServerResponseError: If there's an error communicating with the server

        Notes:
            - Either job_uuid or results_uuid must be provided
            - If both are provided, job_uuid takes precedence
            - For completed jobs, you can use the results_url to view or download results
            - For failed jobs, check the latest_error_report_url for debugging information

        Example:
            >>> job_status = coop.remote_inference_get("9f8484ee-b407-40e4-9652-4133a7236c9c")
            >>> print(f"Job status: {job_status['status']}")
            >>> if job_status['status'] == 'completed':
            ...     print(f"Results available at: {job_status['results_url']}")
        """
        if job_uuid is None and results_uuid is None:
            from .exceptions import CoopValueError

            raise CoopValueError("Either job_uuid or results_uuid must be provided.")
        elif job_uuid is not None:
            params = {"job_uuid": job_uuid}
        else:
            params = {"results_uuid": results_uuid}
        if include_json_string:
            params["include_json_string"] = include_json_string

        response = self._send_server_request(
            uri="api/v0/remote-inference",
            method="GET",
            params=params,
        )
        self._resolve_server_response(response)
        data = response.json()

        results_uuid = data.get("results_uuid")

        if results_uuid is None:
            results_url = None
        else:
            results_url = f"{self.url}/content/{results_uuid}"

        latest_job_run_details = data.get("latest_job_run_details", {})
        if data.get("status") == "partial_failed":
            latest_error_report_uuid = latest_job_run_details.get("error_report_uuid")
            if latest_error_report_uuid is None:
                latest_job_run_details["error_report_url"] = None
            else:
                latest_error_report_url = (
                    f"{self.url}/home/remote-inference/error/{latest_error_report_uuid}"
                )
                latest_job_run_details["error_report_url"] = latest_error_report_url

        return RemoteInferenceResponse(
            **{
                "job_uuid": data.get("job_uuid"),
                "results_uuid": results_uuid,
                "results_url": results_url,
                "status": data.get("status"),
                "version": data.get("version"),
                "job_json_string": data.get("job_json_string"),
                "latest_job_run_details": latest_job_run_details,
            }
        )

    def new_remote_inference_get(
        self,
        job_uuid: Optional[str] = None,
        results_uuid: Optional[str] = None,
        include_json_string: Optional[bool] = False,
    ) -> RemoteInferenceResponse:
        """
        Get the status and details of a remote inference job.

        This method retrieves the current status and information about a remote job,
        including links to results if the job has completed successfully.

        Parameters:
            job_uuid (str, optional): The UUID of the remote job to check
            results_uuid (str, optional): The UUID of the results associated with the job
                (can be used if you only have the results UUID)
            include_json_string (bool, optional): If True, include the json string for the job in the response

        Returns:
            RemoteInferenceResponse: Information about the job including:
                job_uuid: The unique identifier for the job
                results_uuid: The UUID of the results
                results_url: URL to access the results
                status: Current status ("queued", "running", "completed", "failed")
                version: EDSL version used for the job
                job_json_string: The json string for the job (if include_json_string is True)
                latest_job_run_details: Metadata about the job status
                    interview_details: Metadata about the job interview status (for jobs that have reached running status)
                        total_interviews: The total number of interviews in the job
                        completed_interviews: The number of completed interviews
                        interviews_with_exceptions: The number of completed interviews that have exceptions
                        exception_counters: A list of exception counts for the job
                            exception_type: The type of exception
                            inference_service: The inference service
                            model: The model
                            question_name: The name of the question
                            exception_count: The number of exceptions
                    failure_reason: The reason the job failed (failed jobs only)
                    failure_description: The description of the failure (failed jobs only)
                    error_report_uuid: The UUID of the error report (partially failed jobs only)
                    cost_credits: The cost of the job run in credits
                    cost_usd: The cost of the job run in USD
                    expenses: The expenses incurred by the job run
                        service: The service
                        model: The model
                        token_type: The type of token (input or output)
                        price_per_million_tokens: The price per million tokens
                        tokens_count: The number of tokens consumed
                        cost_credits: The cost of the service/model/token type combination in credits
                        cost_usd: The cost of the service/model/token type combination in USD

        Raises:
            ValueError: If neither job_uuid nor results_uuid is provided
            CoopServerResponseError: If there's an error communicating with the server

        Notes:
            - Either job_uuid or results_uuid must be provided
            - If both are provided, job_uuid takes precedence
            - For completed jobs, you can use the results_url to view or download results
            - For failed jobs, check the latest_error_report_url for debugging information

        Example:
            >>> job_status = coop.new_remote_inference_get("9f8484ee-b407-40e4-9652-4133a7236c9c")
            >>> print(f"Job status: {job_status['status']}")
            >>> if job_status['status'] == 'completed':
            ...     print(f"Results available at: {job_status['results_url']}")
        """
        if job_uuid is None and results_uuid is None:
            from .exceptions import CoopValueError

            raise CoopValueError("Either job_uuid or results_uuid must be provided.")
        elif job_uuid is not None:
            params = {"job_uuid": job_uuid}
        else:
            params = {"results_uuid": results_uuid}
        if include_json_string:
            params["include_json_string"] = include_json_string

        response = self._send_server_request(
            uri="api/v0/remote-inference",
            method="GET",
            params=params,
        )
        self._resolve_server_response(response)
        data = response.json()

        results_uuid = data.get("results_uuid")

        if results_uuid is None:
            results_url = None
        else:
            results_url = f"{self.url}/content/{results_uuid}"

        latest_job_run_details = data.get("latest_job_run_details", {})
        if data.get("status") == "partial_failed":
            latest_error_report_uuid = latest_job_run_details.get("error_report_uuid")
            if latest_error_report_uuid is None:
                latest_job_run_details["error_report_url"] = None
            else:
                latest_error_report_url = (
                    f"{self.url}/home/remote-inference/error/{latest_error_report_uuid}"
                )
                latest_job_run_details["error_report_url"] = latest_error_report_url

        json_string = data.get("job_json_string")

        # The job has been offloaded to GCS
        if include_json_string and json_string == "offloaded":
            # Attempt to fetch JSON string from GCS
            response = self._send_server_request(
                uri="api/v0/remote-inference/pull",
                method="POST",
                payload={"job_uuid": job_uuid},
            )
            # Handle any errors in the response
            self._resolve_server_response(response)
            if "signed_url" not in response.json():
                from .exceptions import CoopResponseError

                raise CoopResponseError("No signed url was provided.")
            signed_url = response.json().get("signed_url")

            if signed_url == "":  # The job is in legacy format
                job_json = json_string

            try:
                response = requests.get(signed_url)
                self._resolve_gcs_response(response)
                job_json = json.dumps(response.json())
            except Exception:
                job_json = json_string

        # If the job is in legacy format, we should already have the JSON string
        # from the first API call
        elif include_json_string and not json_string == "offloaded":
            job_json = json_string

        # If include_json_string is False, we don't need the JSON string at all
        else:
            job_json = None

        return RemoteInferenceResponse(
            **{
                "job_uuid": data.get("job_uuid"),
                "results_uuid": results_uuid,
                "results_url": results_url,
                "status": data.get("status"),
                "version": data.get("version"),
                "job_json_string": job_json,
                "latest_job_run_details": latest_job_run_details,
            }
        )

    def _validate_remote_job_status_types(
        self, status: Union[RemoteJobStatus, List[RemoteJobStatus]]
    ) -> List[RemoteJobStatus]:
        """
        Validate visibility types and return a list of valid types.

        Args:
            visibility: Single visibility type or list of visibility types to validate

        Returns:
            List of validated visibility types

        Raises:
            CoopValueError: If any visibility type is invalid
        """
        valid_status_types = [
            "queued",
            "running",
            "completed",
            "failed",
            "cancelled",
            "cancelling",
            "partial_failed",
        ]
        if isinstance(status, list):
            invalid_statuses = [s for s in status if s not in valid_status_types]
            if invalid_statuses:
                raise CoopValueError(
                    f"Invalid status type(s): {invalid_statuses}. "
                    f"Valid types are: {valid_status_types}"
                )
            return status
        else:
            if status not in valid_status_types:
                raise CoopValueError(
                    f"Invalid status type: {status}. "
                    f"Valid types are: {valid_status_types}"
                )
            return [status]

    def remote_inference_list(
        self,
        status: Union[RemoteJobStatus, List[RemoteJobStatus], None] = None,
        search_query: Union[str, None] = None,
        page: int = 1,
        page_size: int = 10,
        sort_ascending: bool = False,
    ) -> "CoopJobsObjects":
        """
        Retrieve jobs owned by the user.

        Notes:
        - search_query only works with the description field.
        - If sort_ascending is False, then the most recently created jobs are returned first.
        """
        from ..scenarios import Scenario

        if page < 1:
            raise CoopValueError("The page must be greater than or equal to 1.")
        if page_size < 1:
            raise CoopValueError("The page size must be greater than or equal to 1.")
        if page_size > 100:
            raise CoopValueError("The page size must be less than or equal to 100.")

        params = {
            "page": page,
            "page_size": page_size,
            "sort_ascending": sort_ascending,
        }
        if status:
            params["status"] = self._validate_remote_job_status_types(status)
        if search_query:
            params["search_query"] = search_query

        response = self._send_server_request(
            uri="api/v0/remote-inference/list",
            method="GET",
            params=params,
        )
        self._resolve_server_response(response)
        content = response.json()
        jobs = []
        for o in content:
            job = Scenario(
                {
                    "uuid": o.get("uuid"),
                    "description": o.get("description"),
                    "status": o.get("status"),
                    "cost_credits": o.get("cost_credits"),
                    "iterations": o.get("iterations"),
                    "results_uuid": o.get("results_uuid"),
                    "latest_error_report_uuid": o.get("latest_error_report_uuid"),
                    "latest_failure_reason": o.get("latest_failure_reason"),
                    "version": o.get("version"),
                    "created_ts": o.get("created_ts"),
                }
            )
            jobs.append(job)

        return CoopJobsObjects(jobs)

    def get_running_jobs(self) -> List[str]:
        """
        Get a list of currently running job IDs.

        Returns:
            list[str]: List of running job UUIDs
        """
        response = self._send_server_request(uri="jobs/status", method="GET")
        self._resolve_server_response(response)
        return response.json().get("running_jobs", [])

    def remote_inference_cost(
        self, input: Union["Jobs", "Survey"], iterations: int = 1
    ) -> int:
        """
        Get the estimated cost in credits of a remote inference job.

        :param input: The EDSL job to send to the server.

        >>> job = Jobs.example()
        >>> coop.remote_inference_cost(input=job)
        {'credits_hold': 0.77, 'usd': 0.0076950000000000005}
        """
        from ..jobs import Jobs
        from ..surveys import Survey

        if isinstance(input, Jobs):
            job = input
        elif isinstance(input, Survey):
            job = Jobs(survey=input)
        else:
            from .exceptions import CoopTypeError

            raise CoopTypeError("Input must be either a Job or a Survey.")

        response = self._send_server_request(
            uri="api/v0/remote-inference/cost",
            method="POST",
            payload={
                "json_string": json.dumps(
                    job.to_dict(),
                    default=self._json_handle_none,
                ),
                "iterations": iterations,
            },
        )
        self._resolve_server_response(response)
        response_json = response.json()
        return {
            "credits_hold": response_json.get("cost_in_credits"),
            "usd": response_json.get("cost_in_usd"),
        }

    ################
    # HUMAN SURVEYS
    ################
    def create_human_survey(
        self,
        survey: "Survey",
        scenario_list: Optional["ScenarioList"] = None,
        scenario_list_method: Optional[
            Literal["randomize", "loop", "single_scenario", "ordered"]
        ] = None,
        human_survey_name: str = "New survey",
        survey_description: Optional[str] = None,
        survey_alias: Optional[str] = None,
        survey_visibility: Optional[VisibilityType] = "private",
        scenario_list_description: Optional[str] = None,
        scenario_list_alias: Optional[str] = None,
        scenario_list_visibility: Optional[VisibilityType] = "private",
    ):
        """
        Create a human survey on Coop, first creating the survey and scenario list (if scenarios are used).
        """
        if scenario_list is None and scenario_list_method is not None:
            raise CoopValueError(
                "You must specify both a scenario list and a scenario list method to use scenarios with your survey."
            )
        elif scenario_list is not None and scenario_list_method is None:
            raise CoopValueError(
                "You must specify both a scenario list and a scenario list method to use scenarios with your survey."
            )
        survey_details = self.push(
            object=survey,
            description=survey_description,
            alias=survey_alias,
            visibility=survey_visibility,
        )
        survey_uuid = survey_details.get("uuid")
        if scenario_list is not None:
            scenario_list_details = self.push(
                object=scenario_list,
                description=scenario_list_description,
                alias=scenario_list_alias,
                visibility=scenario_list_visibility,
            )
            scenario_list_uuid = scenario_list_details.get("uuid")
        else:
            scenario_list_uuid = None
        response = self._send_server_request(
            uri="api/v0/human-surveys",
            method="POST",
            payload={
                "human_survey_name": human_survey_name,
                "survey_uuid": str(survey_uuid),
                "scenario_list_uuid": (
                    str(scenario_list_uuid) if scenario_list_uuid is not None else None
                ),
                "scenario_list_method": scenario_list_method,
            },
        )
        self._resolve_server_response(response)
        response_json = response.json()
        return {
            "name": response_json.get("name"),
            "uuid": response_json.get("uuid"),
            "admin_url": f"{self.url}/home/human-surveys/{response_json.get('uuid')}",
            "respondent_url": f"{self.url}/respond/human-surveys/{response_json.get('uuid')}",
            "n_responses": response_json.get("n_responses"),
            "survey_uuid": response_json.get("survey_uuid"),
            "scenario_list_uuid": response_json.get("scenario_list_uuid"),
        }

    def get_human_survey(
        self,
        human_survey_uuid: str,
    ) -> dict:
        """
        Get a human survey from Coop.
        """
        response = self._send_server_request(
            uri=f"api/v0/human-surveys/{human_survey_uuid}",
            method="GET",
        )
        self._resolve_server_response(response)
        response_json = response.json()
        return {
            "name": response_json.get("name"),
            "uuid": response_json.get("uuid"),
            "admin_url": f"{self.url}/home/human-surveys/{response_json.get('uuid')}",
            "respondent_url": f"{self.url}/respond/human-surveys/{response_json.get('uuid')}",
            "n_responses": response_json.get("n_responses"),
            "survey_uuid": response_json.get("survey_uuid"),
            "scenario_list_uuid": response_json.get("scenario_list_uuid"),
        }

    def _turn_human_responses_into_results(
        self,
        human_responses: List[dict],
        survey_uuid: str,
    ) -> Union["Results", "ScenarioList"]:
        """
        Turn a list of human responses into a Results object.

        If generating the Results object fails, a ScenarioList will be returned instead.
        """
        from ..agents import Agent
        from ..caching import Cache
        from ..language_models import Model
        from ..scenarios import Scenario, ScenarioList
        from ..surveys import Survey

        try:
            survey = Survey.pull(survey_uuid)

            model = Model("test")

            results = None

            for response in human_responses:
                response_uuid = response.get("response_uuid")
                if response_uuid is None:
                    raise RuntimeError(
                        "One of your responses is missing a unique identifier."
                    )

                response_dict = json.loads(response.get("response_json_string"))
                agent_traits_json_string = response.get("agent_traits_json_string")
                scenario_json_string = response.get("scenario_json_string")
                if agent_traits_json_string is not None:
                    agent_traits = json.loads(agent_traits_json_string)
                else:
                    agent_traits = {}

                a = Agent(name=response_uuid, instruction="", traits=agent_traits)

                def create_answer_function(response_data):
                    def f(self, question, scenario):
                        return response_data.get(question.question_name, None)

                    return f

                scenario = None
                if scenario_json_string is not None:
                    scenario = Scenario.from_dict(json.loads(scenario_json_string))

                a.add_direct_question_answering_method(
                    create_answer_function(response_dict)
                )

                job = survey.by(a).by(model)

                if scenario is not None:
                    job = job.by(scenario)

                question_results = job.run(
                    cache=Cache(),
                    disable_remote_cache=True,
                    disable_remote_inference=True,
                    print_exceptions=False,
                )

                if results is None:
                    results = question_results
                else:
                    results = results + question_results
            return results
        except Exception:
            human_response_scenarios = []
            for response in human_responses:
                response_uuid = response.get("response_uuid")
                if response_uuid is None:
                    raise RuntimeError(
                        "One of your responses is missing a unique identifier."
                    )

                response_dict = json.loads(response.get("response_json_string"))
                response_dict["agent_name"] = response_uuid
                scenario = Scenario(response_dict)
                human_response_scenarios.append(scenario)
            return ScenarioList(human_response_scenarios)

    def get_human_survey_responses(
        self,
        human_survey_uuid: str,
    ) -> Union["Results", "ScenarioList"]:
        """
        Return a Results object with the responses for a human survey.

        If generating the Results object fails, a ScenarioList will be returned instead.
        """
        response = self._send_server_request(
            uri=f"api/v0/human-surveys/{human_survey_uuid}/responses",
            method="GET",
        )
        self._resolve_server_response(response)
        response_json = response.json()
        responses = response_json.get("responses", [])
        survey_uuid = response_json.get("survey_uuid")

        return self._turn_human_responses_into_results(responses, survey_uuid)

    def test_scenario_sampling(self, human_survey_uuid: str) -> List[int]:
        """
        Get a sample for a human survey.
        """
        response = self._send_server_request(
            uri=f"api/v0/human-surveys/{human_survey_uuid}/scenario-sampling/test",
            method="GET",
        )
        self._resolve_server_response(response)
        response_json = response.json()
        scenario_indices = response_json.get("scenario_indices")
        return scenario_indices

    def reset_scenario_sampling_state(self, human_survey_uuid: str) -> dict:
        """
        Reset the scenario sampling state for a human survey.

        This is useful if you have scenario_list_method="ordered" and you want to
        start over with the first scenario in the list.
        """
        response = self._send_server_request(
            uri=f"api/v0/human-surveys/{human_survey_uuid}/scenario-sampling/reset",
            method="POST",
        )
        self._resolve_server_response(response)
        response_json = response.json()
        return response_json

    def list_prolific_filters(self) -> "CoopProlificFilters":
        """
        Get a ScenarioList of supported Prolific filters. This list has several methods
        that you can use to create valid filter dicts for use with Coop.create_prolific_study().

        Call find() to examine a specific filter by ID:
        >>> filters = coop.list_prolific_filters()
        >>> filters.find("age")
        Scenario(
            {
                "filter_id": "age",
                "type": "range",
                "range_filter_min": 18,
                "range_filter_max": 100,
                ...
            }
        )

        Call create_study_filter() to create a valid filter dict:
        >>> filters.create_study_filter("age", min=30, max=40)
        {
            "filter_id": "age",
            "selected_range": {
                "lower": 30,
                "upper": 40,
            },
        }
        """
        from ..scenarios import Scenario

        response = self._send_server_request(
            uri="api/v0/prolific-filters",
            method="GET",
        )
        self._resolve_server_response(response)
        response_json = response.json()
        filters = response_json.get("prolific_filters", [])
        filter_scenarios = []
        for filter in filters:
            filter_type = filter.get("type")
            question = filter.get("question")
            scenario = Scenario(
                {
                    "filter_id": filter.get("filter_id"),
                    "title": filter.get("title"),
                    "question": (
                        f"Participants were asked the following: {question}"
                        if question
                        else None
                    ),
                    "type": filter_type,
                    "range_filter_min": (
                        filter.get("min") if filter_type == "range" else None
                    ),
                    "range_filter_max": (
                        filter.get("max") if filter_type == "range" else None
                    ),
                    "select_filter_num_options": (
                        len(filter.get("choices", []))
                        if filter_type == "select"
                        else None
                    ),
                    "select_filter_options": (
                        filter.get("choices") if filter_type == "select" else None
                    ),
                }
            )
            filter_scenarios.append(scenario)
        return CoopProlificFilters(filter_scenarios)

    @staticmethod
    def _validate_prolific_study_cost(
        estimated_completion_time_minutes: int, participant_payment_cents: int
    ) -> tuple[bool, float]:
        """
        If the cost of a Prolific study is below the threshold, return True.
        Otherwise, return False.
        The second value in the tuple is the cost of the study in USD per hour.
        """
        estimated_completion_time_hours = estimated_completion_time_minutes / 60
        participant_payment_usd = participant_payment_cents / 100
        cost_usd_per_hour = participant_payment_usd / estimated_completion_time_hours

        # $8.00 USD per hour is the minimum amount for using Prolific
        if cost_usd_per_hour < 8:
            return True, cost_usd_per_hour
        else:
            return False, cost_usd_per_hour

    def create_prolific_study(
        self,
        human_survey_uuid: str,
        name: str,
        description: str,
        num_participants: int,
        estimated_completion_time_minutes: int,
        participant_payment_cents: int,
        device_compatibility: Optional[
            List[Literal["desktop", "tablet", "mobile"]]
        ] = None,
        peripheral_requirements: Optional[
            List[Literal["audio", "camera", "download", "microphone"]]
        ] = None,
        filters: Optional[List[Dict]] = None,
    ) -> dict:
        """
        Create a Prolific study for a human survey. Returns a dict with the study details.

        To add filters to your study, you should first pull the list of supported
        filters using Coop.list_prolific_filters().
        Then, you can use the create_study_filter method of the returned
        CoopProlificFilters object to create a valid filter dict.
        """
        is_underpayment, cost_usd_per_hour = self._validate_prolific_study_cost(
            estimated_completion_time_minutes, participant_payment_cents
        )
        if is_underpayment:
            raise CoopValueError(
                f"The current participant payment of ${cost_usd_per_hour:.2f} USD per hour is below the minimum payment for using Prolific ($8.00 USD per hour)."
            )

        response = self._send_server_request(
            uri=f"api/v0/human-surveys/{human_survey_uuid}/prolific-studies",
            method="POST",
            payload={
                "name": name,
                "description": description,
                "total_available_places": num_participants,
                "estimated_completion_time": estimated_completion_time_minutes,
                "reward": participant_payment_cents,
                "device_compatibility": (
                    ["desktop", "tablet", "mobile"]
                    if device_compatibility is None
                    else device_compatibility
                ),
                "peripheral_requirements": (
                    [] if peripheral_requirements is None else peripheral_requirements
                ),
                "filters": [] if filters is None else filters,
            },
        )
        self._resolve_server_response(response)
        response_json = response.json()
        return {
            "study_id": response_json.get("study_id"),
            "status": response_json.get("status"),
            "admin_url": response_json.get("admin_url"),
            "respondent_url": response_json.get("respondent_url"),
            "name": response_json.get("name"),
            "description": response_json.get("description"),
            "num_participants": response_json.get("total_available_places"),
            "estimated_completion_time_minutes": response_json.get(
                "estimated_completion_time"
            ),
            "participant_payment_cents": response_json.get("reward"),
            "total_cost_cents": response_json.get("total_cost"),
            "device_compatibility": response_json.get("device_compatibility"),
            "peripheral_requirements": response_json.get("peripheral_requirements"),
            "filters": response_json.get("filters"),
        }

    def update_prolific_study(
        self,
        human_survey_uuid: str,
        study_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        num_participants: Optional[int] = None,
        estimated_completion_time_minutes: Optional[int] = None,
        participant_payment_cents: Optional[int] = None,
        device_compatibility: Optional[
            List[Literal["desktop", "tablet", "mobile"]]
        ] = None,
        peripheral_requirements: Optional[
            List[Literal["audio", "camera", "download", "microphone"]]
        ] = None,
        filters: Optional[List[Dict]] = None,
    ) -> dict:
        """
        Update a Prolific study. Returns a dict with the study details.
        """
        study = self.get_prolific_study(human_survey_uuid, study_id)

        current_completion_time = study.get("estimated_completion_time_minutes")
        current_payment = study.get("participant_payment_cents")

        updated_completion_time = (
            estimated_completion_time_minutes or current_completion_time
        )
        updated_payment = participant_payment_cents or current_payment

        is_underpayment, cost_usd_per_hour = self._validate_prolific_study_cost(
            updated_completion_time, updated_payment
        )
        if is_underpayment:
            raise CoopValueError(
                f"This update would result in a participant payment of ${cost_usd_per_hour:.2f} USD per hour, which is below the minimum payment for using Prolific ($8.00 USD per hour)."
            )

        payload = {}
        if name is not None:
            payload["name"] = name
        if description is not None:
            payload["description"] = description
        if num_participants is not None:
            payload["total_available_places"] = num_participants
        if estimated_completion_time_minutes is not None:
            payload["estimated_completion_time"] = estimated_completion_time_minutes
        if participant_payment_cents is not None:
            payload["reward"] = participant_payment_cents
        if device_compatibility is not None:
            payload["device_compatibility"] = device_compatibility
        if peripheral_requirements is not None:
            payload["peripheral_requirements"] = peripheral_requirements
        if filters is not None:
            payload["filters"] = filters

        response = self._send_server_request(
            uri=f"api/v0/human-surveys/{human_survey_uuid}/prolific-studies/{study_id}",
            method="PATCH",
            payload=payload,
        )
        self._resolve_server_response(response)
        response_json = response.json()
        return {
            "study_id": response_json.get("study_id"),
            "status": response_json.get("status"),
            "admin_url": response_json.get("admin_url"),
            "respondent_url": response_json.get("respondent_url"),
            "name": response_json.get("name"),
            "description": response_json.get("description"),
            "num_participants": response_json.get("total_available_places"),
            "estimated_completion_time_minutes": response_json.get(
                "estimated_completion_time"
            ),
            "participant_payment_cents": response_json.get("reward"),
            "total_cost_cents": response_json.get("total_cost"),
            "device_compatibility": response_json.get("device_compatibility"),
            "peripheral_requirements": response_json.get("peripheral_requirements"),
            "filters": response_json.get("filters"),
        }

    def publish_prolific_study(
        self,
        human_survey_uuid: str,
        study_id: str,
    ) -> dict:
        """
        Publish a Prolific study.

        Once your study is published, Prolific participants can start accepting and completing it.
        """
        response = self._send_server_request(
            uri=f"api/v0/human-surveys/{human_survey_uuid}/prolific-studies/{study_id}/status",
            method="POST",
            payload={
                "action": "PUBLISH",
            },
        )
        self._resolve_server_response(response)
        return response.json()

    def pause_prolific_study(
        self,
        human_survey_uuid: str,
        study_id: str,
    ) -> dict:
        """
        Pause a Prolific study.

        Pausing a study will temporarily stop new participants from joining.
        Participants who have already started the study can still complete it.
        You can resume the study later by calling Coop.resume_prolific_study().
        """
        response = self._send_server_request(
            uri=f"api/v0/human-surveys/{human_survey_uuid}/prolific-studies/{study_id}/status",
            method="POST",
            payload={
                "action": "PAUSE",
            },
        )
        self._resolve_server_response(response)
        return response.json()

    def resume_prolific_study(
        self,
        human_survey_uuid: str,
        study_id: str,
    ) -> dict:
        """
        Resume a paused Prolific study.

        Resuming a study will make it available to participants again.
        New participants will be able to join and complete your study.
        """
        response = self._send_server_request(
            uri=f"api/v0/human-surveys/{human_survey_uuid}/prolific-studies/{study_id}/status",
            method="POST",
            payload={
                "action": "START",
            },
        )
        self._resolve_server_response(response)
        return response.json()

    def stop_prolific_study(
        self,
        human_survey_uuid: str,
        study_id: str,
    ) -> dict:
        """
        Stop a Prolific study.

        Stopping a study will permanently end it.
        No new participants will be able to join, and the study cannot be resumed.
        """
        response = self._send_server_request(
            uri=f"api/v0/human-surveys/{human_survey_uuid}/prolific-studies/{study_id}/status",
            method="POST",
            payload={
                "action": "STOP",
            },
        )
        self._resolve_server_response(response)
        return response.json()

    def get_prolific_study(self, human_survey_uuid: str, study_id: str) -> dict:
        """
        Get a Prolific study. Returns a dict with the study details.
        """
        response = self._send_server_request(
            uri=f"api/v0/human-surveys/{human_survey_uuid}/prolific-studies/{study_id}",
            method="GET",
        )
        self._resolve_server_response(response)
        response_json = response.json()
        return {
            "study_id": response_json.get("study_id"),
            "status": response_json.get("status"),
            "admin_url": response_json.get("admin_url"),
            "respondent_url": response_json.get("respondent_url"),
            "name": response_json.get("name"),
            "description": response_json.get("description"),
            "num_participants": response_json.get("total_available_places"),
            "estimated_completion_time_minutes": response_json.get(
                "estimated_completion_time"
            ),
            "participant_payment_cents": response_json.get("reward"),
            "total_cost_cents": response_json.get("total_cost"),
            "device_compatibility": response_json.get("device_compatibility"),
            "peripheral_requirements": response_json.get("peripheral_requirements"),
            "filters": response_json.get("filters"),
        }

    def get_prolific_study_responses(
        self,
        human_survey_uuid: str,
        study_id: str,
    ) -> Union["Results", "ScenarioList"]:
        """
        Return a Results object with the human responses for a human survey.

        If generating the Results object fails, a ScenarioList will be returned instead.
        """
        response = self._send_server_request(
            uri=f"api/v0/human-surveys/{human_survey_uuid}/prolific-studies/{study_id}/responses",
            method="GET",
        )
        self._resolve_server_response(response)
        response_json = response.json()
        human_responses = response_json.get("human_responses", [])
        survey_uuid = response_json.get("survey_uuid")

        return self._turn_human_responses_into_results(human_responses, survey_uuid)

    def delete_prolific_study(
        self,
        human_survey_uuid: str,
        study_id: str,
    ) -> dict:
        """
        Deletes a Prolific study.

        Note: Only draft studies can be deleted. Once you publish a study, it cannot be deleted.
        """
        response = self._send_server_request(
            uri=f"api/v0/human-surveys/{human_survey_uuid}/prolific-studies/{study_id}",
            method="DELETE",
        )
        self._resolve_server_response(response)
        return response.json()

    def approve_prolific_study_submission(
        self,
        human_survey_uuid: str,
        study_id: str,
        submission_id: str,
    ) -> dict:
        """
        Approve a Prolific study submission.
        """
        response = self._send_server_request(
            uri=f"api/v0/human-surveys/{human_survey_uuid}/prolific-studies/{study_id}/submissions/{submission_id}/approve",
            method="POST",
        )
        self._resolve_server_response(response)
        return response.json()

    def reject_prolific_study_submission(
        self,
        human_survey_uuid: str,
        study_id: str,
        submission_id: str,
        reason: Literal[
            "TOO_QUICKLY",
            "TOO_SLOWLY",
            "FAILED_INSTRUCTIONS",
            "INCOMP_LONGITUDINAL",
            "FAILED_CHECK",
            "LOW_EFFORT",
            "MALINGERING",
            "NO_CODE",
            "BAD_CODE",
            "NO_DATA",
            "UNSUPP_DEVICE",
            "OTHER",
        ],
        explanation: str,
    ) -> dict:
        """
        Reject a Prolific study submission.
        """
        valid_rejection_reasons = [
            "TOO_QUICKLY",
            "TOO_SLOWLY",
            "FAILED_INSTRUCTIONS",
            "INCOMP_LONGITUDINAL",
            "FAILED_CHECK",
            "LOW_EFFORT",
            "MALINGERING",
            "NO_CODE",
            "BAD_CODE",
            "NO_DATA",
            "UNSUPP_DEVICE",
            "OTHER",
        ]
        if reason not in valid_rejection_reasons:
            raise CoopValueError(
                f"Invalid rejection reason. Please use one of the following: {valid_rejection_reasons}."
            )
        if len(explanation) < 100:
            raise CoopValueError(
                "Rejection explanation must be at least 100 characters."
            )
        response = self._send_server_request(
            uri=f"api/v0/human-surveys/{human_survey_uuid}/prolific-studies/{study_id}/submissions/{submission_id}/reject",
            method="POST",
            payload={
                "reason": reason,
                "explanation": explanation,
            },
        )
        self._resolve_server_response(response)
        return response.json()

    def __repr__(self):
        """Return a string representation of the client."""
        return f"Client(api_key='{self.api_key}', url='{self.url}')"

    async def remote_async_execute_model_call(
        self, model_dict: dict, user_prompt: str, system_prompt: str
    ) -> dict:
        url = self.api_url + "/inference/"
        # print("Now using url: ", url)
        data = {
            "model_dict": model_dict,
            "user_prompt": user_prompt,
            "system_prompt": system_prompt,
        }
        # Use aiohttp to send a POST request asynchronously
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                response_data = await response.json()
        return response_data

    def web(
        self,
        survey: dict,
        platform: Literal[
            "google_forms", "lime_survey", "survey_monkey"
        ] = "lime_survey",
        email=None,
    ):
        url = f"{self.api_url}/api/v0/export_to_{platform}"
        if email:
            data = {"json_string": json.dumps({"survey": survey, "email": email})}
        else:
            data = {"json_string": json.dumps({"survey": survey, "email": ""})}

        response_json = requests.post(url, headers=self.headers, data=json.dumps(data))

        return response_json

    def fetch_prices(self) -> dict:
        """
        Fetch the current pricing information for language models.

        This method retrieves the latest pricing information for all supported language models
        from the Expected Parrot API. The pricing data is used to estimate costs for jobs
        and to optimize model selection based on budget constraints.

        Returns:
            dict: A dictionary mapping (service, model) tuples to pricing information.
                Each entry contains token pricing for input and output tokens.
                Example structure:
                {
                    ('openai', 'gpt-4'): {
                        'input': {'usd_per_1M_tokens': 30.0, ...},
                        'output': {'usd_per_1M_tokens': 60.0, ...}
                    }
                }

        Raises:
            ValueError: If the EDSL_FETCH_TOKEN_PRICES configuration setting is invalid

        Notes:
            - Returns an empty dict if EDSL_FETCH_TOKEN_PRICES is set to "False"
            - The pricing data is cached to minimize API calls
            - Pricing may vary based on the model, provider, and token type (input/output)
            - All prices are in USD per million tokens

        Example:
            >>> prices = coop.fetch_prices()
            >>> gpt4_price = prices.get(('openai', 'gpt-4'), {})
            >>> print(f"GPT-4 input price: ${gpt4_price.get('input', {}).get('usd_per_1M_tokens')}")
        """
        from .price_fetcher import PriceFetcher
        from ..config import CONFIG

        if CONFIG.get("EDSL_FETCH_TOKEN_PRICES") == "True":
            price_fetcher = PriceFetcher()
            return price_fetcher.fetch_prices()
        elif CONFIG.get("EDSL_FETCH_TOKEN_PRICES") == "False":
            return {}
        else:
            from .exceptions import CoopValueError

            raise CoopValueError(
                "Invalid EDSL_FETCH_TOKEN_PRICES value---should be 'True' or 'False'."
            )

    def fetch_models(self) -> Dict[str, List[str]]:
        """
        Fetch information about available language models from Expected Parrot.

        This method retrieves the current list of available language models grouped
        by service provider (e.g., OpenAI, Anthropic, etc.). This information is
        useful for programmatically selecting models based on availability and
        for ensuring that jobs only use supported models.

        Returns:
            ServiceToModelsMapping: A mapping of service providers to their available models.
                Example structure:
                {
                    "openai": ["gpt-4", "gpt-3.5-turbo", ...],
                    "anthropic": ["claude-3-opus", "claude-3-sonnet", ...],
                    ...
                }

        Raises:
            CoopServerResponseError: If there's an error communicating with the server

        Notes:
            - The availability of models may change over time
            - Not all models may be accessible with your current API keys
            - Use this method to check for model availability before creating jobs
            - Models may have different capabilities (text-only, multimodal, etc.)

        Example:
            >>> models = coop.fetch_models()
            >>> if "gpt-4" in models.get("openai", []):
            ...     print("GPT-4 is available")
            >>> available_services = list(models.keys())
            >>> print(f"Available services: {available_services}")
        """
        response = self._send_server_request(uri="api/v0/models", method="GET")
        self._resolve_server_response(response)
        data = response.json()
        # return ServiceToModelsMapping(data)
        return data

    def fetch_working_models(self) -> List[dict]:
        """
        Fetch a list of working models from Coop.

        Example output:

        [
            {
                "service": "openai",
                "model": "gpt-4o",
                "works_with_text": True,
                "works_with_images": True,
                "usd_per_1M_input_tokens": 2.5,
                "usd_per_1M_output_tokens": 10.0,
            }
        ]
        """
        response = self._send_server_request(uri="api/v0/working-models", method="GET")
        self._resolve_server_response(response)
        data = response.json()
        return [
            {
                "service": record.get("service"),
                "model": record.get("model"),
                "works_with_text": record.get("works_with_text"),
                "works_with_images": record.get("works_with_images"),
                "usd_per_1M_input_tokens": record.get("input_price_per_1M_tokens"),
                "usd_per_1M_output_tokens": record.get("output_price_per_1M_tokens"),
            }
            for record in data
        ]

    def fetch_rate_limit_config_vars(self) -> dict:
        """
        Fetch a dict of rate limit config vars from Coop.

        The dict keys are RPM and TPM variables like EDSL_SERVICE_RPM_OPENAI.
        """
        response = self._send_server_request(
            uri="api/v0/config-vars",
            method="GET",
        )
        self._resolve_server_response(response)
        data = response.json()
        return data

    def get_uuid_from_hash(self, hash_value: str) -> str:
        """
        Retrieve the UUID for an object based on its hash.

        This method calls the remote endpoint to get the UUID associated with an object hash.

        Args:
            hash_value (str): The hash value of the object to look up

        Returns:
            str: The UUID of the object if found

        Raises:
            CoopServerResponseError: If the object is not found or there's an error
                                   communicating with the server
        """
        response = self._send_server_request(
            uri=f"api/v0/object/hash/{hash_value}", method="GET"
        )
        self._resolve_server_response(response)
        return response.json().get("uuid")

    def pull(
        self,
        url_or_uuid: Optional[Union[str, UUID]] = None,
        expected_object_type: Optional[ObjectType] = None,
    ) -> dict:
        """
        Generate a signed URL for pulling an object directly from Google Cloud Storage.

        This method gets a signed URL that allows direct download access to the object from
        Google Cloud Storage, which is more efficient for large files.

        Parameters:
            url_or_uuid (Union[str, UUID], optional): Identifier for the object to retrieve.
                Can be one of:
                - UUID string (e.g., "123e4567-e89b-12d3-a456-426614174000")
                - Full URL (e.g., "https://expectedparrot.com/content/123e4567...")
                - Alias URL (e.g., "https://expectedparrot.com/content/username/my-survey")
            expected_object_type (ObjectType, optional): If provided, validates that the
                retrieved object is of the expected type (e.g., "survey", "agent")

        Returns:
            dict: A response containing the signed_url for direct download

        Raises:
            CoopNoUUIDError: If no UUID or URL is provided
            CoopInvalidURLError: If the URL format is invalid
            CoopServerResponseError: If there's an error communicating with the server
            HTTPException: If the object or object files are not found

        Example:
            >>> response = coop.pull("123e4567-e89b-12d3-a456-426614174000")
            >>> response = coop.pull("https://expectedparrot.com/content/username/my-survey")
            >>> print(f"Download URL: {response['signed_url']}")
            >>> # Use the signed_url to download the object directly
        """
        obj_uuid, owner_username, alias = self._resolve_uuid_or_alias(url_or_uuid)

        # Handle alias-based retrieval with new/old format detection
        if not obj_uuid and owner_username and alias:
            # First, get object info to determine format and UUID
            info_response = self._send_server_request(
                uri="api/v0/object/alias/info",
                method="GET",
                params={"owner_username": owner_username, "alias": alias},
            )
            self._resolve_server_response(info_response)
            info_data = info_response.json()

            obj_uuid = info_data.get("uuid")
            is_new_format = info_data.get("is_new_format", False)

            # Validate object type if expected
            if expected_object_type:
                actual_object_type = info_data.get("object_type")
                if actual_object_type != expected_object_type:
                    from .exceptions import CoopObjectTypeError

                    raise CoopObjectTypeError(
                        f"Expected {expected_object_type=} but got {actual_object_type=}"
                    )

            # Use get method for old format objects
            if not is_new_format:
                return self.get(url_or_uuid, expected_object_type)

        # Send the request to the API endpoint with the resolved UUID
        response = self._send_server_request(
            uri="api/v0/object/pull",
            method="POST",
            payload={"object_uuid": obj_uuid},
        )
        # Handle any errors in the response
        self._resolve_server_response(response)
        if "signed_url" not in response.json():
            from .exceptions import CoopResponseError

            raise CoopResponseError("No signed url was provided.")
        signed_url = response.json().get("signed_url")

        if signed_url == "":  # it is in old format
            return self.get(url_or_uuid, expected_object_type)

        try:
            response = requests.get(signed_url)

            self._resolve_gcs_response(response)

        except Exception:
            return self.get(url_or_uuid, expected_object_type)

        object_dict = response.json()
        if expected_object_type is not None:
            edsl_class = ObjectRegistry.get_edsl_class_by_object_type(
                expected_object_type
            )
            edsl_object = edsl_class.from_dict(object_dict)
            return edsl_object
        else:
            likely_object_type = object_dict.get("edsl_class_name")
            if likely_object_type is not None:
                edsl_class = ObjectRegistry.get_registry().get(likely_object_type, None)
                return edsl_class.from_dict(object_dict)
            else:
                for edsl_class in ObjectRegistry.get_registry().values():
                    try:
                        edsl_object = edsl_class.from_dict(object_dict)
                        return edsl_object
                        break
                    except Exception:
                        continue

        raise CoopResponseError(f"No EDSL class found for {likely_object_type=}")

    def get_upload_url(self, object_uuid: str) -> dict:
        """
        Get a signed upload URL for updating the content of an existing object.

        This method gets a signed URL that allows direct upload to Google Cloud Storage
        for objects stored in the new format, while preserving the existing UUID.

        Parameters:
            object_uuid (str): The UUID of the object to get an upload URL for

        Returns:
            dict: A response containing:
                - signed_url: The signed URL for uploading new content
                - object_uuid: The UUID of the object
                - message: Success message

        Raises:
            CoopServerResponseError: If there's an error communicating with the server
            HTTPException: If the object is not found, not owned by user, or not in new format

        Notes:
            - Only works with objects stored in the new format (transition table)
            - User must be the owner of the object
            - The signed URL expires after 60 minutes

        Example:
            >>> response = coop.get_upload_url("123e4567-e89b-12d3-a456-426614174000")
            >>> upload_url = response['signed_url']
            >>> # Use the upload_url to PUT new content directly to GCS
        """
        response = self._send_server_request(
            uri="api/v0/object/upload-url",
            method="POST",
            payload={"object_uuid": object_uuid},
        )
        self._resolve_server_response(response)
        return response.json()

    def _process_filestores_for_push(
        self, object_dict: dict, original_object=None
    ) -> dict:
        """
        Detect FileStore objects in the serialized object, upload them to GCS,
        and offload them by replacing base64_string with "offloaded" marker.

        This method:
        1. Recursively searches for FileStore objects in the object_dict
        2. For each FileStore, requests upload URL from backend
        3. Uploads file content to GCS
        4. Adds file_uuid to external_locations["gcs"]
        5. Replaces base64_string with "offloaded"
        6. Updates the original FileStore objects in the original_object

        Args:
            object_dict: The serialized object dictionary
            original_object: The original EDSLObject (optional, for updating FileStores)

        Returns:
            dict: The modified object_dict with offloaded FileStores
        """
        import base64
        from copy import deepcopy

        # Create a deep copy to avoid modifying the original dict structure
        modified_dict = deepcopy(object_dict)

        def process_dict_recursive(d: dict, path: str = ""):
            """Recursively process dictionaries looking for FileStore objects."""
            if self._scenario_is_file_store(d):
                # This is a FileStore object
                base64_string = d.get("base64_string", "")

                # Skip if already offloaded
                if base64_string == "offloaded":
                    return d

                # Skip if no content to upload
                if not base64_string or not isinstance(base64_string, str):
                    return d

                # Get FileStore metadata
                file_name = d.get("path", "unknown")
                mime_type = d.get("mime_type", "application/octet-stream")
                suffix = d.get("suffix", "bin")

                # Request upload URL from backend
                try:
                    response = self._send_server_request(
                        uri="api/v0/filestore/upload-url",
                        method="POST",
                        payload={
                            "file_name": file_name,
                            "mime_type": mime_type,
                            "suffix": suffix,
                        },
                    )
                    response_data = response.json()
                    file_uuid = response_data.get("file_uuid")
                    upload_url = response_data.get("upload_url")

                    if not file_uuid or not upload_url:
                        # If backend didn't return proper response, skip upload
                        return d

                    # Decode base64 content
                    file_content = base64.b64decode(base64_string)

                    # Upload to GCS
                    upload_response = requests.put(
                        upload_url,
                        data=file_content,
                        headers={
                            "Content-Type": mime_type,
                            "Content-Length": str(len(file_content)),
                        },
                    )

                    # Check if upload was successful
                    if upload_response.status_code in (200, 201):
                        # Upload successful, offload the FileStore
                        d["base64_string"] = "offloaded"

                        # Add file_uuid to external_locations
                        if "external_locations" not in d:
                            d["external_locations"] = {}

                        d["external_locations"]["gcs"] = {
                            "file_uuid": file_uuid,
                            "uploaded": True,
                            "offloaded": True,
                        }

                        # Also update the original FileStore object if we have access to it
                        if original_object is not None and path:
                            try:
                                # Navigate to the FileStore in the original object
                                from ..scenarios.file_store import FileStore

                                # Clean up the path: remove leading dots and split
                                clean_path = path.lstrip(".")
                                keys = (
                                    clean_path.split(".")
                                    if "." in clean_path
                                    else [clean_path]
                                )
                                # Filter out empty strings that might result from splitting
                                keys = [k for k in keys if k]
                                current_obj = original_object

                                # For list-like objects (ScenarioList, AgentList), the first key in the path
                                # might be the serialization wrapper (e.g., 'scenarios', 'agents')
                                # which doesn't exist as an attribute on the object itself.
                                # We need to transform 'scenarios[0]' to just '[0]' for list-like objects.
                                if keys and "[" in keys[0]:
                                    first_key_name = keys[0].split("[")[0]
                                    if (
                                        first_key_name
                                        and hasattr(original_object, "__iter__")
                                        and not hasattr(original_object, first_key_name)
                                    ):
                                        # Remove the key name but keep the bracket part
                                        # e.g., 'scenarios[0]' becomes '[0]'
                                        bracket_part = "[" + keys[0].split("[", 1)[1]
                                        keys[0] = bracket_part

                                # Navigate through nested structures
                                for key in keys:
                                    if (
                                        "[" in key
                                    ):  # Handle bracket-style list indexing: "items[0]"
                                        key_name, idx = key.split("[")
                                        idx = int(idx.rstrip("]"))
                                        # Handle empty key_name (means root object is a list)
                                        if key_name:
                                            current_obj = current_obj[key_name][idx]
                                        else:
                                            current_obj = current_obj[idx]
                                    elif (
                                        key.isdigit()
                                    ):  # Handle numeric string keys for list access: "0", "1", etc.
                                        # Convert string index to integer for list-like objects
                                        current_obj = current_obj[int(key)]
                                    else:
                                        # Regular dictionary-style key access
                                        current_obj = current_obj[key]

                                # Update the FileStore object directly
                                if isinstance(current_obj, FileStore):
                                    current_obj.base64_string = "offloaded"
                                    current_obj["base64_string"] = "offloaded"

                                    if "external_locations" not in current_obj:
                                        current_obj["external_locations"] = {}

                                    current_obj["external_locations"]["gcs"] = {
                                        "file_uuid": file_uuid,
                                        "uploaded": True,
                                        "offloaded": True,
                                    }
                                    current_obj.external_locations = current_obj[
                                        "external_locations"
                                    ]
                            except Exception as update_error:
                                # If we can't update the original object, that's okay
                                # The serialized dict is still correctly offloaded
                                print(
                                    f"Warning: Could not update original FileStore at path '{path}': {update_error}"
                                )
                    else:
                        # Upload failed, keep FileStore as-is with full base64
                        pass

                except Exception as e:
                    # If upload fails, keep the FileStore as-is (with full base64)
                    # This ensures backward compatibility
                    print(f"Warning: FileStore upload failed: {e}")

            else:
                # Not a FileStore, recursively process nested dicts
                for key, value in d.items():
                    if isinstance(value, dict):
                        d[key] = process_dict_recursive(
                            value, f"{path}.{key}" if path else key
                        )
                    elif isinstance(value, list):
                        d[key] = [
                            (
                                process_dict_recursive(item, f"{path}.{key}[{i}]")
                                if isinstance(item, dict)
                                else item
                            )
                            for i, item in enumerate(value)
                        ]

            return d

        return process_dict_recursive(modified_dict)

    def push(
        self,
        object: EDSLObject,
        description: Optional[str] = None,
        alias: Optional[str] = None,
        visibility: Optional[VisibilityType] = "private",
        force: bool = False,
    ) -> "Scenario":
        """
        Generate a signed URL for pushing an object directly to Google Cloud Storage.

        This method gets a signed URL that allows direct upload access to Google Cloud Storage,
        which is more efficient for large files.

        Parameters:
            object_type (ObjectType): The type of object to be uploaded

        Returns:
            dict: A response containing the signed_url for direct upload and optionally a job_id

        Raises:
            CoopServerResponseError: If there's an error communicating with the server

        Example:
            >>> response = coop.push("scenario")
            >>> print(f"Upload URL: {response['signed_url']}")
            >>> # Use the signed_url to upload the object directly
        """
        from ..scenarios import Scenario

        # Validate alias before attempting to push
        self._validate_alias(alias)

        object_type = ObjectRegistry.get_object_type_by_edsl_class(object)
        object_dict = object.to_dict()
        object_hash = object.get_hash() if hasattr(object, "get_hash") else None

        # Process FileStore objects: upload to GCS and offload
        object_dict = self._process_filestores_for_push(
            object_dict, original_object=object
        )

        # Send the request to the API endpoint
        response = self._send_server_request(
            uri="api/v0/object/push",
            method="POST",
            payload={
                "object_type": object_type,
                "description": description,
                "alias": alias,
                "visibility": visibility,
                "object_hash": object_hash,
                "version": self._edsl_version,
            },
        )
        response_json = response.json()
        if response_json.get("signed_url") is not None:
            signed_url = response_json.get("signed_url")
        else:
            from .exceptions import CoopResponseError

            url = f"{self.api_url}/api/v0/object/push"
            error_message = response.text

            # Check if this is an alias conflict error and force is enabled
            if (
                force
                and alias
                and "already have an object with the alias" in error_message
            ):
                # Get username to construct the alias URL
                profile = self.get_profile()
                username = profile["username"]

                # Construct the alias URL and use patch instead
                alias_url = f"{self.url}/content/{username}/{alias}"
                patch_result = self.patch(
                    url_or_uuid=alias_url,
                    description=description,
                    alias=alias,
                    value=object,
                    visibility=visibility,
                )

                # Get complete metadata after the patch
                metadata = self.get_metadata(alias_url)

                # Return in the same format as push
                return Scenario(
                    {
                        "description": metadata.get("description"),
                        "object_type": object_type,
                        "url": metadata.get("url"),
                        "alias_url": metadata.get("alias_url"),
                        "uuid": metadata.get("uuid"),
                        "version": self._edsl_version,
                        "visibility": metadata.get("visibility"),
                    }
                )

            raise CoopResponseError(f"Request to {url} failed: {error_message}")

        try:
            json_data = json.dumps(
                object_dict,
                default=self._json_handle_none,
                allow_nan=False,
            )
        except (ValueError, TypeError) as e:
            from .exceptions import CoopSerializationError
            import math

            # Find specific problematic values
            problems = self._find_problematic_floats(object_dict)

            if problems:
                # Create detailed error message with specific locations
                error_msg = f"Cannot serialize object to JSON due to {len(problems)} problematic float value(s):\n"
                for path, value in problems[
                    :10
                ]:  # Limit to first 10 to avoid overwhelming output
                    value_type = (
                        "inf"
                        if math.isinf(value)
                        else "nan" if math.isnan(value) else "invalid"
                    )
                    error_msg += f"  • {path}: {value} ({value_type})\n"

                if len(problems) > 10:
                    error_msg += (
                        f"  ... and {len(problems) - 10} more problematic values\n"
                    )

                error_msg += "\nTo fix this issue:\n"
                error_msg += "1. Replace NaN values with None or a default value\n"
                error_msg += (
                    "2. Replace inf/-inf values with large finite numbers or None\n"
                )
                error_msg += (
                    "3. Filter out rows/records with problematic values before pushing"
                )

                raise CoopSerializationError(error_msg) from e
            else:
                # Generic serialization error
                error_msg = f"Failed to serialize object to JSON: {str(e)}"
                if "not JSON serializable" in str(e):
                    error_msg += f"\nObject type: {type(object_dict)}"
                    error_msg += f"\nObject class: {object.__class__.__name__}"
                raise CoopSerializationError(error_msg) from e
        response = requests.put(
            signed_url,
            data=json_data.encode(),
            headers={"Content-Type": "application/json"},
        )
        self._resolve_gcs_response(response)

        # Send confirmation that upload was completed
        object_uuid = response_json.get("object_uuid", None)
        owner_username = response_json.get("owner_username", None)
        object_alias = response_json.get("alias", None)

        if object_uuid is None:
            from .exceptions import CoopResponseError

            raise CoopResponseError("No object uuid was provided received")

        # Confirm the upload completion
        confirm_response = self._send_server_request(
            uri="api/v0/object/confirm-upload",
            method="POST",
            payload={"object_uuid": object_uuid},
        )
        self._resolve_server_response(confirm_response)

        return Scenario(
            {
                "description": response_json.get("description"),
                "object_type": object_type,
                "url": f"{self.url}/content/{object_uuid}",
                "alias": object_alias,
                "alias_url": self._get_alias_url(owner_username, object_alias),
                "uuid": object_uuid,
                "version": self._edsl_version,
                "visibility": response_json.get("visibility"),
            }
        )

    def _display_login_url(
        self, edsl_auth_token: str, link_description: Optional[str] = None
    ):
        """
        Uses rich.print to display a login URL.

        - We need this function because URL detection with print() does not work alongside animations in VSCode.
        """
        from rich import print as rich_print
        from rich.console import Console

        console = Console()

        url = f"{CONFIG.EXPECTED_PARROT_URL}/login?edsl_auth_token={edsl_auth_token}"

        # Check if we're in marimo by checking sys.modules
        in_marimo = "marimo" in sys.modules
        mo = None
        if in_marimo:
            try:
                import marimo as mo
            except ImportError:
                in_marimo = False

        # Debug output
        print(
            f"DEBUG: in_marimo={in_marimo}, console.is_terminal={console.is_terminal}"
        )

        description = (
            link_description
            if link_description
            else "🔗 Use the link below to log in to Expected Parrot so we can automatically update your API key."
        )
        html_content = f"""
        <div style="margin: 15px 0; padding: 10px; border-left: 3px solid #38bdf8; background-color: #f8fafc;">
            <p style="margin: 0 0 10px 0; color: #334155;">{description}</p>
            <a href="{url}" target="_blank"
               style="color: #38bdf8; text-decoration: none; font-weight: 500; font-size: 14px;">
                🔗 Log in and automatically store key
            </a>
        </div>
        """

        if in_marimo and mo is not None:
            # marimo: use mo.callout with markdown link
            callout = mo.callout(
                mo.md(
                    f"""
{description}

[🔗 Log in and automatically store key]({url})
                """
                ),
                kind="info",
            )
            return callout
        elif console.is_terminal:
            # Running in a standard terminal, show the full URL
            if link_description:
                rich_print(
                    f"{link_description}\n[#38bdf8][link={url}]{url}[/link][/#38bdf8]"
                )
            else:
                rich_print(f"[#38bdf8][link={url}]{url}[/link][/#38bdf8]")
        else:
            # Running in an interactive environment (e.g., Jupyter Notebook)
            # Use IPython HTML display
            from IPython.display import HTML, display

            display(HTML(html_content))

        print("Logging in will activate the following features:")
        print("  - Remote inference: Runs jobs remotely on the Expected Parrot server.")
        print("  - Remote logging: Sends error messages to the Expected Parrot server.")
        print("\n")

    def _get_api_key(self, edsl_auth_token: str):
        """
        Given an EDSL auth token, find the corresponding user's API key.
        """

        response = self._send_server_request(
            uri="api/v0/get-api-key",
            method="POST",
            payload={
                "edsl_auth_token": edsl_auth_token,
            },
        )
        data = response.json()
        api_key = data.get("api_key")
        return api_key

    def login(self):
        """
        Starts the EDSL auth token login flow.
        """
        import secrets
        from dotenv import load_dotenv
        from ..utilities.utilities import write_api_key_to_env

        edsl_auth_token = secrets.token_urlsafe(16)

        html_obj = self._display_login_url(
            edsl_auth_token=edsl_auth_token,
            link_description="\n🔗 Use the link below to log in to Expected Parrot so we can automatically update your API key.",
        )

        # If in marimo, print the HTML object so it displays
        if html_obj is not None:
            print(html_obj)

        api_key = self._poll_for_api_key(edsl_auth_token)

        if api_key is None:
            from .exceptions import CoopTimeoutError

            raise CoopTimeoutError("Timed out waiting for login. Please try again.")

        path_to_env = write_api_key_to_env(api_key)
        print("\n✨ API key retrieved and written to .env file at the following path:")
        print(f"    {path_to_env}")

        # Add API key to environment
        load_dotenv()

    def login_streamlit(self, timeout: int = 120):
        """
        Start the EDSL auth token login flow inside a Streamlit application.

        This helper is functionally equivalent to ``Coop.login`` but renders the
        login link and status updates directly in the Streamlit UI.  The method
        will automatically poll the Expected Parrot server for the API-key
        associated with the generated auth-token and, once received, store it
        via ``ExpectedParrotKeyHandler`` and write it to the local ``.env``
        file so subsequent sessions pick it up automatically.

        Parameters
        ----------
        timeout : int, default 120
            How many seconds to wait for the user to complete the login before
            giving up and showing an error in the Streamlit app.

        Returns
        -------
        str | None
            The API-key if the user logged-in successfully, otherwise ``None``.
        """
        try:
            import streamlit as st
            from streamlit.runtime.scriptrunner import get_script_run_ctx
        except ModuleNotFoundError as exc:
            raise ImportError(
                "Streamlit is required for `login_streamlit`. Install it with `pip install streamlit`."
            ) from exc

        # Ensure we are actually running inside a Streamlit script. If not, give a
        # clear error message instead of crashing when `st.experimental_rerun` is
        # invoked outside the Streamlit runtime.
        if get_script_run_ctx() is None:
            raise RuntimeError(
                "`login_streamlit` must be invoked from within a running Streamlit "
                "app (use `streamlit run your_script.py`). If you need to obtain an "
                "API-key in a regular Python script or notebook, use `Coop.login()` "
                "instead."
            )

        import secrets
        from dotenv import load_dotenv
        from .ep_key_handling import ExpectedParrotKeyHandler
        from ..utilities.utilities import write_api_key_to_env

        # ------------------------------------------------------------------
        # 1. Prepare auth-token and store state across reruns
        # ------------------------------------------------------------------
        if "edsl_auth_token" not in st.session_state:
            st.session_state.edsl_auth_token = secrets.token_urlsafe(16)
            st.session_state.login_start_time = time.time()

        edsl_auth_token: str = st.session_state.edsl_auth_token
        login_url = (
            f"{CONFIG.EXPECTED_PARROT_URL}/login?edsl_auth_token={edsl_auth_token}"
        )

        # ------------------------------------------------------------------
        # 2. Render clickable login link
        # ------------------------------------------------------------------
        st.markdown(
            f"🔗 **Log in to Expected Parrot** → [click here]({login_url})",
            unsafe_allow_html=True,
        )

        # ------------------------------------------------------------------
        # 3. Poll server for API-key (runs once per Streamlit execution)
        # ------------------------------------------------------------------
        api_key = self._get_api_key(edsl_auth_token)
        if api_key is None:
            elapsed = time.time() - st.session_state.login_start_time
            if elapsed > timeout:
                st.error(
                    "Timed-out waiting for login. Please rerun the app to try again."
                )
                return None

            remaining = int(timeout - elapsed)
            st.info(f"Waiting for login… ({remaining}s left)")
            # Trigger a rerun after a short delay to continue polling
            time.sleep(1)

            # Attempt a rerun in a version-agnostic way. Different Streamlit
            # releases expose the helper under different names.
            def _safe_rerun():
                if hasattr(st, "experimental_rerun"):
                    st.experimental_rerun()
                elif hasattr(st, "rerun"):
                    st.rerun()  # introduced in newer versions
                else:
                    # Fallback – advise the user to update Streamlit for automatic polling.
                    st.warning(
                        "Please refresh the page to continue the login flow. "
                        "(Consider upgrading Streamlit to enable automatic refresh.)"
                    )

            try:
                _safe_rerun()
            except Exception:
                # The Streamlit runtime intercepts the rerun exception; any other
                # unexpected errors are ignored to avoid crashing the app.
                pass

        # ------------------------------------------------------------------
        # 4. Key received – persist it and notify user
        # ------------------------------------------------------------------
        ExpectedParrotKeyHandler().store_ep_api_key(api_key)
        os.environ["EXPECTED_PARROT_API_KEY"] = api_key
        path_to_env = write_api_key_to_env(api_key)
        load_dotenv()

        st.success("API-key retrieved and stored. You are now logged-in! 🎉")
        st.caption(f"Key saved to `{path_to_env}`.")

        return api_key

    def transfer_credits(
        self,
        credits_transferred: int,
        recipient_username: str,
        transfer_note: str = None,
    ) -> dict:
        """
        Transfer credits to another user.

        This method transfers a specified number of credits from the authenticated user's
        account to another user's account on the Expected Parrot platform.

        Parameters:
            credits_transferred (int): The number of credits to transfer to the recipient
            recipient_username (str): The username of the recipient
            transfer_note (str, optional): A personal note to include with the transfer

        Returns:
            dict: Information about the transfer transaction, including:
                - success: Whether the transaction was successful
                - transaction_id: A unique identifier for the transaction
                - remaining_credits: The number of credits remaining in the sender's account

        Raises:
            CoopServerResponseError: If there's an error communicating with the server
                or if the transfer criteria aren't met (e.g., insufficient credits)

        Example:
            >>> result = coop.transfer_credits(
            ...     credits_transferred=100,
            ...     recipient_username="friend_username",
            ...     transfer_note="Thanks for your help!"
            ... )
            >>> print(f"Transfer successful! You have {result['remaining_credits']} credits left.")
        """
        response = self._send_server_request(
            uri="api/users/gift",
            method="POST",
            payload={
                "credits_gifted": credits_transferred,
                "recipient_username": recipient_username,
                "gift_note": transfer_note,
            },
        )
        self._resolve_server_response(response)
        return response.json()

    def pay_for_service(
        self,
        credits_transferred: int,
        recipient_username: str,
        service_name: str,
    ) -> dict:
        """
        Pay for a service.

        This method transfers a specified number of credits from the authenticated user's
        account to another user's account on the Expected Parrot platform.

        Parameters:
            credits_transferred (int): The number of credits to transfer to the recipient
            recipient_username (str): The username of the recipient
            service_name (str): The name of the service to pay for

        Returns:
            dict: Information about the transfer transaction, including:
                - success: Whether the transaction was successful
                - transaction_id: A unique identifier for the transaction
                - remaining_credits: The number of credits remaining in the sender's account

        Raises:
            CoopServerResponseError: If there's an error communicating with the server
                or if the transfer criteria aren't met (e.g., insufficient credits)

        Example:
            >>> result = coop.pay_for_service(
            ...     credits_transferred=100,
            ...     service_name="service_name",
            ...     recipient_username="friend_username",
            ... )
            >>> print(f"Transfer successful! You have {result['remaining_credits']} credits left.")
        """
        response = self._send_server_request(
            uri="api/v0/users/pay-for-service",
            method="POST",
            payload={
                "cost_credits": credits_transferred,
                "service_name": service_name,
                "recipient_username": recipient_username,
            },
        )
        self._resolve_server_response(response)
        return response.json()

    def get_balance(self) -> dict:
        """
        Get the current credit balance for the authenticated user.

        This method retrieves the user's current credit balance information from
        the Expected Parrot platform.

        Returns:
            dict: Information about the user's credit balance, including:
                - credits: The current number of credits in the user's account
                - usage_history: Recent credit usage if available

        Raises:
            CoopServerResponseError: If there's an error communicating with the server

        Example:
            >>> balance = coop.get_balance()
            >>> print(f"You have {balance['credits']} credits available.")
        """
        response = self._send_server_request(
            uri="api/v0/users/get-balance", method="GET"
        )
        self._resolve_server_response(response)
        return response.json()

    def get_profile(self) -> dict:
        """
        Get the current user's profile information.

        This method retrieves the authenticated user's profile information from
        the Expected Parrot platform using their API key.

        Returns:
            dict: User profile information including:
                - username: The user's username
                - email: The user's email address

        Raises:
            CoopServerResponseError: If there's an error communicating with the server

        Example:
            >>> profile = coop.get_profile()
            >>> print(f"Welcome, {profile['username']}!")
        """
        response = self._send_server_request(uri="api/v0/users/profile", method="GET")
        self._resolve_server_response(response)
        return response.json()

    def execute_firecrawl_request(self, request_dict: Dict[str, Any]) -> Any:
        """
        Execute a Firecrawl request through the Extension Gateway.

        This method sends a Firecrawl request dictionary to the Extension Gateway's
        /firecrawl/execute endpoint, which processes it using FirecrawlScenario
        and returns EDSL Scenario/ScenarioList objects.

        Parameters:
            request_dict (Dict[str, Any]): A dictionary containing the Firecrawl request.
                Must include:
                - method: The Firecrawl method to execute (scrape, crawl, search, extract, map_urls)
                - api_key: Optional if provided via environment or this method will add it
                - Other method-specific parameters (url_or_urls, query_or_queries, etc.)

        Returns:
            Any: The result from FirecrawlScenario execution:
                - For scrape/extract with single URL: Scenario object
                - For scrape/extract with multiple URLs: ScenarioList object
                - For crawl/search/map_urls: ScenarioList object

        Raises:
            httpx.HTTPError: If the request to the Extension Gateway fails
            ValueError: If the request_dict is missing required fields
            Exception: If the Firecrawl execution fails

        Example:
            >>> # Scrape a single URL
            >>> result = coop.execute_firecrawl_request({
            ...     "method": "scrape",
            ...     "url_or_urls": "https://example.com",
            ...     "kwargs": {"formats": ["markdown"]}
            ... })

            >>> # Search the web
            >>> results = coop.execute_firecrawl_request({
            ...     "method": "search",
            ...     "query_or_queries": "AI research papers",
            ...     "kwargs": {"limit": 10}
            ... })

            >>> # Extract structured data
            >>> result = coop.execute_firecrawl_request({
            ...     "method": "extract",
            ...     "url_or_urls": "https://shop.example.com/product",
            ...     "schema": {"title": "string", "price": "number"},
            ... })
        """
        import httpx
        from ..config import CONFIG

        # Validate request_dict
        if not request_dict or not isinstance(request_dict, dict):
            raise ValueError("request_dict must be a non-empty dictionary")

        if "method" not in request_dict:
            raise ValueError("request_dict must contain 'method' field")

        # Initialize the Extension Gateway client
        gateway_url = CONFIG.get_extension_gateway_url()

        # Prepare headers with the Coop API key for authentication
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        # Make the request to the Extension Gateway
        try:
            with httpx.Client(timeout=300.0) as client:
                response = client.post(
                    f"{gateway_url}/firecrawl/execute",
                    json=request_dict,
                    headers=headers,
                )

                # Check for errors
                if response.status_code == 400:
                    error_detail = response.json().get("detail", "Bad request")
                    raise ValueError(f"Firecrawl request failed: {error_detail}")
                elif response.status_code == 401:
                    error_detail = response.json().get("detail", "Unauthorized")
                    raise ValueError(f"Authentication failed: {error_detail}")
                elif response.status_code == 500:
                    error_detail = response.json().get("detail", "Internal error")
                    raise Exception(f"Firecrawl execution error: {error_detail}")

                response.raise_for_status()

                # Parse the response
                response_data = response.json()

                if not response_data.get("success", False):
                    raise Exception(f"Firecrawl request failed: {response_data}")

                # Return the result
                # The gateway should have already converted it to proper EDSL objects
                result = response_data.get("result")
                if "scenarios" in result:
                    from ..scenarios import ScenarioList

                    return ScenarioList.from_dict(result)
                else:
                    from ..scenarios import Scenario

                    return Scenario.from_dict(result)

        except httpx.HTTPError as e:
            self._logger.error(f"HTTP error calling Extension Gateway: {e}")
            raise
        except Exception as e:
            self._logger.error(f"Error executing Firecrawl request: {e}")
            raise

    async def report_error(self, error: Exception) -> None:
        """
        Report an error for debugging purposes.

        This method provides a non-blocking way to report errors that occur during
        EDSL operations. It sends error reports to the server for monitoring and
        debugging purposes, while also printing to stderr for immediate feedback.

        Duplicate errors (same error type and message) are not reported if they
        occurred within the past minute to prevent spam.

        Parameters:
            error (Exception): The exception to report

        Example:
            >>> try:
            ...     # some operation that might fail
            ...     pass
            ... except Exception as e:
            ...     await coop.report_error(e)
        """
        import sys
        import traceback
        import httpx
        import hashlib
        from datetime import datetime

        # Prepare error data for remote logging
        try:
            import time

            start_time = time.time()
            current_time = time.time()

            # Create a signature for this error to detect duplicates
            error_signature = hashlib.md5(
                f"{type(error).__name__}:{str(error)}".encode()
            ).hexdigest()
            # Check if we've reported this same error recently (within 1 minute)
            if error_signature in Coop._class_error_cache:
                last_reported = Coop._class_error_cache[error_signature]
                if current_time - last_reported < 60:  # 60 seconds = 1 minute
                    # Skip reporting this duplicate error
                    return

            # Clean up old entries from cache (older than 1 minute)
            Coop._class_error_cache = {
                sig: timestamp
                for sig, timestamp in Coop._class_error_cache.items()
                if current_time - timestamp < 60
            }

            # Mark this error as reported BEFORE attempting to send to prevent duplicates
            Coop._class_error_cache[error_signature] = current_time

            error_data = {
                "error_type": type(error).__name__,
                "error_message": str(error),
                "traceback": traceback.format_exc(),
                "timestamp": datetime.now().isoformat(),
            }

            # Send to remote logging endpoint asynchronously
            url = f"{self.api_url}/api/v0/user_service_error_logs"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url, json=error_data, headers=self.headers, timeout=4.0
                )

                end_time = time.time()
                duration_ms = round((end_time - start_time) * 1000, 2)

                # if response.status_code == 200:
                #     print(f"Error report sent to server (took {duration_ms}ms)", file=sys.stderr)
                # else:
                #     print(f"Failed to send error report to server: {response.status_code} (took {duration_ms}ms)", file=sys.stderr)

        except Exception as send_error:
            # Don't let error reporting itself cause issues
            print(f"Failed to send error report: {str(send_error)}", file=sys.stderr)

    def login_gradio(self, timeout: int = 120, launch: bool = True, **launch_kwargs):
        """
        Start the EDSL auth token login flow inside a **Gradio** application.

        This helper mirrors the behaviour of :py:meth:`Coop.login_streamlit` but
        renders the login link and status updates inside a Gradio UI.  It will
        poll the Expected Parrot server for the API-key associated with a newly
        generated auth-token and, once received, store it via
        :pyclass:`~edsl.coop.ep_key_handling.ExpectedParrotKeyHandler` as well as
        in the local ``.env`` file so subsequent sessions pick it up
        automatically.

        Parameters
        ----------
        timeout : int, default 120
            How many seconds to wait for the user to complete the login before
            giving up.
        launch : bool, default True
            If ``True`` the Gradio app is immediately launched with
            ``demo.launch(**launch_kwargs)``.  Set this to ``False`` if you want
            to embed the returned :class:`gradio.Blocks` object into an existing
            Gradio interface.
        **launch_kwargs
            Additional keyword-arguments forwarded to ``gr.Blocks.launch`` when
            *launch* is ``True``.

        Returns
        -------
        str | gradio.Blocks | None
            • If the API-key is retrieved within *timeout* seconds while the
              function is executing (e.g. when *launch* is ``False`` and the
              caller integrates the Blocks into another app) the key is
              returned.
            • If *launch* is ``True`` the method returns ``None`` after the
              Gradio app has been launched.
            • If *launch* is ``False`` the constructed ``gr.Blocks`` is
              returned so the caller can compose it further.
        """
        try:
            import gradio as gr
        except ModuleNotFoundError as exc:
            raise ImportError(
                "Gradio is required for `login_gradio`. Install it with `pip install gradio`."
            ) from exc

        import secrets
        from dotenv import load_dotenv
        from .ep_key_handling import ExpectedParrotKeyHandler
        from ..utilities.utilities import write_api_key_to_env

        # ------------------------------------------------------------------
        # 1. Prepare auth-token
        # ------------------------------------------------------------------
        edsl_auth_token = secrets.token_urlsafe(16)
        login_url = (
            f"{CONFIG.EXPECTED_PARROT_URL}/login?edsl_auth_token={edsl_auth_token}"
        )
        start_time = time.time()

        # ------------------------------------------------------------------
        # 2. Build Gradio interface
        # ------------------------------------------------------------------
        with gr.Blocks() as demo:
            gr.HTML(
                f'🔗 <b>Log in to Expected Parrot</b> → <a href="{login_url}" target="_blank">click here</a>'
            )
            status_md = gr.Markdown("Waiting for login…")
            refresh_btn = gr.Button(
                "I've logged in – click to continue", elem_id="refresh-btn"
            )
            key_state = gr.State(value=None)

            # --------------------------------------------------------------
            # Polling callback
            # --------------------------------------------------------------
            def _refresh(current_key):  # noqa: D401, pylint: disable=unused-argument
                """Poll server for API-key and update UI accordingly."""

                # Fallback helper to generate a `update` object for the refresh button
                def _button_update(**kwargs):
                    try:
                        return gr.Button.update(**kwargs)
                    except AttributeError:
                        return gr.update(**kwargs)

                api_key = self._get_api_key(edsl_auth_token)
                # Fall back to env var in case the key was obtained earlier in this session
                if not api_key:
                    api_key = os.environ.get("EXPECTED_PARROT_API_KEY")
                elapsed = time.time() - start_time
                remaining = max(0, int(timeout - elapsed))

                if api_key:
                    # Persist and expose the key
                    ExpectedParrotKeyHandler().store_ep_api_key(api_key)
                    os.environ["EXPECTED_PARROT_API_KEY"] = api_key
                    path_to_env = write_api_key_to_env(api_key)
                    load_dotenv()
                    success_msg = (
                        "API-key retrieved and stored 🎉\n\n"
                        f"Key saved to `{path_to_env}`."
                    )
                    return (
                        success_msg,
                        _button_update(interactive=False, visible=False),
                        api_key,
                    )

                if elapsed > timeout:
                    err_msg = (
                        "Timed-out waiting for login. Please refresh the page "
                        "or restart the app to try again."
                    )
                    return (
                        err_msg,
                        _button_update(),
                        None,
                    )

                info_msg = f"Waiting for login… ({remaining}s left)"
                return (
                    info_msg,
                    _button_update(),
                    None,
                )

            # Initial status check when the interface loads
            demo.load(
                fn=_refresh,
                inputs=key_state,
                outputs=[status_md, refresh_btn, key_state],
            )

        # ------------------------------------------------------------------
        # 3. Launch or return interface
        # ------------------------------------------------------------------
        if launch:
            demo.launch(**launch_kwargs)
            return None
        return demo


def main():
    """
    A simple example for the coop client
    """
    from uuid import uuid4
    from edsl import (
        Agent,
        AgentList,
        Cache,
        Notebook,
        QuestionFreeText,
        QuestionMultipleChoice,
        Results,
        Scenario,
        ScenarioList,
        Survey,
    )
    from ..coop import Coop
    from ..caching import CacheEntry
    from ..jobs import Jobs

    # init & basics
    API_KEY = "b"
    coop = Coop(api_key=API_KEY)
    coop
    coop.edsl_settings

    ##############
    # A. A simple example
    ##############
    # .. create and manipulate an object through the Coop client
    response = coop.create(QuestionMultipleChoice.example())
    coop.get(response.get("uuid"))
    coop.get(response.get("uuid"), expected_object_type="question")
    coop.get(response.get("url"))
    coop.create(QuestionMultipleChoice.example())
    coop.list("question")
    coop.patch(response.get("uuid"), visibility="private")
    coop.patch(response.get("uuid"), description="hey")
    coop.patch(response.get("uuid"), value=QuestionFreeText.example())
    # coop.patch(response.get("uuid"), value=Survey.example()) - should throw error
    coop.get(response.get("uuid"))
    coop.delete(response.get("uuid"))

    # .. create and manipulate an object through the class
    response = QuestionMultipleChoice.example().push()
    QuestionMultipleChoice.pull(response.get("uuid"))
    QuestionMultipleChoice.pull(response.get("url"))
    QuestionMultipleChoice.patch(response.get("uuid"), visibility="private")
    QuestionMultipleChoice.patch(response.get("uuid"), description="hey")
    QuestionMultipleChoice.patch(response.get("uuid"), value=QuestionFreeText.example())
    QuestionMultipleChoice.pull(response.get("uuid"))
    QuestionMultipleChoice.delete(response.get("uuid"))

    ##############
    # B. Examples with all objects
    ##############
    OBJECTS = [
        ("agent", Agent),
        ("agent_list", AgentList),
        ("cache", Cache),
        ("notebook", Notebook),
        ("question", QuestionMultipleChoice),
        ("results", Results),
        ("scenario", Scenario),
        ("scenario_list", ScenarioList),
        ("survey", Survey),
    ]
    for object_type, cls in OBJECTS:
        print(f"Testing {object_type} objects")
        # 1. Delete existing objects
        existing_objects = coop.list(object_type)
        for item in existing_objects:
            coop.delete(item.get("uuid"))
        # 2. Create new objects
        example = cls.example()
        response_1 = coop.create(example)
        response_2 = coop.create(cls.example(), visibility="private")
        response_3 = coop.create(cls.example(), visibility="public")
        response_4 = coop.create(
            cls.example(), visibility="unlisted", description="hey"
        )
        # 3. Retrieve all objects
        objects = coop.list(object_type)
        assert len(objects) == 4
        # 4. Try to retrieve an item that does not exist
        try:
            coop.get(uuid4())
        except Exception as e:
            print(e)
        # 5. Try to retrieve all test objects by their uuids
        for response in [response_1, response_2, response_3, response_4]:
            coop.get(response.get("uuid"))
        # 6. Change visibility of all objects
        for item in objects:
            coop.patch(item.get("uuid"), visibility="private")
        # 6. Change description of all objects
        for item in objects:
            coop.patch(item.get("uuid"), description="hey")
        # 7. Delete all objects
        for item in objects:
            coop.delete(item.get("uuid"))
        assert len(coop.list(object_type)) == 0

    ##############
    # C. Remote Cache
    ##############
    # clear
    coop.legacy_remote_cache_clear()
    assert coop.legacy_remote_cache_get() == []
    # create one remote cache entry
    cache_entry = CacheEntry.example()
    cache_entry.to_dict()
    # coop.remote_cache_create(cache_entry)
    # create many remote cache entries
    cache_entries = [CacheEntry.example(randomize=True) for _ in range(10)]
    # coop.remote_cache_create_many(cache_entries)
    # get all remote cache entries
    coop.legacy_remote_cache_get()
    coop.legacy_remote_cache_get(exclude_keys=[])
    coop.legacy_remote_cache_get(exclude_keys=["a"])
    exclude_keys = [cache_entry.key for cache_entry in cache_entries]
    coop.legacy_remote_cache_get(exclude_keys)
    # clear
    coop.legacy_remote_cache_clear()
    coop.legacy_remote_cache_get()

    ##############
    # D. Remote Inference
    ##############
    job = Jobs.example()
    coop.remote_inference_cost(job)
    job_coop_object = coop.remote_inference_create(job)
    job_coop_results = coop.new_remote_inference_get(job_coop_object.get("uuid"))
    coop.get(job_coop_results.get("results_uuid"))

    import streamlit as st
    from edsl.coop import Coop

    coop = Coop()  # no API-key required yet
    api_key = coop.login_streamlit()  # renders link + handles polling & storage

    if api_key:
        st.success("Ready to use EDSL with remote features!")
