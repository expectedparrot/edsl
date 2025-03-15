from edsl.questions import QuestionMultipleChoice
from edsl.study.ObjectEntry import ObjectEntry

question = QuestionMultipleChoice.example()


def test_ObjectEntry_initialization():
    oe = ObjectEntry("question", question, "This is a multiple-choice question")
    assert oe.variable_name == "question"
    assert oe.object == question
    assert oe.description == "This is a multiple-choice question"
    assert oe.edsl_class_name == question.__class__.__name__
    assert isinstance(oe.created_at, float)
    assert oe.coop_info is None


def test_ObjectEntry_to_dict():
    oe = ObjectEntry("question", question, "This is a multiple-choice question")
    oe_dict = oe.to_dict()
    assert oe_dict["variable_name"] == "question"
    assert oe_dict["object"] == question.to_dict()
    assert oe_dict["description"] == "This is a multiple-choice question"
    assert oe_dict["edsl_class_name"] == question.__class__.__name__
    assert isinstance(oe_dict["created_at"], float)
    assert oe_dict["coop_info"] is None


def test_ObjectEntry_from_dict():
    oe = ObjectEntry("question", question, "This is a multiple-choice question")
    oe_dict = oe.to_dict()
    new_oe = ObjectEntry.from_dict(oe_dict)
    assert new_oe.variable_name == oe.variable_name
    assert new_oe.object == oe.object
    assert new_oe.description == oe.description
    assert new_oe.edsl_class_name == oe.edsl_class_name
    assert new_oe.created_at == oe.created_at
    assert new_oe.coop_info == oe.coop_info


def test_ObjectEntry_hash_property():
    oe = ObjectEntry("question", question, "This is a multiple-choice question")
    obj_hash = hash(question)
    assert oe.hash == str(obj_hash)
