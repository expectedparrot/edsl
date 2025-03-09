import pytest

from edsl.jobs.interviews.interview_status_dictionary import InterviewStatusDictionary
from edsl.jobs.tasks.task_status_enum import TaskStatus, TaskStatusDescriptor


def test_instantiation():
    i = InterviewStatusDictionary()
    assert i is not None

    for task in TaskStatus:
        assert task in i

    i1 = InterviewStatusDictionary()
    i2 = InterviewStatusDictionary()
    i3 = i1 + i2
    assert isinstance(i3, InterviewStatusDictionary)


def test_check_enum():
    data = {task_status: 0 for task_status in TaskStatus}
    data["number_from_cache"] = 0
    i = InterviewStatusDictionary(data=data)

    # expect an assertion error
    with pytest.raises(AssertionError):
        data = {task_status: 0 for task_status in TaskStatus}
        import random

        to_delete = random.choice(list(TaskStatus))
        data.pop(to_delete)
        i = InterviewStatusDictionary(data=data)


def test_check_descriptor():
    class FakeClass:
        task = TaskStatusDescriptor()

    a = FakeClass()
    a.task = TaskStatus.API_CALL_IN_PROGRESS

    # can't assign a status that's not from the TaskStatus enum
    with pytest.raises(ValueError):
        b = FakeClass()
        b.task = "poo"


def test_serialization():
    data = {task_status: 0 for task_status in TaskStatus}
    data["number_from_cache"] = 0
    i = InterviewStatusDictionary(data=data)

    d = i.to_dict()
    i2 = InterviewStatusDictionary.from_dict(d)

    assert i == i2
    assert i is not i2
