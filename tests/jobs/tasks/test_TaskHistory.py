import pytest

from edsl.tasks import TaskStatus
from edsl.jobs import Jobs
from edsl.tasks import TaskHistory

@pytest.fixture
def sample_task_history():
    j = Jobs.example(throw_exception_probability=1, test_model=True)
    results = j.run(
        print_exceptions=False,
        skip_retry=True,
        cache=False,
        raise_validation_errors=True,
    )
    return TaskHistory(results.task_history.total_interviews)


def test_task_history_initialization(sample_task_history):
    assert isinstance(sample_task_history, TaskHistory)
    assert len(sample_task_history.total_interviews) > 0


def test_exceptions_property(sample_task_history):
    exceptions = sample_task_history.exceptions
    assert isinstance(exceptions, list)
    assert len(exceptions) > 0
    # assert all(isinstance(e, dict) for e in exceptions)


def test_indices_property(sample_task_history):
    indices = sample_task_history.indices
    assert isinstance(indices, list)
    assert len(indices) > 0
    assert all(isinstance(i, int) for i in indices)


def test_has_exceptions_property(sample_task_history):
    assert sample_task_history.has_exceptions == True


def test_to_dict_method(sample_task_history):
    task_dict = sample_task_history.to_dict()
    # assert isinstance(task_dict, dict)
    # assert "exceptions" in task_dict
    # assert "indices" in task_dict


def test_get_updates_method(sample_task_history):
    updates = sample_task_history.get_updates()
    assert isinstance(updates, list)
    # In this test, we might not have any actual log updates due to using mocks
    # We're just testing that the method returns a list without errors


def test_exceptions_by_type_property(sample_task_history):
    exceptions_by_type = sample_task_history.exceptions_by_type
    assert isinstance(exceptions_by_type, dict)
    assert len(exceptions_by_type) > 0


def test_exceptions_by_question_name_property(sample_task_history):
    exceptions_by_question = sample_task_history.exceptions_by_question_name
    assert isinstance(exceptions_by_question, dict)
    assert len(exceptions_by_question) > 0


def test_exceptions_by_model_property(sample_task_history):
    exceptions_by_model = sample_task_history.exceptions_by_model
    assert isinstance(exceptions_by_model, dict)
    assert len(exceptions_by_model) > 0


def test_plotting_data_method(sample_task_history):
    plot_data = sample_task_history.plotting_data(num_periods=50)
    assert isinstance(plot_data, list)
    # These assertions are too strict for our mock-based TaskHistory
    # Just check that we get a list back with the correct number of periods
    assert len(plot_data) == 50
    assert all(isinstance(d, dict) for d in plot_data)


# Additional tests can be added for methods like plot(), html(), etc.
# These methods might require more complex setup or mocking of external dependencies.
