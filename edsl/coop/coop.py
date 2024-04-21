import json
import os
from edsl.config import CONFIG
import aiohttp
import asyncio

import requests
from requests.exceptions import ConnectionError
from typing import Any, Optional, Type, Union, Literal
import edsl
from edsl import CONFIG
from edsl.agents import Agent, AgentList
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
    def _json_handle_none(value: Any) -> Any:
        """
        Helper function to handle None values in JSON serialization.
        """
        if value is None:
            return "null"
        else:
            return value

    def _get_edsl_version(self) -> str:
        """
        Return the version of the EDSL.
        """
        try:
            version = edsl.__version__
        except:
            version = None
        return version

    def _edsl_object_to_uri(
        self, object: Union[Type[QuestionBase], Survey, Agent, Results]
    ) -> str:
        """
        Return the URI for an object type.
        """
        if isinstance(object, QuestionBase):
            return "questions"
        elif isinstance(object, Survey):
            return "surveys"
        elif isinstance(object, Agent) or isinstance(object, AgentList):
            return "agents"
        elif isinstance(object, Results):
            return "results"
        else:
            raise ValueError("Incorrect or not supported object type")

    async def remote_async_execute_model_call(
        self, model_dict: dict, user_prompt: str, system_prompt: str
    ) -> dict:
        url = CONFIG.get("EXPECTED_PARROT_URL") + "/inference/"
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

    ################
    # OBJECT METHODS
    ################

    # -----------------
    # A. CREATE METHODS
    # -----------------
    def _create(
        self,
        edsl_object: Union[Type[QuestionBase], Survey, Agent, AgentList, Results],
        public: bool = False,
    ) -> dict:
        """
        Create an EDSL object in the Coop server.

        :param edsl_object: the EDSL object to be sent.
        :param public: whether the object should be public (defaults to False).
        """

        uri = self._edsl_object_to_uri(edsl_object)
        response = self._send_server_request(
            uri=f"api/v0/{uri}",
            method="POST",
            payload={
                "json_string": json.dumps(
                    edsl_object.to_dict(), default=self._json_handle_none
                ),
                "public": public,
                "version": self._get_edsl_version(),
            },
        )
        self._resolve_server_response(response)
        return response.json()

    def create(
        self,
        object: Union[Type[QuestionBase], Survey, Agent, AgentList, Results],
        public: bool = False,
    ):
        """
        Create an EDSL object in the Coop server.

        :param object: the EDSL object to be sent.
        :param public: whether the object should be public (defaults to False)
        """
        return self._create(object, public)

    def web(
        self,
        survey: dict,
        platform: Literal[
            "google_forms", "lime_survey", "survey_monkey"
        ] = "lime_survey",
        email=None,
    ):
        base_url = self.url

        if base_url is None:
            return {"status": "error", "error": "EXPECTED_PARROT_API_URL not set"}

        url = f"{base_url}/api/v0/export_to_{platform}"
        if email:
            data = {"json_string": json.dumps({"survey": survey, "email": email})}
        else:
            data = {"json_string": json.dumps({"survey": survey, "email": email})}

        response_json = requests.post(url, data=json.dumps(data))

        return response_json

    # -----------------
    # B. GET METHODS
    # -----------------
    def _get(self, object_type: str, id: int) -> dict:
        """
        Retrieve an EDSL object from the Coop server.
        """
        response = self._send_server_request(
            uri=f"api/v0/{object_type}/{id}", method="GET"
        )
        self._resolve_server_response(response)
        return json.loads(response.json().get("json_string"))

    def get_question(self, id: int) -> Type[QuestionBase]:
        """
        Retrieve a Question object by its id.
        """
        json_dict = self._get("questions", id)
        return QuestionBase.from_dict(json_dict)

    def get_survey(self, id: int) -> Type[Survey]:
        """
        Retrieve a Survey object by its id.
        """
        json_dict = self._get("surveys", id)
        return Survey.from_dict(json_dict)

    def get_agent(self, id: int) -> Union[Agent, AgentList]:
        """
        Retrieve an Agent or AgentList object by id.
        """
        json_dict = self._get("agents", id)
        if "agent_list" in json_dict:
            return AgentList.from_dict(json_dict)
        else:
            return Agent.from_dict(json_dict)

    def get_results(self, id: int) -> Results:
        """Retrieve a Results object by id."""
        json_dict = self._get("results", id)
        return Results.from_dict(json_dict)

    def get(
        self, object_type: str, id: int
    ) -> Union[Type[QuestionBase], Survey, Agent, AgentList, Results]:
        """
        Retrieve an EDSL object by its id.

        :param object_type: the type of object to retrieve.
        :param id: the id of the object.
        """
        if object_type in {"question", "questions"}:
            return self.get_question(id)
        elif object_type in {"survey", "surveys"}:
            return self.get_survey(id)
        elif object_type in {"agent", "agents"}:
            return self.get_agent(id)
        elif object_type == "results":
            return self.get_results(id)
        else:
            raise ValueError("Object type not recognized")

    def _get_base(self, cls, id):
        """
        Used by the Base class to offer a get functionality.
        """
        if issubclass(cls, QuestionBase):
            return self.get_question(id)
        elif cls == Survey:
            return self.get_survey(id)
        elif cls == Agent or cls == AgentList:
            return self.get_agent(id)
        elif cls == Results:
            return self.get_results(id)
        else:
            raise ValueError("Class type not recognized")

    # -----------------
    # C. GET ALL METHODS
    # -----------------
    @property
    def questions(self) -> list[dict[str, Union[int, QuestionBase]]]:
        """Retrieve all Questions."""
        response = self._send_server_request(uri="api/v0/questions", method="GET")
        self._resolve_server_response(response)
        questions = [
            {
                "id": q.get("id"),
                "question": QuestionBase.from_dict(json.loads(q.get("json_string"))),
                "version": q.get("version"),
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
                "id": s.get("id"),
                "survey": Survey.from_dict(json.loads(s.get("json_string"))),
                "version": s.get("version"),
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
                    "id": a.get("id"),
                    "agent": agent,
                    "version": a.get("version"),
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
                "id": r.get("id"),
                "results": Results.from_dict(json.loads(r.get("json_string"))),
                "version": r.get("version"),
            }
            for r in response.json()
        ]
        return results

    # -----------------
    # D. DELETE METHODS
    # -----------------
    def delete_question(self, id: int) -> dict:
        """Delete a question from the Coop."""
        response = self._send_server_request(
            uri=f"api/v0/questions/{id}", method="DELETE"
        )
        self._resolve_server_response(response)
        return response.json()

    def delete_survey(self, id: int) -> dict:
        """Delete a Survey from the coop."""
        response = self._send_server_request(
            uri=f"api/v0/surveys/{id}", method="DELETE"
        )
        self._resolve_server_response(response)
        return response.json()

    def delete_agent(self, id: int) -> dict:
        """Delete an Agent or AgentList from the coop."""
        response = self._send_server_request(uri=f"api/v0/agents/{id}", method="DELETE")
        self._resolve_server_response(response)
        return response.json()

    def delete_results(self, id: int) -> dict:
        """Delete a Results object from the coop."""
        response = self._send_server_request(
            uri=f"api/v0/results/{id}", method="DELETE"
        )
        self._resolve_server_response(response)
        return response.json()

    ################
    # CACHE METHODS
    ################
    def create_cache_entry(self, cache_entry: CacheEntry) -> dict:
        """
        Create a CacheEntry object.
        """
        response = self._send_server_request(
            uri="api/v0/cache/create-cache-entry",
            method="POST",
            payload={
                "json_string": json.dumps(
                    {"key": cache_entry.key, "value": json.dumps(cache_entry.to_dict())}
                )
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
            uri="api/v0/cache/get-cache-entries",
            method="POST",
            payload={"json_string": json.dumps(exclude_keys)},
        )
        self._resolve_server_response(response)
        return [
            CacheEntry.from_dict(json.loads(v.get("json_string")))
            for v in response.json()
        ]

    def send_cache_entries(self, cache_entries: dict[str, CacheEntry]) -> None:
        """
        Send a dictionary of CacheEntry objects to the server.
        """
        response = self._send_server_request(
            uri="api/v0/cache/create-cache-entries",
            method="POST",
            payload={
                "json_string": json.dumps(
                    {k: json.dumps(v.to_dict()) for k, v in cache_entries.items()}
                )
            },
        )
        self._resolve_server_response(response)
        return response.json()

    ################
    # ERROR MESSAGE METHODS
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

    API_KEY = "b"
    coop = Coop(api_key=API_KEY)

    # basics
    coop

    ##############
    # A. QUESTIONS
    ##############
    from edsl.questions import QuestionMultipleChoice
    from edsl.questions import QuestionCheckBox
    from edsl.questions import QuestionFreeText

    # check questions on server (should be an empty list)
    coop.questions
    for question in coop.questions:
        coop.delete_question(question.get("id"))

    # get a question that does not exist (should return None)
    coop.get_question(id=1000)

    # now post a Question
    coop.create(QuestionMultipleChoice.example())
    coop.create(QuestionCheckBox.example(), public=False)
    coop.create(QuestionFreeText.example(), public=True)

    # check all questions
    coop.questions

    # or get question by id
    coop.get_question(id=1)
    # alternatively
    coop.get(object_type="question", id=1)

    # delete the question
    coop.delete_question(id=1)

    # check all questions
    coop.questions

    ##############
    # B. Surveys
    ##############
    from edsl.surveys import Survey

    # check surveys on server (should be an empty list)
    coop.surveys
    for survey in coop.surveys:
        coop.delete_survey(survey.get("id"))

    # get a survey that does not exist (should return None)
    coop.get_survey(id=1)

    # now post a Survey
    coop.create(Survey.example())
    coop.create(Survey.example(), public=False)
    coop.create(Survey.example(), public=True)
    coop.create(Survey(), public=True)
    s = Survey().example()
    for i in range(10):
        q = QuestionFreeText.example()
        q.question_name = f"question_{i}"
        s.add_question(q)
    coop.create(s, public=True)

    # check all surveys
    coop.surveys

    # or get survey by id
    coop.get_survey(id=1)

    # delete the survey
    coop.delete_survey(id=1)

    # check all surveys
    coop.surveys

    ##############
    # C. Agents and AgentLists
    ##############
    from edsl.agents import Agent, AgentList

    # check agents on server (should be an empty list)
    coop.agents
    for agent in coop.agents:
        coop.delete_agent(agent.get("id"))

    # get an agent that does not exist (should return None)
    coop.get_agent(id=2)

    # now post an Agent
    coop.create(Agent.example())
    coop.create(Agent.example(), public=False)
    coop.create(Agent.example(), public=True)
    coop.create(
        Agent(traits={"hair_type": "curly", "skil_color": "white"}), public=True
    )
    coop.create(AgentList.example())
    coop.create(AgentList.example(), public=False)
    coop.create(AgentList.example(), public=True)

    # check all agents
    coop.agents

    # or get agent by id
    coop.get_agent(id=1)

    # delete the agent
    coop.delete_agent(id=1)

    # check all agents
    coop.agents

    ##############
    # D. Results
    ##############
    from edsl.results import Results

    # check results on server (should be an empty list)
    len(coop.results)
    for results in coop.results:
        coop.delete_results(results.get("id"))

    # get a result that does not exist (should return None)
    coop.get_results(id=2)

    # now post a Results
    coop.create(Results.example())
    coop.create(Results.example(), public=False)
    coop.create(Results.example(), public=True)

    # check all results
    coop.results

    # or get results by id
    coop.get_results(id=1)

    # delete the results
    coop.delete_results(id=1)

    # check all results
    coop.results

    ##############
    # E. CACHE
    ##############
    from edsl.data.CacheEntry import CacheEntry

    # should be empty in the beginning
    coop.get_cache_entries()
    # now create one cache entry
    cache_entry = CacheEntry.example()
    coop.create_cache_entry(cache_entry)
    # see that if you try to create it again, you'll get the same id
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
    coop.send_cache_entries(cache_entries)

    ##############
    # E. ERROR MESSAGE
    ##############
    coop = Coop()
    coop.api_key = "a"
    coop.send_error_message({"something": "This is an error message"})
    coop.api_key = None
    coop.send_error_message({"something": "This is an error message"})
