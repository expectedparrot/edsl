import pytest
import time
from edsl import QuestionFreeText
from edsl.study import ObjectEntry


@pytest.fixture
def question_object():
    return QuestionFreeText.example()


def test_object_entry_initialization(question_object):
    oe = ObjectEntry("test_var", question_object, "This is a test object")
    assert oe.variable_name == "test_var"
    assert oe.object == question_object
    assert oe.description == "This is a test object"
    assert oe.coop_info is None
    assert oe.edsl_class_name == "QuestionFreeText"


def test_object_entry_to_dict(question_object):
    oe = ObjectEntry("test_var", question_object, "This is a test object")
    d = oe.to_dict()
    expected_dict = {
        "created_at": oe.created_at,
        "variable_name": "test_var",
        "object": question_object.to_dict(),
        "edsl_class_name": "QuestionFreeText",
        "description": "This is a test object",
        "coop_info": None,
    }
    assert d == expected_dict


def test_object_entry_from_dict(question_object):
    d = {
        "created_at": time.time(),
        "variable_name": "test_var",
        "object": question_object.to_dict(),
        "edsl_class_name": "QuestionFreeText",
        "description": "This is a test object",
        "coop_info": None,
    }
    oe = ObjectEntry.from_dict(d)
    assert oe.variable_name == "test_var"
    assert oe.object.to_dict() == question_object.to_dict()
    assert oe.description == "This is a test object"
    assert oe.coop_info is None
    assert oe.edsl_class_name == "QuestionFreeText"


def test_object_entry_hash(question_object):
    oe = ObjectEntry("test_var", question_object, "This is a test object")
    obj_hash = str(hash(question_object))
    assert oe.hash == obj_hash


# def test_object_entry_add_to_namespace(question_object):
#     oe = ObjectEntry("test_var", question_object, "This is a test object")
#     oe.add_to_namespace()
#     print(globals())
#     assert globals()["test_var"] == question_object
