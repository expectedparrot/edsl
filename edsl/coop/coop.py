import aiohttp
import json
import os
import requests
from inspect import isclass
from requests.exceptions import ConnectionError
from typing import Any, Optional, Type, Union, Literal
from uuid import UUID
import edsl
from edsl import CONFIG
from edsl.agents import Agent, AgentList
from edsl.config import CONFIG
from edsl.data.Cache import Cache
from edsl.questions.QuestionBase import QuestionBase
from edsl.results import Results
from edsl.surveys import Survey
from edsl.data.CacheEntry import CacheEntry


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
            if method.upper() in ["GET", "DELETE"]:
                response = requests.request(
                    method, url, params=params, headers=self.headers
                )
            else:
                response = requests.request(
                    method, url, json=payload, headers=self.headers
                )
        except ConnectionError:
            raise ConnectionError("Could not connect to the server.")

        return response

    def _resolve_server_response(self, response: requests.Response) -> None:
        """
        Check the response from the server and raise appropriate errors.
        """
        if response.status_code >= 400:
            message = response.json().get("detail")
            if "Authorization" in message:
                message = "Please provide an Expected Parrot API key."
            raise Exception(message)

    ################
    # HELPER METHODS
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

    def _json_handle_none(self, value: Any) -> Any:
        """
        Helper function to handle None values in JSON serialization.
        - Returns "null" if value is None. If not, doesn't return anything else.
        """
        if value is None:
            return "null"

    def _get_edsl_version(self) -> str:
        """
        Return the version of the EDSL.
        """
        try:
            version = edsl.__version__
        except:
            version = None
        return version

    def _resolve_edsl_object(
        self,
        object: Union[
            Type[QuestionBase], QuestionBase, Survey, Agent, AgentList, Results
        ],
    ) -> tuple[str, str]:
        """
        Resolves an EDSL object or class to an (API_URI: str, object_type: str) tuple.
        """
        object_type = type(object) if not isclass(object) else object

        if issubclass(object_type, QuestionBase):
            return ("questions", "question")
        elif issubclass(object_type, Survey):
            return ("surveys", "survey")
        elif issubclass(object_type, Agent) or issubclass(object_type, AgentList):
            return ("agents", "agent")
        elif issubclass(object_type, Results):
            return ("results", "results")
        elif issubclass(object_type, Cache):
            return ("caches", "cache")
        else:
            raise ValueError("Incorrect or not supported object type")

    def _resolve_object_type(self, object_type: str) -> tuple[str, Type]:
        """
        Resolve an object_type string to an (API_URI: str, object_type: Type) tuple.
        """
        TYPE_MAP = {
            "question": ("questions", QuestionBase),
            "survey": ("surveys", Survey),
            "agent": ("agents", Agent),
            "results": ("results", Results),
            "cache": ("caches", Cache),
        }

        if object_type is None:
            raise ValueError("Please provide an `object_type`.")
        elif object_type not in TYPE_MAP:
            raise ValueError(
                f"Object type {object_type} not recognized. "
                f"Valid object types are: {', '.join(TYPE_MAP.keys())}"
            )

        return TYPE_MAP[object_type]

    def _resolve_uri(self, uri: str) -> tuple[str, Type]:
        """
        Resolve an API URI to an (API_URI: str, object_type: Type) tuple.
        """
        URI_MAP = {
            "questions": ("question", QuestionBase),
            "surveys": ("survey", Survey),
            "agents": ("agent", Agent),
            "results": ("results", Results),
            "caches": ("cache", Cache),
        }

        if uri is None:
            raise ValueError("Please provide a URI.")
        elif uri not in URI_MAP:
            raise ValueError(f"URI {uri} not recognized")

        return URI_MAP[uri]

    ################
    # OBJECT METHODS
    ################

    # ----------
    # A. CREATE
    # ----------
    def _create(
        self,
        object: Union[Type[QuestionBase], Survey, Agent, AgentList, Results],
        visibility: Literal["public", "unlisted", "private"] = "unlisted",
    ) -> dict:
        """
        Create an EDSL object in the Coop server.

        :param object: the EDSL object to be sent.
        :param visibility: the object's visibility (defaults to "unlisted").
        """

        uri, _ = self._resolve_edsl_object(object)
        response = self._send_server_request(
            uri=f"api/v0/{uri}",
            method="POST",
            payload={
                "json_string": json.dumps(
                    object.to_dict(), default=self._json_handle_none
                ),
                "visibility": visibility,
                "version": self._get_edsl_version(),
            },
        )
        self._resolve_server_response(response)
        response_json = response.json()
        url = f"{self.url}/explore/{uri}/{response_json['uuid']}"
        response_json["url"] = url
        return response_json

    def create(
        self,
        object: Union[Type[QuestionBase], Survey, Agent, AgentList, Results],
        visibility: Literal["public", "unlisted", "private"] = "unlisted",
        verbose: bool = False,
    ) -> dict:
        """
        Create an EDSL object in the Coop server.

        :param object: the EDSL object to be sent.
        :param visibility: the object's visibility (defaults to "unlisted").
        """
        response = self._create(object, visibility)
        if verbose:
            print(f"Object pushed to Coop - available at {response['url']}")
        return response

    # ----------
    # B. GET
    # ----------
    def _get(self, object_type_uri: str, uuid: Union[str, UUID]) -> dict:
        """
        Retrieve an EDSL object from the Coop server.
        """
        response = self._send_server_request(
            uri=f"api/v0/{object_type_uri}/{uuid}", method="GET"
        )
        self._resolve_server_response(response)
        return json.loads(response.json().get("json_string"))

    def get(
        self, object_type: str = None, uuid: Union[str, UUID] = None, url: str = None
    ) -> Union[Type[QuestionBase], Survey, Agent, AgentList, Results]:
        """
        Retrieve an EDSL object by its object type and UUID, or by its url.

        :param object_type: the type of object to retrieve.
        :param uuid: the uuid of the object either in str or UUID format.
        :param url: the url of the object.
        """
        if url:
            uri = url.split("/")[-2]
            object_type, cls = self._resolve_uri(uri)
            uuid = url.split("/")[-1]
        elif object_type and uuid:
            uri, cls = self._resolve_object_type(object_type)
        else:
            raise ValueError(
                "Please provide either an object type and a UUID, or a url."
            )

        json_dict = self._get(object_type_uri=uri, uuid=uuid)
        if object_type == "agent" and "agent_list" in json_dict:
            return AgentList.from_dict(json_dict)
        else:
            return cls.from_dict(json_dict)

    def _get_base(
        self,
        cls: Union[Type[QuestionBase], Survey, Agent, AgentList, Results],
        uuid: Union[str, UUID],
    ):
        """
        Used by the Base class to offer a get functionality.
        """
        _, object_type = self._resolve_edsl_object(cls)
        return self.get(object_type, uuid)

    # ----------
    # C. GET ALL
    # ----------
    @property
    def questions(self) -> list[dict[str, Union[int, QuestionBase]]]:
        """Retrieve all Questions."""
        response = self._send_server_request(uri="api/v0/questions", method="GET")
        self._resolve_server_response(response)
        questions = [
            {
                "question": QuestionBase.from_dict(json.loads(q["json_string"])),
                "uuid": q["uuid"],
                "version": q["version"],
                "visibility": q.get("visibility"),
                "url": f"{self.url}/explore/questions/{q['uuid']}",
            }
            for q in response.json()
        ]
        return questions

    @property
    def surveys(self) -> list[dict[str, Union[int, Survey]]]:
        """Retrieve all Surveys."""
        response = self._send_server_request(uri="api/v0/surveys", method="GET")
        self._resolve_server_response(response)
        surveys = [
            {
                "survey": Survey.from_dict(json.loads(s["json_string"])),
                "uuid": s["uuid"],
                "version": s["version"],
                "visibility": s.get("visibility"),
                "url": f"{self.url}/explore/surveys/{s['uuid']}",
            }
            for s in response.json()
        ]
        return surveys

    @property
    def agents(self) -> list[dict[str, Union[int, Agent, AgentList]]]:
        """Retrieve all Agents and AgentLists."""
        response = self._send_server_request(uri="api/v0/agents", method="GET")
        self._resolve_server_response(response)
        agents = []
        for a in response.json():
            agent_dict = json.loads(a.get("json_string"))
            if "agent_list" in agent_dict:
                agent = AgentList.from_dict(agent_dict)
            else:
                agent = Agent.from_dict(agent_dict)
            agents.append(
                {
                    "uuid": a.get("uuid"),
                    "agent": agent,
                    "version": a.get("version"),
                    "visibility": a.get("visibility"),
                    "url": f"{self.url}/explore/agents/{a['uuid']}",
                }
            )
        return agents

    @property
    def results(self) -> list[dict[str, Union[int, Results]]]:
        """Retrieve all Results."""
        response = self._send_server_request(uri="api/v0/results", method="GET")
        self._resolve_server_response(response)
        results = [
            {
                "uuid": r.get("uuid"),
                "results": Results.from_dict(json.loads(r.get("json_string"))),
                "version": r.get("version"),
                "visibility": r.get("visibility"),
                "url": f"{self.url}/explore/results/{r['uuid']}",
            }
            for r in response.json()
        ]
        return results

    @property
    def caches(self) -> list[dict[str, Union[int, Cache]]]:
        """Retrieve all Caches."""
        response = self._send_server_request(uri="api/v0/caches", method="GET")
        self._resolve_server_response(response)
        caches = [
            {
                "uuid": c.get("uuid"),
                "cache": Cache.from_dict(json.loads(c.get("json_string"))),
                "version": c.get("version"),
                "visibility": c.get("visibility"),
                "url": f"{self.url}/explore/caches/{c['uuid']}",
            }
            for c in response.json()
        ]
        return caches

    # ----------
    # D. DELETE
    # ----------
    def delete(self, object_type: str, uuid: Union[str, UUID]) -> dict:
        """
        Delete an EDSL object from the Coop server.

        :param object_type: the type of object to delete.
        :param uuid: the uuid of the object either in str or UUID format.
        """

        uri, _ = self._resolve_object_type(object_type)
        response = self._send_server_request(
            uri=f"api/v0/{uri}/{uuid}", method="DELETE"
        )
        self._resolve_server_response(response)
        return response.json()

    ################
    # CacheEntry Methods
    ################
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
                "version": self._get_edsl_version(),
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
                "version": self._get_edsl_version(),
                "json_string": json.dumps(
                    {k: json.dumps(v.to_dict()) for k, v in cache_entries.items()}
                ),
            },
        )
        # print(response.json())
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


if __name__ == "__main__":
    from edsl.coop import Coop
    import uuid

    API_KEY = "b"
    coop = Coop(api_key=API_KEY)

    # basics
    coop

    ##############
    # A. Objects
    ##############

    # ------------
    # A.1 Questions
    # ------------
    from edsl.questions import QuestionMultipleChoice
    from edsl.questions import QuestionCheckBox
    from edsl.questions import QuestionFreeText

    # check questions on server (should be an empty list)
    coop.questions
    for item in coop.questions:
        coop.delete(object_type="question", uuid=item.get("uuid"))
    # try to get a question that does not exist - should get an error
    coop.get(object_type="question", uuid=uuid.uuid4())
    coop.get(object_type="question", uuid=str(uuid.uuid4()))
    # now post some questions
    response = coop.create(QuestionMultipleChoice.example())
    coop.create(QuestionCheckBox.example(), visibility="private")
    coop.create(QuestionFreeText.example(), visibility="public")
    # check all questions - there must be three
    coop.questions
    # or get a question by its uuid
    coop.get(object_type="question", uuid=response.get("uuid"))
    # or by its url
    coop.get(url=response.get("url"))
    # delete the question
    coop.delete(object_type="question", uuid=response.get("uuid"))
    # check all questions - there must be two left
    coop.questions

    # ------------
    # A.2 Surveys
    # ------------
    from edsl.surveys import Survey

    # check surveys on server (should be an empty list)
    coop.surveys
    for survey in coop.surveys:
        coop.delete(object_type="survey", uuid=survey.get("uuid"))
    # try to get a survey that does not exist - should get an error
    coop.get(object_type="survey", uuid=uuid.uuid4())
    coop.get(object_type="survey", uuid=str(uuid.uuid4()))
    # now post some surveys
    response = coop.create(Survey.example())
    coop.create(Survey.example(), visibility="private")
    coop.create(Survey.example(), visibility="public")
    s = Survey().example()
    for i in range(10):
        q = QuestionFreeText.example()
        q.question_name = f"question_{i}"
        s.add_question(q)
    coop.create(s, visibility="public")
    # check all surveys - there must be three
    coop.surveys
    # or get survey by uuid
    coop.get(object_type="survey", uuid=response.get("uuid"))
    # or by its url
    coop.get(url=response.get("url"))
    # delete the survey
    coop.delete(object_type="survey", uuid=response.get("uuid"))
    # check all surveys - there must be two left
    coop.surveys

    # ------------
    # A.3 Agents
    # ------------
    from edsl.agents import Agent, AgentList

    # check agents on server (should be an empty list)
    coop.agents
    for agent in coop.agents:
        coop.delete(object_type="agent", uuid=agent.get("uuid"))
    # try to get an agent that does not exist - should get an error
    coop.get(object_type="agent", uuid=uuid.uuid4())
    coop.get(object_type="agent", uuid=str(uuid.uuid4()))
    # now post some agents
    response = coop.create(Agent.example())
    coop.create(Agent.example(), visibility="private")
    coop.create(Agent.example(), visibility="public")
    coop.create(
        Agent(traits={"hair_type": "curly", "skil_color": "white"}), visibility="public"
    )
    coop.create(AgentList.example())
    coop.create(AgentList.example(), visibility="private")
    coop.create(AgentList.example(), visibility="public")
    # check all agents - there must be a few
    coop.agents
    # or get agent by uuid
    coop.get(object_type="agent", uuid=response.get("uuid"))
    # or by its url
    coop.get(url=response.get("url"))
    # delete the agent
    coop.delete(object_type="agent", uuid=response.get("uuid"))
    # check all agents
    coop.agents

    # ------------
    # A.4 Results
    # ------------
    from edsl.results import Results

    # check results on server (should be an empty list)
    coop.results
    for results in coop.results:
        coop.delete(object_type="results", uuid=results.get("uuid"))
    # try to get a results that does not exist - should get an error
    coop.get(object_type="results", uuid=uuid.uuid4())
    coop.get(object_type="results", uuid=str(uuid.uuid4()))
    # now post some Results
    response = coop.create(Results.example())
    coop.create(Results.example(), visibility="private")
    coop.create(Results.example(), visibility="public")
    # check all results - there must be a few
    coop.results
    # or get results by uuid
    coop.get(object_type="results", uuid=response.get("uuid"))
    # or by its url
    coop.get(url=response.get("url"))
    # delete the results
    coop.delete(object_type="results", uuid=response.get("uuid"))
    # check all results
    coop.results

    # ------------
    # A.5 Caches
    # ------------
    from edsl.data import Cache

    # check caches on server (should be an empty list)
    coop.caches
    for cache in coop.caches:
        coop.delete(object_type="cache", uuid=cache.get("uuid"))
    # try to get a cache that does not exist - should get an error
    coop.get(object_type="cache", uuid=uuid.uuid4())
    coop.get(object_type="cache", uuid=str(uuid.uuid4()))
    # now post some Caches
    response = coop.create(Cache.example())
    coop.create(Cache.example(), visibility="private")
    coop.create(Cache.example(), visibility="public")
    # check all caches - there must be a few
    coop.caches
    # or get cache by uuid
    coop.get(object_type="cache", uuid=response.get("uuid"))
    # or by its url
    coop.get(url=response.get("url"))
    # delete the cache
    coop.delete(object_type="cache", uuid=response.get("uuid"))
    # check all caches
    coop.caches

    ##############
    # B. CacheEntries
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
    # E. ERROR MESSAGE
    ##############
    coop = Coop()
    coop.api_key = "a"
    coop.send_error_message({"something": "This is an error message"})
    coop.api_key = None
    coop.send_error_message({"something": "This is an error message"})
