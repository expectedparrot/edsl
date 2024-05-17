import aiohttp
import json
import os
import requests
from typing import Any, Optional, Union, Literal
from uuid import UUID
import edsl
from edsl import CONFIG
from edsl.coop.utils import EDSLObject, ObjectRegistry, ObjectType, VisibilityType


class Coop:
    """
    Client for the Expected Parrot API.
    """

    def __init__(self, api_key: str = None, url: str = None) -> None:
        """
        Initialize the client.
        """
        self.api_key = api_key or os.getenv("EXPECTED_PARROT_API_KEY")
        self.url = url or CONFIG.EXPECTED_PARROT_URL
        self._edsl_version = edsl.__version__

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
        return headers

    def _send_server_request(
        self,
        uri: str,
        method: str,
        payload: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> requests.Response:
        """
        Send a request to the server and return the response.
        """
        url = f"{self.url}/{uri}"
        try:
            if method.lower() in ["GET", "DELETE"]:
                response = requests.request(
                    method, url, params=params, headers=self.headers
                )
            else:
                response = requests.request(
                    method, url, json=payload, headers=self.headers
                )
        except requests.ConnectionError:
            raise requests.ConnectionError("Could not connect to the server.")

        return response

    def _resolve_server_response(self, response: requests.Response) -> None:
        """
        Check the response from the server and raise errors as appropriate.
        """
        if response.status_code >= 400:
            message = response.json().get("detail")
            if "Authorization" in message:
                message = "Please provide an Expected Parrot API key."
            raise Exception(message)

    def _json_handle_none(self, value: Any) -> Any:
        """
        Handle None values during JSON serialization.
        - Return "null" if the value is None. Otherwise, don't return anything.
        """
        if value is None:
            return "null"

    @property
    def edsl_settings(self) -> dict:
        """
        Retrieve and return the EDSL settings stored on Coop.
        """
        response = self._send_server_request(uri="api/v0/edsl-settings", method="GET")
        self._resolve_server_response(response)
        return response.json()

    ################
    # Objects
    ################

    # TODO: add URL to get and get_all methods

    def create(
        self,
        object: EDSLObject,
        visibility: VisibilityType = "unlisted",
    ) -> dict:
        """
        Create an EDSL object in the Coop server.
        """
        object_type = ObjectRegistry.get_object_type_by_edsl_class(object)
        response = self._send_server_request(
            uri=f"api/v0/object",
            method="POST",
            payload={
                "object_type": object_type,
                "json_string": json.dumps(
                    object.to_dict(),
                    default=self._json_handle_none,
                ),
                "visibility": visibility,
                "version": self._edsl_version,
            },
        )
        self._resolve_server_response(response)
        response_json = response.json()
        return {
            "uuid": response_json.get("uuid"),
            "version": self._edsl_version,
            "visibility": response_json.get("visibility"),
            "url": "TO BE ADDED",
        }

    def get(
        self,
        object_type: ObjectType = None,
        uuid: Union[str, UUID] = None,
        url: str = None,
    ) -> EDSLObject:
        """
        Retrieve an EDSL object either by object type & UUID, or by its url.
        - The object has to belong to the user or not be private.
        - Returns the initialized object class instance.

        :param object_type: the type of object to retrieve.
        :param uuid: the uuid of the object either in str or UUID format.
        :param url: the url of the object.
        """
        if url:
            object_type = url.split("/")[-2]
            uuid = url.split("/")[-1]
        elif not object_type and not uuid:
            raise Exception("Provide either object_type & UUID, or a url.")
        edsl_class = ObjectRegistry.object_type_to_edsl_class.get(object_type)
        response = self._send_server_request(
            uri=f"api/v0/object",
            method="GET",
            params={"type": object_type, "uuid": uuid},
        )
        self._resolve_server_response(response)
        json_string = response.json().get("json_string")
        return edsl_class.from_dict(json.loads(json_string))

    def _get_base(
        self,
        cls: EDSLObject,
        uuid: Union[str, UUID],
    ) -> EDSLObject:
        """
        Used by the Base class to offer a get functionality.
        """
        object_type = ObjectRegistry.get_object_type_by_edsl_class(cls)
        return self.get(object_type, uuid)

    def get_all(self, object_type: ObjectType) -> list[EDSLObject]:
        """
        Retrieve all objects of a certain type associated with the user.
        """
        edsl_class = ObjectRegistry.object_type_to_edsl_class.get(object_type)
        response = self._send_server_request(
            uri=f"api/v0/objects",
            method="GET",
            params={"type": object_type},
        )
        self._resolve_server_response(response)
        objects = [
            {
                "object": edsl_class.from_dict(json.loads(o.get("json_string"))),
                "uuid": o.get("uuid"),
                "version": o.get("version"),
                "visibility": o.get("visibility"),
                "url": "TO BE ADDED",
            }
            for o in response.json()
        ]
        return objects

    def delete(self, object_type: str, uuid: Union[str, UUID]) -> dict:
        """
        Delete an object from the server.
        """
        response = self._send_server_request(
            uri=f"api/v0/object",
            method="DELETE",
            params={"type": object_type, "uuid": uuid},
        )
        self._resolve_server_response(response)
        return response.json()

    ################
    # Remote Caching
    ################
    from edsl.data.CacheEntry import CacheEntry

    def create_cache_entry(
        self, cache_entry: CacheEntry, visibility: str = "unlisted"
    ) -> dict:
        """
        Create a CacheEntry object.
        """
        response = self._send_server_request(
            uri="api/v0/cache-entries",
            method="POST",
            payload={
                "visibility": visibility,
                "version": self._edsl_version,
                "json_string": json.dumps(
                    {"key": cache_entry.key, "value": json.dumps(cache_entry.to_dict())}
                ),
            },
        )
        self._resolve_server_response(response)
        return response.json()

    def create_cache_entries(
        self, cache_entries: dict[str, CacheEntry], visibility: str = "unlisted"
    ) -> None:
        """
        Send a dictionary of CacheEntry objects to the server.
        """
        response = self._send_server_request(
            uri="api/v0/cache-entries/many",
            method="POST",
            payload={
                "visibility": visibility,
                "version": self._edsl_version,
                "json_string": json.dumps(
                    {k: json.dumps(v.to_dict()) for k, v in cache_entries.items()}
                ),
            },
        )
        self._resolve_server_response(response)
        return response.json()

    def get_cache_entries(
        self, exclude_keys: Optional[list[str]] = None
    ) -> list[CacheEntry]:
        """
        Return CacheEntry objects from the server.

        :param exclude_keys: exclude CacheEntry objects with these keys.
        """
        if exclude_keys is None:
            exclude_keys = []
        response = self._send_server_request(
            uri="api/v0/cache-entries/get-many",
            method="POST",
            payload={"keys": exclude_keys},
        )
        self._resolve_server_response(response)
        return [
            CacheEntry.from_dict(json.loads(v.get("json_string")))
            for v in response.json()
        ]

    ################
    # Error Message Methods
    ################
    def send_error_message(self, error_data: str) -> dict:
        """
        Send an error message to the server.
        """
        response = self._send_server_request(
            uri="api/v0/errors",
            method="POST",
            payload={"json_string": json.dumps(error_data)},
        )
        self._resolve_server_response(response)
        return response.json()

    ################
    # DUNDER METHODS
    ################
    def __repr__(self):
        """Return a string representation of the client."""
        return f"Client(api_key='{self.api_key}', url='{self.url}')"

    ################
    # EXPERIMENTAL
    ################
    async def remote_async_execute_model_call(
        self, model_dict: dict, user_prompt: str, system_prompt: str
    ) -> dict:
        url = self.url + "/inference/"
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
        url = f"{self.url}/api/v0/export_to_{platform}"
        if email:
            data = {"json_string": json.dumps({"survey": survey, "email": email})}
        else:
            data = {"json_string": json.dumps({"survey": survey, "email": email})}

        response_json = requests.post(url, data=json.dumps(data))

        return response_json


if __name__ == "__main__":
    from edsl.coop import Coop
    import uuid

    # init
    API_KEY = "b"
    coop = Coop(api_key=API_KEY)
    # basics
    coop
    coop.edsl_settings

    ##############
    # A. Objects
    ##############
    from uuid import uuid4
    from edsl import Agent, Cache, Jobs, QuestionMultipleChoice, Results, Survey

    OBJECTS = [
        ("agent", Agent),
        ("cache", Cache),
        ("job", Jobs),
        ("question", QuestionMultipleChoice),
        ("results", Results),
        ("survey", Survey),
    ]

    for object_type, cls in OBJECTS:
        print(f"Testing {object_type} objects")
        # 1. Delete existing objects
        existing_objects = coop.get_all(object_type)
        for item in existing_objects:
            coop.delete(object_type=object_type, uuid=item.get("uuid"))
        # 2. Create new objects
        example = cls.example()
        response_1 = coop.create(example)
        response_2 = coop.create(cls.example(), visibility="private")
        response_3 = coop.create(cls.example(), visibility="public")
        response_4 = coop.create(cls.example(), visibility="unlisted")
        # 3. Retrieve all objects
        objects = coop.get_all(object_type)
        assert len(objects) == 4
        # 4. Try to retrieve an item that does not exist
        try:
            coop.get(object_type=object_type, uuid=uuid4())
        except Exception as e:
            print(e)
        # 5. Try to retrieve all test objects by their uuids
        for response in [response_1, response_2, response_3, response_4]:
            coop.get(object_type=object_type, uuid=response.get("uuid"))
        # 6. Delete all objects
        for item in objects:
            coop.delete(object_type=object_type, uuid=item.get("uuid"))
        assert len(coop.get_all(object_type)) == 0

    ##############
    # B. Jobs
    ##############
    from edsl.jobs import Jobs

    # check jobs on server (should be an empty list)
    coop.jobs
    for job in coop.jobs:
        coop.delete(object_type="job", uuid=job.get("uuid"))
    # try to get a job that does not exist - should get an error
    coop.get(object_type="job", uuid=uuid.uuid4())
    coop.get(object_type="job", uuid=str(uuid.uuid4()))
    # now post some Jobs
    response = coop.create(Jobs.example())
    coop.create(Jobs.example(), visibility="private")
    coop.create(Jobs.example(), visibility="public")
    # check all jobs - there must be a few
    coop.jobs
    # get job by uuid
    for job in coop.jobs:
        print(
            f"Job: {job.get('uuid')}, Status: {job.get('status')}, Results: {job.get('results_uuid')}"
        )

    ##############
    # C. CacheEntries
    ##############
    from edsl.data.CacheEntry import CacheEntry

    # should be empty in the beginning
    coop.get_cache_entries()
    # now create one cache entry
    cache_entry = CacheEntry.example()
    coop.create_cache_entry(cache_entry)
    # see that if you try to create it again, you'll get the same uuid
    coop.create_cache_entry(cache_entry)
    # now get all your cache entries
    coop.get_cache_entries()
    coop.get_cache_entries(exclude_keys=[])
    coop.get_cache_entries(exclude_keys=["a"])
    # this will be empty
    coop.get_cache_entries(exclude_keys=[cache_entry.key])
    # now send many cache entries
    cache_entries = {}
    for i in range(10):
        cache_entry = CacheEntry.example(randomize=True)
        cache_entries[cache_entry.key] = cache_entry
    coop.create_cache_entries(cache_entries)

    ##############
    # D. Errors
    ##############
    coop = Coop()
    coop.api_key = "a"
    coop.send_error_message({"something": "This is an error message"})
    coop.api_key = None
    coop.send_error_message({"something": "This is an error message"})
