import pytest

from edsl import Model
from edsl import QuestionFreeText as Q


def test_canned_response():
    m = Model("test", canned_response="poop")
    response = m.simple_ask(Q.example())
    assert response["message"][0]["text"] == "poop"