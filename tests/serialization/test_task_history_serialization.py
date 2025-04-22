import pytest
from edsl import Model, QuestionMultipleChoice
from edsl.tasks import TaskHistory
from edsl.interviews.exception_tracking import InterviewExceptionCollection

def test_task_history_exception_serialization():
    """
    Test to verify that TaskHistory serialization and deserialization 
    properly handles exceptions.
    
    This test ensures that the fix for the 'dict' object has no attribute 'num_unfixed'
    bug is working correctly.
    """
    # Create a question and model that will produce validation errors
    q1 = QuestionMultipleChoice(
        question_name="q1",
        question_text="What is your favorite color?",
        question_options=["Red", "Blue", "Green", "Yellow"]
    )
    # Using a canned response that doesn't match the options to trigger validation error
    model = Model("test", canned_response={"q1": ["White", "Black"]})
    
    # Run the question (this will produce exceptions)
    res = q1.by(model).run(disable_remote_inference=True, cache=False, print_exceptions=False)
    
    # Verify we have exceptions
    assert res.has_unfixed_exceptions, "Test should have unfixed exceptions"
    
    # Convert to dictionary
    task_history_dict = res.task_history.to_dict()
    
    # This used to fail with AttributeError: 'dict' object has no attribute 'num_unfixed'
    # Now it should work with our fix
    t = TaskHistory.from_dict(task_history_dict)
    
    # Verify the deserialized object still has the exceptions
    assert t.has_unfixed_exceptions, "Deserialized task history should have unfixed exceptions"
    assert len(t.unfixed_exceptions) > 0, "Deserialized task history should have unfixed exceptions"
    
    # Verify exception structure
    first_interview = t.total_interviews[0]
    assert hasattr(first_interview.exceptions, "num_unfixed"), "Exceptions should have num_unfixed method"
    assert callable(first_interview.exceptions.num_unfixed), "num_unfixed should be callable"
    
    # Verify we can access unfixed_exceptions without AttributeError
    try:
        _ = t.unfixed_exceptions
    except AttributeError:
        pytest.fail("Accessing unfixed_exceptions raised AttributeError")
