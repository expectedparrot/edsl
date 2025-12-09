
from edsl.language_models.model import Model
from edsl.questions import QuestionFreeText as Q


def test_canned_response():
    m = Model("test", canned_response="poop")
    response = m.simple_ask(Q.example())
    assert response["message"][0]["text"] == "poop"
