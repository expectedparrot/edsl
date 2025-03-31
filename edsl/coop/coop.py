import aiohttp
import base64
import json
import requests

from typing import Any, Optional, Union, Literal, TypedDict, TYPE_CHECKING
from uuid import UUID

from .. import __version__

from ..config import CONFIG
from ..caching import CacheEntry

if TYPE_CHECKING:
    from ..jobs import Jobs
    from ..surveys import Survey

from .exceptions import (
    CoopInvalidURLError,
    CoopNoUUIDError,
    CoopServerResponseError,
)
from .utils import (
    EDSLObject,
    ObjectRegistry,
    ObjectType,
    RemoteJobStatus,
    VisibilityType,
)

from .coop_functions import CoopFunctionsMixin
from .ep_key_handling import ExpectedParrotKeyHandler

from ..inference_services.data_structures import ServiceToModelsMapping


class RemoteInferenceResponse(TypedDict):
    job_uuid: str
    results_uuid: str
    results_url: str
    latest_error_report_uuid: str
    latest_error_report_url: str
    status: str
    reason: str
    credits_consumed: float
    version: str


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

    def __init__(
        self, api_key: Optional[str] = None, url: Optional[str] = None
    ) -> None:
        """
        Initialize the Expected Parrot API client.

        This constructor sets up the connection to Expected Parrot's cloud services.
        If not provided explicitly, it will attempt to obtain an API key from
        environment variables or from a stored location in the user's config directory.

        Parameters:
            api_key (str, optional): API key for authentication with Expected Parrot.
                If not provided, will attempt to obtain from environment or stored location.
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
        """
        self.ep_key_handler = ExpectedParrotKeyHandler()
        self.api_key = api_key or self.ep_key_handler.get_ep_api_key()

        self.url = url or CONFIG.EXPECTED_PARROT_URL
        if self.url.endswith("/"):
            self.url = self.url[:-1]
        if "chick.expectedparrot" in self.url:
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
            timeout = max(40, (len(payload.get("json_string", "")) // (1024 * 1024)))
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

                raise CoopInvalidMethodError(f"Invalid {method=}.")
        except requests.ConnectionError:
            raise requests.ConnectionError(f"Could not connect to the server at {url}.")

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

    def _resolve_server_response(
        self, response: requests.Response, check_api_key: bool = True
    ) -> None:
        """
        Check the response from the server and raise errors as appropriate.
        """
        # Get EDSL version from header
        # breakpoint()
        # Commented out as currently unused
        # server_edsl_version = response.headers.get("X-EDSL-Version")

        # if server_edsl_version:
        #     if self._user_version_is_outdated(
        #         user_version_str=self._edsl_version,
        #         server_version_str=server_edsl_version,
        #     ):
        #         print(
        #             "Please upgrade your EDSL version to access our latest features. Open your terminal and run `pip install --upgrade edsl`"
        #         )

        if response.status_code >= 400:
            try:
                message = response.json().get("detail")
            except json.JSONDecodeError:
                raise CoopServerResponseError(
                    f"Server returned status code {response.status_code}."
                    "JSON response could not be decoded.",
                    "The server response was: " + response.text,
                )
            # print(response.text)
            if "The API key you provided is invalid" in message and check_api_key:
                import secrets
                from ..utilities.utilities import write_api_key_to_env

                edsl_auth_token = secrets.token_urlsafe(16)

                print("Your Expected Parrot API key is invalid.")
                self._display_login_url(
                    edsl_auth_token=edsl_auth_token,
                    link_description="\n🔗 Use the link below to log in to your account and automatically update your API key.",
                )
                api_key = self._poll_for_api_key(edsl_auth_token)

                if api_key is None:
                    print("\nTimed out waiting for login. Please try again.")
                    return

                print("\n✨ API key retrieved.")

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
                print(message)
                message = "Please provide an Expected Parrot API key."

            raise CoopServerResponseError(message)

    def _resolve_gcs_response(self, response: requests.Response) -> None:
        """
        Check the response from uploading or downloading a file from Google Cloud Storage.
        Raise errors as appropriate.
        """
        if response.status_code >= 400:
            try:
                import xml.etree.ElementTree as ET

                # Extract elements from XML string
                root = ET.fromstring(response.text)

                code = root.find("Code").text
                message = root.find("Message").text
                details = root.find("Details").text
            except Exception:
                from .exceptions import CoopServerResponseError

                raise CoopServerResponseError(
                    f"Server returned status code {response.status_code}. "
                    f"XML response could not be decoded. "
                    f"The server response was: {response.text}"
                )

            from .exceptions import CoopServerResponseError

            raise CoopServerResponseError(
                f"An error occurred: {code} - {message} - {details}"
            )

    def _poll_for_api_key(
        self, edsl_auth_token: str, timeout: int = 120
    ) -> Union[str, None]:
        """
        Allows the user to retrieve their Expected Parrot API key by logging in with an EDSL auth token.

        :param edsl_auth_token: The EDSL auth token to use for login
        :param timeout: Maximum time to wait for login, in seconds (default: 120)
        """
        import time
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
        Handle None values during JSON serialization.
        - Return "null" if the value is None. Otherwise, don't return anything.
        """
        if value is None:
            return "null"

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
        visibility: Optional[VisibilityType] = "unlisted",
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
                    )
                    if object_type != "scenario"
                    else ""
                ),
                "object_type": object_type,
                "file_store_metadata": file_store_metadata,
                "visibility": visibility,
                "version": self._edsl_version,
            },
        )
        self._resolve_server_response(response)
        response_json = response.json()

        if object_type == "scenario":
            json_data = json.dumps(
                object_dict,
                default=self._json_handle_none,
            )
            headers = {"Content-Type": "application/json"}
            if response_json.get("upload_signed_url"):
                signed_url = response_json.get("upload_signed_url")
            else:
                from .exceptions import CoopResponseError

                raise CoopResponseError("No signed url was provided received")

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
        edsl_class = ObjectRegistry.object_type_to_edsl_class.get(object_type)
        object = edsl_class.from_dict(json.loads(json_string))
        if object_type == "results":
            object.initialize_cache_from_results()
        return object

    def get_all(self, object_type: ObjectType) -> list[dict[str, Any]]:
        """
        Retrieve all objects of a certain type associated with the user.
        """
        edsl_class = ObjectRegistry.object_type_to_edsl_class.get(object_type)
        response = self._send_server_request(
            uri="api/v0/objects",
            method="GET",
            params={"type": object_type},
        )
        self._resolve_server_response(response)
        objects = []
        for o in response.json():
            json_string = o.get("json_string")
            ## check if load from bucket needed.
            if "load_from:" in json_string[0:12]:
                load_link = json_string.split("load_from:")[1]
                object_data = requests.get(load_link)
                self._resolve_gcs_response(object_data)
                json_string = object_data.text

            json_string = json.loads(json_string)
            object = {
                "object": edsl_class.from_dict(json_string),
                "uuid": o.get("uuid"),
                "version": o.get("version"),
                "description": o.get("description"),
                "visibility": o.get("visibility"),
                "url": f"{self.url}/content/{o.get('uuid')}",
                "alias_url": self._get_alias_url(
                    o.get("owner_username"), o.get("alias")
                ),
            }
            objects.append(object)

        return objects

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
        if (
            description is None
            and visibility is None
            and value is None
            and alias is None
        ):
            from .exceptions import CoopPatchError

            raise CoopPatchError("Nothing to patch.")

        obj_uuid, owner_username, obj_alias = self._resolve_uuid_or_alias(url_or_uuid)

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
                    )
                    if value
                    else None
                ),
                "visibility": visibility,
            },
        )
        self._resolve_server_response(response)
        return response.json()

    ################
    # Remote Cache
    ################
    # def remote_cache_create(
    #     self,
    #     cache_entry: CacheEntry,
    #     visibility: VisibilityType = "private",
    #     description: Optional[str] = None,
    # ) -> dict:
    #     """
    #     Create a single remote cache entry.
    #     If an entry with the same key already exists in the database, update it instead.

    #     :param cache_entry: The cache entry to send to the server.
    #     :param visibility: The visibility of the cache entry.
    #     :param optional description: A description for this entry in the remote cache.

    #     >>> entry = CacheEntry.example()
    #     >>> coop.remote_cache_create(cache_entry=entry)
    #     {'status': 'success', 'created_entry_count': 1, 'updated_entry_count': 0}
    #     """
    #     response = self._send_server_request(
    #         uri="api/v0/remote-cache",
    #         method="POST",
    #         payload={
    #             "json_string": json.dumps(cache_entry.to_dict()),
    #             "version": self._edsl_version,
    #             "visibility": visibility,
    #             "description": description,
    #         },
    #     )
    #     self._resolve_server_response(response)
    #     response_json = response.json()
    #     created_entry_count = response_json.get("created_entry_count", 0)
    #     if created_entry_count > 0:
    #         self.remote_cache_create_log(
    #             response,
    #             description="Upload new cache entries to server",
    #             cache_entry_count=created_entry_count,
    #         )
    #     return response.json()

    # def remote_cache_create_many(
    #     self,
    #     cache_entries: list[CacheEntry],
    #     visibility: VisibilityType = "private",
    #     description: Optional[str] = None,
    # ) -> dict:
    #     """
    #     Create many remote cache entries.
    #     If an entry with the same key already exists in the database, update it instead.

    #     :param cache_entries: The list of cache entries to send to the server.
    #     :param visibility: The visibility of the cache entries.
    #     :param optional description: A description for these entries in the remote cache.

    #     >>> entries = [CacheEntry.example(randomize=True) for _ in range(10)]
    #     >>> coop.remote_cache_create_many(cache_entries=entries)
    #     {'status': 'success', 'created_entry_count': 10, 'updated_entry_count': 0}
    #     """
    #     payload = [
    #         {
    #             "json_string": json.dumps(c.to_dict()),
    #             "version": self._edsl_version,
    #             "visibility": visibility,
    #             "description": description,
    #         }
    #         for c in cache_entries
    #     ]
    #     response = self._send_server_request(
    #         uri="api/v0/remote-cache/many",
    #         method="POST",
    #         payload=payload,
    #         timeout=40,
    #     )
    #     self._resolve_server_response(response)
    #     response_json = response.json()
    #     created_entry_count = response_json.get("created_entry_count", 0)
    #     if created_entry_count > 0:
    #         self.remote_cache_create_log(
    #             response,
    #             description="Upload new cache entries to server",
    #             cache_entry_count=created_entry_count,
    #         )
    #     return response.json()

    def remote_cache_get(
        self,
        job_uuid: Optional[Union[str, UUID]] = None,
    ) -> list[CacheEntry]:
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
        select_keys: Optional[list[str]] = None,
    ) -> list[CacheEntry]:
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

    def legacy_remote_cache_get(
        self,
        exclude_keys: Optional[list[str]] = None,
        select_keys: Optional[list[str]] = None,
    ) -> list[CacheEntry]:
        """
        Get all remote cache entries.

        :param optional select_keys: Only return CacheEntry objects with these keys.
        :param optional exclude_keys: Exclude CacheEntry objects with these keys.

        >>> coop.legacy_remote_cache_get()
        [CacheEntry(...), CacheEntry(...), ...]
        """
        if exclude_keys is None:
            exclude_keys = []
        if select_keys is None:
            select_keys = []
        response = self._send_server_request(
            uri="api/v0/remote-cache/legacy/get-many",
            method="POST",
            payload={"exclude_keys": exclude_keys, "selected_keys": select_keys},
            timeout=40,
        )
        self._resolve_server_response(response)
        return [
            CacheEntry.from_dict(json.loads(v.get("json_string")))
            for v in response.json()
        ]

    def legacy_remote_cache_get_diff(
        self,
        client_cacheentry_keys: list[str],
    ) -> dict:
        """
        Get the difference between local and remote cache entries for a user.
        """
        response = self._send_server_request(
            uri="api/v0/remote-cache/legacy/get-diff",
            method="POST",
            payload={"keys": client_cacheentry_keys},
            timeout=40,
        )
        self._resolve_server_response(response)
        response_json = response.json()
        response_dict = {
            "client_missing_cacheentries": [
                CacheEntry.from_dict(json.loads(c.get("json_string")))
                for c in response_json.get("client_missing_cacheentries", [])
            ],
            "server_missing_cacheentry_keys": response_json.get(
                "server_missing_cacheentry_keys", []
            ),
        }
        downloaded_entry_count = len(response_dict["client_missing_cacheentries"])
        if downloaded_entry_count > 0:
            self.legacy_remote_cache_create_log(
                response,
                description="Download missing cache entries to client",
                cache_entry_count=downloaded_entry_count,
            )
        return response_dict

    def legacy_remote_cache_clear(self) -> dict:
        """
        Clear all remote cache entries.

        >>> entries = [CacheEntry.example(randomize=True) for _ in range(10)]
        >>> coop.legacy_remote_cache_create_many(cache_entries=entries)
        >>> coop.legacy_remote_cache_clear()
        {'status': 'success', 'deleted_entry_count': 10}
        """
        response = self._send_server_request(
            uri="api/v0/remote-cache/legacy/delete-all",
            method="DELETE",
        )
        self._resolve_server_response(response)
        response_json = response.json()
        deleted_entry_count = response_json.get("deleted_entry_count", 0)
        if deleted_entry_count > 0:
            self.legacy_remote_cache_create_log(
                response,
                description="Clear cache entries",
                cache_entry_count=deleted_entry_count,
            )
        return response.json()

    def legacy_remote_cache_create_log(
        self, response: requests.Response, description: str, cache_entry_count: int
    ) -> Union[dict, None]:
        """
        If a remote cache action has been completed successfully,
        log the action.
        """
        if 200 <= response.status_code < 300:
            log_response = self._send_server_request(
                uri="api/v0/remote-cache-log/legacy",
                method="POST",
                payload={
                    "description": description,
                    "cache_entry_count": cache_entry_count,
                },
            )
            self._resolve_server_response(log_response)
            return response.json()

    def legacy_remote_cache_clear_log(self) -> dict:
        """
        Clear all remote cache log entries.

        >>> coop.legacy_remote_cache_clear_log()
        {'status': 'success'}
        """
        response = self._send_server_request(
            uri="api/v0/remote-cache-log/legacy/delete-all",
            method="DELETE",
        )
        self._resolve_server_response(response)
        return response.json()

    def remote_inference_create(
        self,
        job: "Jobs",
        description: Optional[str] = None,
        status: RemoteJobStatus = "queued",
        visibility: Optional[VisibilityType] = "unlisted",
        initial_results_visibility: Optional[VisibilityType] = "unlisted",
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
        self, job_uuid: Optional[str] = None, results_uuid: Optional[str] = None
    ) -> RemoteInferenceResponse:
        """
        Get the status and details of a remote inference job.

        This method retrieves the current status and information about a remote job,
        including links to results if the job has completed successfully.

        Parameters:
            job_uuid (str, optional): The UUID of the remote job to check
            results_uuid (str, optional): The UUID of the results associated with the job
                (can be used if you only have the results UUID)

        Returns:
            RemoteInferenceResponse: Information about the job including:
                - job_uuid: The unique identifier for the job
                - results_uuid: The UUID of the results (if job is completed)
                - results_url: URL to access the results (if available)
                - latest_error_report_uuid: UUID of error report (if job failed)
                - latest_error_report_url: URL to access error details (if available)
                - status: Current status ("queued", "running", "completed", "failed")
                - reason: Reason for failure (if applicable)
                - credits_consumed: Credits used for the job execution
                - version: EDSL version used for the job

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

        response = self._send_server_request(
            uri="api/v0/remote-inference",
            method="GET",
            params=params,
        )
        self._resolve_server_response(response)
        data = response.json()

        results_uuid = data.get("results_uuid")
        latest_error_report_uuid = data.get("latest_error_report_uuid")

        if results_uuid is None:
            results_url = None
        else:
            results_url = f"{self.url}/content/{results_uuid}"

        if latest_error_report_uuid is None:
            latest_error_report_url = None
        else:
            latest_error_report_url = (
                f"{self.url}/home/remote-inference/error/{latest_error_report_uuid}"
            )

        return RemoteInferenceResponse(
            **{
                "job_uuid": data.get("job_uuid"),
                "results_uuid": results_uuid,
                "results_url": results_url,
                "latest_error_report_uuid": latest_error_report_uuid,
                "latest_error_report_url": latest_error_report_url,
                "status": data.get("status"),
                "reason": data.get("latest_failure_reason"),
                "credits_consumed": data.get("price"),
                "version": data.get("version"),
            }
        )

    def get_running_jobs(self) -> list[str]:
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
        Get the cost of a remote inference job.

        :param input: The EDSL job to send to the server.

        >>> job = Jobs.example()
        >>> coop.remote_inference_cost(input=job)
        {'credits': 0.77, 'usd': 0.0076950000000000005}
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
            "credits": response_json.get("cost_in_credits"),
            "usd": response_json.get("cost_in_usd"),
        }

    ################
    # PROJECTS
    ################
    def create_project(
        self,
        survey: "Survey",
        project_name: str = "Project",
        survey_description: Optional[str] = None,
        survey_alias: Optional[str] = None,
        survey_visibility: Optional[VisibilityType] = "unlisted",
    ):
        """
        Create a survey object on Coop, then create a project from the survey.
        """
        survey_details = self.create(
            object=survey,
            description=survey_description,
            alias=survey_alias,
            visibility=survey_visibility,
        )
        survey_uuid = survey_details.get("uuid")
        response = self._send_server_request(
            uri="api/v0/projects/create-from-survey",
            method="POST",
            payload={"project_name": project_name, "survey_uuid": str(survey_uuid)},
        )
        self._resolve_server_response(response)
        response_json = response.json()
        return {
            "name": response_json.get("project_name"),
            "uuid": response_json.get("uuid"),
            "admin_url": f"{self.url}/home/projects/{response_json.get('uuid')}",
            "respondent_url": f"{self.url}/respond/{response_json.get('uuid')}",
        }

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

    def fetch_models(self) -> ServiceToModelsMapping:
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
        return ServiceToModelsMapping(data)

    def fetch_working_models(self) -> list[dict]:
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

        if console.is_terminal:
            # Running in a standard terminal, show the full URL
            if link_description:
                rich_print(
                    "{link_description}\n[#38bdf8][link={url}]{url}[/link][/#38bdf8]"
                )
            else:
                rich_print(f"[#38bdf8][link={url}]{url}[/link][/#38bdf8]")
        else:
            # Running in an interactive environment (e.g., Jupyter Notebook), hide the URL
            if link_description:
                rich_print(
                    f"{link_description}\n[#38bdf8][link={url}][underline]Log in and automatically store key[/underline][/link][/#38bdf8]"
                )
            else:
                rich_print(
                    f"[#38bdf8][link={url}][underline]Log in and automatically store key[/underline][/link][/#38bdf8]"
                )

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

        self._display_login_url(
            edsl_auth_token=edsl_auth_token,
            link_description="\n🔗 Use the link below to log in to Expected Parrot so we can automatically update your API key.",
        )
        api_key = self._poll_for_api_key(edsl_auth_token)

        if api_key is None:
            from .exceptions import CoopTimeoutError

            raise CoopTimeoutError("Timed out waiting for login. Please try again.")

        path_to_env = write_api_key_to_env(api_key)
        print("\n✨ API key retrieved and written to .env file at the following path:")
        print(f"    {path_to_env}")

        # Add API key to environment
        load_dotenv()


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
    coop.get_all("question")
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
        existing_objects = coop.get_all(object_type)
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
        objects = coop.get_all(object_type)
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
        assert len(coop.get_all(object_type)) == 0

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
    job_coop_results = coop.remote_inference_get(job_coop_object.get("uuid"))
    coop.get(job_coop_results.get("results_uuid"))
