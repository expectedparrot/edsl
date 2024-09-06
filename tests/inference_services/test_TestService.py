import pytest

from edsl import Model
from edsl import QuestionFreeText as Q


def test_canned_response():
    m = Model("test", canned_response="poop")
    assert m.simple_ask(Q.example()) == {"message": [{"text": "poop"}]}
