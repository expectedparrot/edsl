from edsl.jobs.task_management import InterviewStatusDictionary

from edsl.jobs.task_management import TaskStatus

def test_instantiation():
    i = InterviewStatusDictionary()
    assert i is not None

    for task in TaskStatus:
        assert task in i

    i1 = InterviewStatusDictionary()
    i2 = InterviewStatusDictionary()
    i3 = i1 + i2
    assert isinstance(i3, InterviewStatusDictionary)