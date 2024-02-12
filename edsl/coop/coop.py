import json
import requests
from typing import Type
from edsl import CONFIG
from edsl.exceptions import InvalidApiKeyError
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

    def _is_valid_api_key(self, response: dict):
        """Checks if the API key is invalid and raises an error if so."""
        if (
            isinstance(response, dict)
            and response.get("detail") == "The api key you provided is invalid"
        ):
            raise InvalidApiKeyError()

    # QUESTIONS METHODS
    @property
    def questions(self) -> list[Type[Question]]:
        """Returns all questions the user has sent to the coop."""
        url = f"{self.url}/api/v0/questions/"
        response = requests.get(url, headers=self.headers).json()
        self._is_valid_api_key(response)
        questions = [
            Question.from_dict(json.loads(q.get("json_string"))) for q in response
        ]
        return questions

    def get_question(self, question_id: int) -> Type[Question]:
        """Returns a question from the coop."""
        url = f"{self.url}/api/v0/questions/{question_id}"
        response = requests.get(url, headers=self.headers).json()
        self._is_valid_api_key(response)
        if response.get("detail") == "Object not found":
            return None
        else:
            return Question.from_dict(json.loads(response.get("json_string")))

    def post_question(self, question: Type[Question]) -> dict:
        """Sends a question to the coop."""
        url = f"{self.url}/api/v0/questions"
        payload = {"json_string": json.dumps(question.to_dict())}
        response = requests.post(url, json=payload, headers=self.headers)
        self._is_valid_api_key(response)
        return response.json()

    def delete_question(self, question_id: int) -> dict:
        """Deletes a question from the coop."""
        url = f"{self.url}/api/v0/questions/{question_id}"
        response = requests.delete(url, headers=self.headers)
        self._is_valid_api_key(response)
        return response.json()


if __name__ == "__main__":
    from edsl.coop import Coop
    from edsl.questions import QuestionMultipleChoice
    from edsl.questions import QuestionCheckBox
    from edsl.questions import QuestionFreeText

    API_KEY = "_j6wrtj6CB6iIPvoFJaYM4RbZRm0XQvfPJyO68s8FcI"
    RUN_MODE = "development"
    coop = Coop(api_key=API_KEY, run_mode=RUN_MODE)

    # basics
    coop
    coop.headers
    coop.url

    # check jobs on server (should be an empty list)
    coop.questions

    # get a question that does not exist (should return None)
    coop.get_question(question_id=1)

    # now post a Question
    coop.post_question(QuestionMultipleChoice.example())
    coop.post_question(QuestionCheckBox.example())
    coop.post_question(QuestionFreeText.example())

    # check all questions
    coop.questions

    # or get question by id
    coop.get_question(question_id=1)

    # delete the question
    coop.delete_question(question_id=1)

    # check all questions (should be an empty list)
    coop.questions
