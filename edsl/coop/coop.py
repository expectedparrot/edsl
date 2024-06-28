import aiohttp
import json
import os
import requests
from typing import Any, Optional, Union, Literal
from uuid import UUID
import edsl
from edsl import CONFIG, CacheEntry
from edsl.coop.utils import EDSLObject, ObjectRegistry, ObjectType, VisibilityType


class Coop:
    """
    Client for the Expected Parrot API.
    """

    def __init__(self, api_key: str = None, url: str = None) -> None:
        """
        Initialize the client.
        - Provide an API key directly, or through an env variable.
        - Provide a URL directly, or use the default one.
        """
        self.api_key = api_key or os.getenv("EXPECTED_PARROT_API_KEY")
        self.url = url or CONFIG.EXPECTED_PARROT_URL
        if self.url.endswith("/"):
            self.url = self.url[:-1]
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
        else:
            headers["Authorization"] = f"Bearer None"
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
            method = method.upper()
            if method in ["GET", "DELETE"]:
                response = requests.request(
                    method, url, params=params, headers=self.headers
                )
            elif method in ["POST", "PATCH"]:
                response = requests.request(
                    method, url, params=params, json=payload, headers=self.headers
                )
            else:
                raise Exception(f"Invalid {method=}.")
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
                print(message)
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
        description: Optional[str] = None,
        visibility: Optional[VisibilityType] = "unlisted",
    ) -> dict:
        """
        Create an EDSL object in the Coop server.
        """
        object_type = ObjectRegistry.get_object_type_by_edsl_class(object)
        object_page = ObjectRegistry.get_object_page_by_object_type(object_type)
        response = self._send_server_request(
            uri=f"api/v0/object",
            method="POST",
            payload={
                "description": description,
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
            "description": response_json.get("description"),
            "visibility": response_json.get("visibility"),
            "url": f"{self.url}/explore/{object_page}/{response_json.get('uuid')}",
        }

    def get(
        self,
        object_type: ObjectType = None,
        uuid: Union[str, UUID] = None,
        url: str = None,
        exec_profile=None,
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
        import time

        start = time.time()
        response = self._send_server_request(
            uri=f"api/v0/object",
            method="GET",
            params={"type": object_type, "uuid": uuid},
        )
        end = time.time()
        if exec_profile:
            print("Download exec time = ", end - start)
        self._resolve_server_response(response)
        json_string = response.json().get("json_string")
        start = time.time()
        res_object = edsl_class.from_dict(json.loads(json_string))
        end = time.time()
        if exec_profile:
            print("Creating object exec time = ", end - start)
        return res_object

    def _get_base(
        self,
        cls: EDSLObject,
        uuid: Union[str, UUID],
        exec_profile=None,
    ) -> EDSLObject:
        """
        Used by the Base class to offer a get functionality.
        """
        object_type = ObjectRegistry.get_object_type_by_edsl_class(cls)
        return self.get(object_type, uuid, exec_profile=exec_profile)

    def get_all(self, object_type: ObjectType) -> list[EDSLObject]:
        """
        Retrieve all objects of a certain type associated with the user.
        """
        edsl_class = ObjectRegistry.object_type_to_edsl_class.get(object_type)
        object_page = ObjectRegistry.get_object_page_by_object_type(object_type)
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
                "description": o.get("description"),
                "visibility": o.get("visibility"),
                "url": f"{self.url}/explore/{object_page}/{o.get('uuid')}",
            }
            for o in response.json()
        ]
        return objects

    def delete(self, object_type: ObjectType, uuid: Union[str, UUID]) -> dict:
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

    def _delete_base(
        self,
        cls: EDSLObject,
        uuid: Union[str, UUID],
    ) -> dict:
        """
        Used by the Base class to offer a delete functionality.
        """
        object_type = ObjectRegistry.get_object_type_by_edsl_class(cls)
        return self.delete(object_type, uuid)

    def patch(
        self,
        object_type: ObjectType,
        uuid: Union[str, UUID],
        description: Optional[str] = None,
        value: Optional[EDSLObject] = None,
        visibility: Optional[VisibilityType] = None,
    ) -> dict:
        """
        Change the attributes of an uploaded object
        - Only supports visibility for now
        """
        if description is None and visibility is None and value is None:
            raise Exception("Nothing to patch.")
        if value is not None:
            value_type = ObjectRegistry.get_object_type_by_edsl_class(value)
            if value_type != object_type:
                raise Exception(f"Object type mismatch: {object_type=} {value_type=}")
        response = self._send_server_request(
            uri=f"api/v0/object",
            method="PATCH",
            params={"type": object_type, "uuid": uuid},
            payload={
                "description": description,
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

    def _patch_base(
        self,
        cls: EDSLObject,
        uuid: Union[str, UUID],
        description: Optional[str] = None,
        value: Optional[EDSLObject] = None,
        visibility: Optional[VisibilityType] = None,
    ) -> dict:
        """
        Used by the Base class to offer a patch functionality.
        """
        object_type = ObjectRegistry.get_object_type_by_edsl_class(cls)
        return self.patch(object_type, uuid, description, value, visibility)

    ################
    # Remote Cache
    ################
    def remote_cache_create(
        self,
        cache_entry: CacheEntry,
        visibility: VisibilityType = "private",
    ) -> dict:
        """
        Create a single remote cache entry.
        """
        response = self._send_server_request(
            uri="api/v0/remote-cache",
            method="POST",
            payload={
                "json_string": json.dumps(cache_entry.to_dict()),
                "version": self._edsl_version,
                "visibility": visibility,
            },
        )
        self._resolve_server_response(response)
        response_json = response.json()
        created_entry_count = response_json.get("created_entry_count", 0)
        if created_entry_count > 0:
            self.remote_cache_create_log(
                response,
                description="Upload new cache entries to server",
                cache_entry_count=created_entry_count,
            )
        return response.json()

    def remote_cache_create_many(
        self,
        cache_entries: list[CacheEntry],
        visibility: VisibilityType = "private",
    ) -> dict:
        """
        Create many remote cache entries.
        """
        payload = [
            {
                "json_string": json.dumps(c.to_dict()),
                "version": self._edsl_version,
                "visibility": visibility,
            }
            for c in cache_entries
        ]
        response = self._send_server_request(
            uri="api/v0/remote-cache/many",
            method="POST",
            payload=payload,
        )
        self._resolve_server_response(response)
        response_json = response.json()
        created_entry_count = response_json.get("created_entry_count", 0)
        if created_entry_count > 0:
            self.remote_cache_create_log(
                response,
                description="Upload new cache entries to server",
                cache_entry_count=created_entry_count,
            )
        return response.json()

    def remote_cache_get(
        self,
        exclude_keys: Optional[list[str]] = None,
    ) -> list[CacheEntry]:
        """
        Get all remote cache entries.
        - optional exclude_keys: exclude CacheEntry objects with these keys.
        """
        if exclude_keys is None:
            exclude_keys = []
        response = self._send_server_request(
            uri="api/v0/remote-cache/get-many",
            method="POST",
            payload={"keys": exclude_keys},
        )
        self._resolve_server_response(response)
        return [
            CacheEntry.from_dict(json.loads(v.get("json_string")))
            for v in response.json()
        ]

    def remote_cache_get_diff(
        self,
        client_cacheentry_keys: list[str],
    ) -> dict:
        """
        Get the difference between local and remote cache entries for a user.
        """
        response = self._send_server_request(
            uri="api/v0/remote-cache/get-diff",
            method="POST",
            payload={"keys": client_cacheentry_keys},
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
            self.remote_cache_create_log(
                response,
                description="Download missing cache entries to client",
                cache_entry_count=downloaded_entry_count,
            )
        return response_dict

    def remote_cache_clear(self) -> dict:
        """
        Clear all remote cache entries.
        """
        response = self._send_server_request(
            uri="api/v0/remote-cache/delete-all",
            method="DELETE",
        )
        self._resolve_server_response(response)
        response_json = response.json()
        deleted_entry_count = response_json.get("deleted_entry_count", 0)
        if deleted_entry_count > 0:
            self.remote_cache_create_log(
                response,
                description="Clear cache entries",
                cache_entry_count=deleted_entry_count,
            )
        return response.json()

    def remote_cache_create_log(
        self, response: requests.Response, description: str, cache_entry_count: int
    ) -> Union[dict, None]:
        """
        If a remote cache action has been completed successfully,
        log the action.
        """
        if 200 <= response.status_code < 300:
            log_response = self._send_server_request(
                uri="api/v0/remote-cache-log",
                method="POST",
                payload={
                    "description": description,
                    "cache_entry_count": cache_entry_count,
                },
            )
            self._resolve_server_response(log_response)
            return response.json()

    def remote_cache_clear_log(self) -> dict:
        """
        Clear all remote cache log entries.
        """
        response = self._send_server_request(
            uri="api/v0/remote-cache-log/delete-all",
            method="DELETE",
        )
        self._resolve_server_response(response)
        return response.json()

    ################
    # Remote Inference
    ################
    def remote_inference_get(self, job_uuid: str) -> dict:
        """
        Get the results of a remote inference job.
        """
        response = self._send_server_request(
            uri="api/v0/remote-inference",
            method="GET",
            params={"uuid": job_uuid},
        )
        self._resolve_server_response(response)
        data = response.json()
        return {
            "jobs_uuid": data.get("jobs_uuid"),
            "results_uuid": data.get("results_uuid"),
            "results_url": "TO BE ADDED",
            "status": data.get("status"),
            "reason": data.get("reason"),
            "price": data.get("price"),
            "version": data.get("version"),
        }

    ################
    # Remote Errors
    ################
    def error_create(self, error_data: str) -> dict:
        """
        Send an error message to the server.
        """
        response = self._send_server_request(
            uri="api/v0/errors",
            method="POST",
            payload={
                "json_string": json.dumps(error_data),
                "version": self._edsl_version,
            },
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
            data = {"json_string": json.dumps({"survey": survey, "email": ""})}

        response_json = requests.post(url, headers=self.headers, data=json.dumps(data))

        return response_json


if __name__ == "__main__":
    from edsl.coop import Coop

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
    from edsl import (
        Agent,
        AgentList,
        Cache,
        Jobs,
        Notebook,
        QuestionMultipleChoice,
        Results,
        Scenario,
        ScenarioList,
        Survey,
    )

    OBJECTS = [
        ("agent", Agent),
        ("agent_list", AgentList),
        ("cache", Cache),
        ("job", Jobs),
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
            coop.delete(object_type=object_type, uuid=item.get("uuid"))
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
            coop.get(object_type=object_type, uuid=uuid4())
        except Exception as e:
            print(e)
        # 5. Try to retrieve all test objects by their uuids
        for response in [response_1, response_2, response_3, response_4]:
            coop.get(object_type=object_type, uuid=response.get("uuid"))
        # 6. Change visibility of all objects
        for item in objects:
            coop.patch(
                object_type=object_type, uuid=item.get("uuid"), visibility="private"
            )
        # 6. Change description of all objects
        for item in objects:
            coop.patch(
                object_type=object_type, uuid=item.get("uuid"), description="hey"
            )
        # 7. Delete all objects
        for item in objects:
            coop.delete(object_type=object_type, uuid=item.get("uuid"))
        assert len(coop.get_all(object_type)) == 0

    # a simple example
    from edsl import Coop, QuestionMultipleChoice, QuestionFreeText

    coop = Coop(api_key="b")
    response = QuestionMultipleChoice.example().push()
    QuestionMultipleChoice.pull(response.get("uuid"))
    coop.patch(object_type="question", uuid=response.get("uuid"), visibility="public")
    coop.patch(
        object_type="question",
        uuid=response.get("uuid"),
        description="crazy new description",
    )
    coop.patch(
        object_type="question",
        uuid=response.get("uuid"),
        value=QuestionFreeText.example(),
    )
    coop.delete(object_type="question", uuid=response.get("uuid"))

    ##############
    # B. Remote Cache
    ##############
    from edsl.data.CacheEntry import CacheEntry

    # clear
    coop.remote_cache_clear()
    assert coop.remote_cache_get() == []
    # create one remote cache entry
    cache_entry = CacheEntry.example()
    cache_entry.to_dict()
    coop.remote_cache_create(cache_entry)
    # create many remote cache entries
    cache_entries = [CacheEntry.example(randomize=True) for _ in range(10)]
    coop.remote_cache_create_many(cache_entries)
    # get all remote cache entries
    coop.remote_cache_get()
    coop.remote_cache_get(exclude_keys=[])
    coop.remote_cache_get(exclude_keys=["a"])
    exclude_keys = [cache_entry.key for cache_entry in cache_entries]
    coop.remote_cache_get(exclude_keys)
    # clear
    coop.remote_cache_clear()
    coop.remote_cache_get()

    ##############
    # C. Remote Inference
    ##############
    from edsl.jobs import Jobs

    # check jobs on server (should be an empty list)
    coop.get_all("job")
    for job in coop.get_all("job"):
        coop.delete(object_type="job", uuid=job.get("uuid"))
    # post a job
    response = coop.create(Jobs.example())
    # get job and results
    coop.remote_inference_get(response.get("uuid"))
    coop.get(
        object_type="results",
        uuid=coop.remote_inference_get(response.get("uuid")).get("results_uuid"),
    )

    ##############
    # D. Errors
    ##############
    from edsl import Coop

    coop = Coop()
    coop.api_key = "a"
    coop.error_create({"something": "This is an error message"})
    coop.api_key = None
    coop.error_create({"something": "This is an error message"})
