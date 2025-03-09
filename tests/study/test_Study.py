import pytest
from uuid import UUID

from edsl.study import Study
from edsl.questions import QuestionFreeText, QuestionMultipleChoice

def test_instantiate():
    s = Study.example()
    new_study = Study.from_dict(s.to_dict())
    assert s == new_study


def test_exception_non_empty_namespace():
    with pytest.raises(ValueError):
        q = QuestionFreeText.example()
        with Study() as study:
            pass


def test_record_objects():
    import tempfile

    f = tempfile.NamedTemporaryFile()
    with Study(filename=f.name) as study:
        q = QuestionFreeText.example()

    assert len(study) == 1

    assert type(study.q) == type(q)

    assert study.name_to_object["q"] == q

    assert study.name_to_object["q"].question_name == q.question_name

    new_study = Study.from_dict(study.to_dict())
    assert new_study == study


def test_equality():
    import tempfile

    f1 = tempfile.NamedTemporaryFile()
    f2 = tempfile.NamedTemporaryFile()
    f3 = tempfile.NamedTemporaryFile()

    with Study(filename=f1.name) as study1:
        q = QuestionFreeText.example()

    # breakpoint()

    del q

    with Study(filename=f2.name) as study2:
        q = QuestionFreeText.example()

    del q

    assert study1 == study2

    with Study(filename=f3.name) as study3:
        q = QuestionMultipleChoice.example()

    assert study1 == study2
    assert study1 != study3

    assert hash(study1) == hash(study2)


def test_versions():
    import tempfile

    f1 = tempfile.NamedTemporaryFile()

    with Study(filename=f1.name) as study1:
        q = QuestionFreeText.example()

    del q

    with Study(filename=f1.name) as study2:
        q = QuestionMultipleChoice.example()

    assert len(study2.versions()["q"]) == 2

    del q


def test_delete_object():
    import tempfile

    f = tempfile.NamedTemporaryFile()

    with Study(filename=f.name, verbose=False) as study:
        q1 = QuestionFreeText.example()
        q2 = QuestionMultipleChoice.example()

    assert len(study) == 2

    # Test deleting by variable name
    study.delete_object("q1")
    assert len(study) == 1
    assert "q1" not in study.name_to_object
    assert "q2" in study.name_to_object

    # Test deleting by hash
    q2_hash = next(iter(study.objects.keys()))
    study.delete_object(q2_hash)  # Pass the hash string directly
    assert len(study) == 0

    # Test deleting non-existent object
    with pytest.raises(ValueError):
        study.delete_object("non_existent")

    with pytest.raises(ValueError):
        study.delete_object("00000000-0000-0000-0000-000000000000")  # Use a string UUID

    # Test with invalid identifier type
    with pytest.raises(TypeError):
        study.delete_object(123)
