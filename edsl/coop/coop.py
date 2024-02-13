import json
import requests
from typing import Any, Optional, Type, Union
from edsl import CONFIG
from edsl.questions import Question


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

    def get_question(self, question_id: int) -> Type[Question]:
        """Retrieves a Question object by id."""
        response = self._send_server_request(
            uri=f"api/v0/questions/{question_id}", method="GET"
        )
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

    def delete_question(self, question_id: int) -> dict:
        """Deletes a question from the coop."""
        response = self._send_server_request(
            uri=f"api/v0/questions/{question_id}", method="DELETE"
        )
        self._resolve_server_response(response)
        return response.json()


if __name__ == "__main__":
    from edsl.coop import Coop
    from edsl.questions import QuestionMultipleChoice
    from edsl.questions import QuestionCheckBox
    from edsl.questions import QuestionFreeText

    API_KEY = "X27Nqvl4oPxd_5Dt6oJbF9r2Myh_44Pit_851Ap7V7w"
    RUN_MODE = "development"
    coop = Coop(api_key=API_KEY, run_mode=RUN_MODE)

    # basics
    coop
    coop.headers
    coop.url

    # check jobs on server (should be an empty list)
    coop.questions
    for question in coop.questions:
        coop.delete_question(question.get("id"))

    # get a question that does not exist (should return None)
    coop.get_question(question_id=1)

    # now post a Question
    coop.create_question(QuestionMultipleChoice.example())
    coop.create_question(QuestionCheckBox.example(), public=False)
    coop.create_question(QuestionFreeText.example(), public=True)

    # check all questions
    coop.questions

    # or get question by id
    coop.get_question(question_id=1)

    # delete the question
    coop.delete_question(question_id=2)

    # check all questions (should be an empty list)
    coop.questions
