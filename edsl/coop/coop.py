import json
import os
import requests
from requests.exceptions import ConnectionError
from typing import Any, Optional, Type, Union
from edsl import CONFIG
from edsl.agents import Agent, AgentList
from edsl.questions.QuestionBase import QuestionBase
from edsl.results import Results
from edsl.surveys import Survey
from edsl.data.CacheEntry import CacheEntry


api_url = {
    "development": "http://127.0.0.1:8000",
    "development-testrun": "http://127.0.0.1:8000",
    "production": os.getenv("EXPECTED_PARROT_API_URL"),
}


class Coop:
    """
    Client for the Expected Parrot API.
    """

    def __init__(self, api_key: str = None, run_mode: str = None) -> None:
        """Initialize the client."""
        self.api_key = api_key or os.getenv("EXPECTED_PARROT_API_KEY")
        self.run_mode = run_mode or CONFIG.EDSL_RUN_MODE
        self.run_mode = "production"
        self._api_key_is_valid()

    ################
    # BASIC METHODS
    ################
    def _api_key_is_valid(self) -> None:
        """
        Check if the API key is valid.
        """
        if not self.api_key:
            raise ValueError("API key is required.")
        if not isinstance(self.api_key, str):
            raise ValueError("API key must be a string.")
        response = self._send_server_request(uri="api/v0/validate-apikey", method="GET")
        self._resolve_server_response(response)

    @property
    def headers(self) -> dict:
        """
        Return the headers for the request.
        """
        return {"Authorization": f"Bearer {self.api_key}"}

    @property
    def url(self) -> str:
        """
        Return the URL for the request.
        """
        return api_url[self.run_mode]

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
            if self.run_mode == "production":
                raise ConnectionError("Could not connect to the server.")
            else:
                raise ConnectionError(
                    f"\n\n\nCould not connect to the server."
                    f"\nIs the server running? Try:"
                    f"\n   cd ~/coop && make fresh-db && make launch"
                )

        return response

    def _resolve_server_response(self, response: requests.Response) -> None:
        """
        Check the response from the server and raise appropriate errors.
        """
        if response.status_code >= 400:
            raise Exception(response.json().get("detail"))

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
    # EDSL METHODS
    ################
    def _edsl_object_to_uri(
        self, object: Union[Type[QuestionBase], Survey, Agent, Results]
    ) -> str:
        """
        Return the URI for the object type.
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
                "json_string": json.dumps(edsl_object.to_dict()),
                "public": public,
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
                "id": q.get("id"),
                "survey": Survey.from_dict(json.loads(q.get("json_string"))),
            }
            for q in response.json()
        ]
        return surveys

    @property
    def agents(self) -> list[dict[str, Union[int, Agent, AgentList]]]:
        """Retrieve all Agents and AgentLists."""
        response = self._send_server_request(uri="api/v0/agents", method="GET")
        self._resolve_server_response(response)
        agents = []
        for q in response.json():
            agent_dict = json.loads(q.get("json_string"))
            if "agent_list" in agent_dict:
                agent = AgentList.from_dict(agent_dict)
            else:
                agent = Agent.from_dict(agent_dict)
            agents.append({"id": q.get("id"), "agent": agent})
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
    # DUNDER METHODS
    ################
    def __repr__(self):
        """Return a string representation of the client."""
        return f"Client(api_key='{self.api_key}', run_mode='{self.run_mode}')"


if __name__ == "__main__":
    from edsl.coop import Coop

    API_KEY = "b"
    RUN_MODE = "development"
    coop = Coop(api_key=API_KEY, run_mode=RUN_MODE)

    # basics
    coop
    coop.headers
    coop.url

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
