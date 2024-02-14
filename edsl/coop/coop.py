import json
import requests
from typing import Any, Optional, Type, Union
from edsl import CONFIG
from edsl.questions import Question
from edsl.surveys import Survey


api_url = {
    "development": "http://127.0.0.1:8000",
    "production": "https://api.goemeritus.com",
}


class Coop:
    def __init__(self, api_key: str = None, run_mode: str = None) -> None:
        self.api_key = api_key or CONFIG.EMERITUS_API_KEY
        self.run_mode = run_mode or CONFIG.EDSL_RUN_MODE

    def __repr__(self):
        return f"Client(api_key='{self.api_key}', run_mode='{self.run_mode}')"

    @property
    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}

    @property
    def url(self) -> str:
        return api_url[self.run_mode]

    def _send_server_request(
        self,
        uri: str,
        method: str,
        payload: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> requests.Response:
        """Sends a request to the server and returns the response."""
        url = f"{self.url}/{uri}"

        if method.upper() in ["GET", "DELETE"]:
            response = requests.request(
                method, url, params=params, headers=self.headers
            )
        else:
            response = requests.request(method, url, json=payload, headers=self.headers)

        return response

    def _resolve_server_response(self, response: requests.Response) -> None:
        """Checks the response from the server and raises appropriate errors."""
        if response.status_code >= 400:
            raise Exception(response.json().get("detail"))

    # QUESTIONS METHODS
    def create_question(self, question: Type[Question], public: bool = False) -> dict:
        """
        Creates a Question object.
        - `question`: the EDSL Question to be sent.
        - `public`: whether the question should be public (defaults to False)
        """
        response = self._send_server_request(
            uri="api/v0/questions",
            method="POST",
            payload={"json_string": json.dumps(question.to_dict()), "public": public},
        )
        self._resolve_server_response(response)
        return response.json()

    def get_question(self, id: int) -> Type[Question]:
        """Retrieves a Question object by id."""
        response = self._send_server_request(uri=f"api/v0/questions/{id}", method="GET")
        self._resolve_server_response(response)
        return Question.from_dict(json.loads(response.json().get("json_string")))

    @property
    def questions(self) -> list[dict[str, Union[int, Question]]]:
        """Retrieves all Questions."""
        response = self._send_server_request(uri="api/v0/questions", method="GET")
        self._resolve_server_response(response)
        questions = [
            {
                "id": q.get("id"),
                "question": Question.from_dict(json.loads(q.get("json_string"))),
            }
            for q in response.json()
        ]
        return questions

    def delete_question(self, id: int) -> dict:
        """Deletes a question from the coop."""
        response = self._send_server_request(
            uri=f"api/v0/questions/{id}", method="DELETE"
        )
        self._resolve_server_response(response)
        return response.json()

    # Surveys METHODS
    def create_survey(self, survey: Type[Survey], public: bool = False) -> dict:
        """
        Creates a Question object.
        - `survey`: the EDSL Survey to be sent.
        - `public`: whether the survey should be public (defaults to False)
        """
        response = self._send_server_request(
            uri="api/v0/surveys",
            method="POST",
            payload={"json_string": json.dumps(survey.to_dict()), "public": public},
        )
        self._resolve_server_response(response)
        return response.json()

    def get_survey(self, id: int) -> Type[Survey]:
        """Retrieves a Survey object by id."""
        response = self._send_server_request(uri=f"api/v0/surveys/{id}", method="GET")
        self._resolve_server_response(response)
        return Survey.from_dict(json.loads(response.json().get("json_string")))

    @property
    def surveys(self) -> list[dict[str, Union[int, Survey]]]:
        """Retrieves all Surveys."""
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

    def delete_survey(self, id: int) -> dict:
        """Deletes a Survey from the coop."""
        response = self._send_server_request(
            uri=f"api/v0/surveys/{id}", method="DELETE"
        )
        self._resolve_server_response(response)
        return response.json()


if __name__ == "__main__":
    from edsl.coop import Coop

    API_KEY = "p-llmNVgNM8pnzCWZQ6-sDCdlMgRgithISctb_9yzqU"
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
    coop.get_question(id=1)

    # now post a Question
    coop.create_question(QuestionMultipleChoice.example())
    coop.create_question(QuestionCheckBox.example(), public=False)
    coop.create_question(QuestionFreeText.example(), public=True)

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
    coop.create_survey(Survey.example())
    coop.create_survey(Survey.example(), public=False)
    coop.create_survey(Survey.example(), public=True)

    # check all surveys
    coop.surveys

    # or get survey by id
    coop.get_survey(id=1)

    # delete the survey
    coop.delete_survey(id=1)

    # check all surveys
    coop.surveys
