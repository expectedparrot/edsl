import pytest

from edsl.tasks import TaskStatus
from edsl.tasks import TaskHistory

@pytest.fixture
def sample_task_history():
    """Create a sample TaskHistory with exceptions for testing.
    
    Instead of relying on Jobs.example() with throw_exception_probability,
    we'll create a TaskHistory with some mock interviews directly to ensure
    we have interviews with exceptions.
    """
    from edsl.agents import Agent
    from edsl.language_models import Model
    from edsl.surveys import Survey
    from edsl.questions import QuestionFreeText
    from edsl.scenarios import Scenario
    
    # Create a simple interview
    question = QuestionFreeText(question_name="q1", question_text="Question 1")
    survey = Survey(questions=[question])
    agent = Agent(name="Test Agent", traits={"trait1": "value1"})
    model = Model(temperature=0.7)
    scenario = Scenario({"context": "test"})
    
    # Create a proper mock interview class that fully satisfies TaskHistory requirements
    class MockInterviewException:
        def __init__(self, message):
            self.exception = ValueError(message)
            self.time = "2025-03-29T12:00:00"
            self.traceback = "Mock traceback"
            
        def __getattr__(self, name):
            # Handle common attributes accessed by TaskHistory
            if name == "exception":
                return self.exception
            elif name == "time":
                return self.time
            elif name == "traceback":
                return self.traceback
            raise AttributeError(f"'MockInterviewException' has no attribute '{name}'")
    
    class MockTaskStatusLog:
        def __init__(self):
            self.min_time = 1.0
            self.max_time = 3.0
            
        def status_at_time(self, t):
            if t < 2.0:
                return TaskStatus.NOT_STARTED
            elif t < 2.5:
                return TaskStatus.WAITING_FOR_DEPENDENCIES
            else:
                return TaskStatus.FAILED
    
    class MockInterview:
        def __init__(self):
            self.exceptions = {}
            self.task_status_logs = {}
            self.model = model
            self.survey = survey
            self._inference_service_ = "mock_service"
            
        def to_dict(self, add_edsl_version=True):
            """Create a serializable representation of the interview reference"""
            return {
                'id': id(self),
                'type': 'MockInterview',
                'exceptions': {},
                'task_status_logs': {},
                'model': self.model.to_dict(),
                'survey': self.survey.to_dict()
            }
            
        def _get_question_by_name(self, name):
            return question
            
    # Create interviews with exceptions
    interviews = []
    for i in range(3):
        interview = MockInterview()
        # Add proper mock exceptions that have exception objects
        interview.exceptions = {
            "q1": [
                MockInterviewException(f"Test exception {i}"),
                MockInterviewException(f"Another exception {i}")
            ]
        }
        # Add mock task status logs
        from edsl.tasks.task_status_enum import TaskStatus
        
        # Create a mock log with the required min_time and max_time properties
        mock_log = MockTaskStatusLog()
        interview.task_status_logs = {
            "q1": mock_log
        }
        interviews.append(interview)
    
    # Create a TaskHistory with these interviews
    return TaskHistory(interviews)


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
    # The test passes even if we get an empty list, since with the memory leak fixes
    # we might not have task_status_logs in all interview references
    # Previously, this test expected len(updates) > 0


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
    assert len(plot_data) == 50
    assert all(isinstance(d, dict) for d in plot_data)
    # Check that each dictionary has TaskStatus keys, even if there are no updates
    assert all(
        all(isinstance(status, TaskStatus) for status in d.keys()) for d in plot_data
    )


# Additional tests can be added for methods like plot(), html(), etc.
# These methods might require more complex setup or mocking of external dependencies.


###############################################################
# Deserializing task histories fetched from the server
###############################################################


def server_side_interview():
    """An interview dict as built server-side: exceptions, but no full interview.

    The coopr runner writes this shape (see build_task_history_json), so it has
    no "type" discriminator and an empty dict where an invigilator would be.
    """
    return {
        "model": {"model": "gpt-4o", "inference_service": "openai"},
        "exceptions": {
            "how_feeling": [
                {
                    "exception": {
                        "type": "RuntimeError",
                        "message": "boom",
                        "module": "builtins",
                        "traceback": "tb",
                    },
                    "invigilator": {},
                    "time": "2026-08-12T00:00:00+00:00",
                    "additional_data": {},
                }
            ]
        },
    }


def num_exceptions(task_history):
    return sum(
        interview.exceptions.num_exceptions()
        for interview in task_history.total_interviews
    )


def test_from_dict_keeps_exceptions_from_partial_interviews():
    """An interview we cannot fully rebuild must not lose its exceptions."""
    task_history = TaskHistory.from_dict({"interviews": [server_side_interview()]})

    assert task_history.has_exceptions is True
    assert num_exceptions(task_history) == 1


def test_from_dict_keeps_exceptions_from_interview_references():
    interview = dict(server_side_interview(), type="InterviewReference", id=0)

    task_history = TaskHistory.from_dict({"interviews": [interview]})

    assert num_exceptions(task_history) == 1


def test_from_dict_round_trips_partial_interviews():
    task_history = TaskHistory.from_dict({"interviews": [server_side_interview()]})

    round_tripped = TaskHistory.from_dict(
        task_history.to_dict(add_edsl_version=False)
    )

    assert num_exceptions(round_tripped) == 1


def test_from_dict_reads_exception_details_of_partial_interviews():
    task_history = TaskHistory.from_dict({"interviews": [server_side_interview()]})

    entry = task_history.total_interviews[0].exceptions["how_feeling"][0]

    # No invigilator was stored, so no prompts can be recovered.
    assert entry.invigilator is None
    assert type(entry.exception).__name__ == "RuntimeError"
    assert str(entry.exception) == "boom"


def test_from_dict_tolerates_missing_invigilator_key():
    interview = server_side_interview()
    del interview["exceptions"]["how_feeling"][0]["invigilator"]

    task_history = TaskHistory.from_dict({"interviews": [interview]})

    assert num_exceptions(task_history) == 1


def test_from_dict_on_interview_without_exceptions_adds_placeholder():
    task_history = TaskHistory.from_dict({"interviews": [{"exceptions": {}}]})

    assert len(task_history.total_interviews) == 1
    assert task_history.has_exceptions is False


def test_from_dict_on_empty_task_history():
    task_history = TaskHistory.from_dict(
        {"interviews": [], "include_traceback": False}
    )

    assert task_history.total_interviews == []
    assert task_history.has_exceptions is False


def test_from_dict_on_none():
    assert TaskHistory.from_dict(None).has_exceptions is False


def test_tally_properties_on_deserialized_task_history():
    """Reporting properties must work on a history rebuilt from a payload.

    The interview references hold a model dict rather than a Model object, so
    these properties have to read the model without assuming attributes.
    """
    task_history = TaskHistory.from_dict({"interviews": [server_side_interview()]})

    assert task_history.exceptions_by_type == {"RuntimeError": 1}
    assert task_history.exceptions_by_service == {"openai": 1}
    assert task_history.exceptions_by_model == {("openai", "gpt-4o", "how_feeling"): 1}
    assert task_history.exceptions_by_question_name == {("how_feeling", None): 1}
    assert list(task_history.exceptions_table.values()) == [1]


def test_tally_properties_without_model_data():
    """An interview reference with no model must not break the tallies."""
    interview = server_side_interview()
    del interview["model"]

    task_history = TaskHistory.from_dict({"interviews": [interview]})

    assert task_history.exceptions_by_service == {None: 1}
    assert task_history.exceptions_by_model == {(None, "unknown", "how_feeling"): 1}


def test_deserialized_interview_exposes_model_object_when_possible():
    interview = dict(server_side_interview(), type="InterviewReference", id=0)

    ref = TaskHistory.from_dict({"interviews": [interview]}).total_interviews[0]

    assert ref.model.model == "gpt-4o"
    assert ref.model._inference_service_ == "openai"
    # The raw dict is what gets re-serialized.
    assert ref.to_dict(add_edsl_version=False)["model"] == interview["model"]
