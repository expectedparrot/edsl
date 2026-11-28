from edsl.runner.executor import ExecutionResult
from edsl.runner.serialization import (
    deserialize_execution_result,
    serialize_execution_result,
)


def test_execution_result_serialization_preserves_answer_source():
    result = ExecutionResult(
        task_id="task-1",
        job_id="job-1",
        interview_id="interview-1",
        success=True,
        answer=42,
        answer_source="repaired",
    )

    serialized = serialize_execution_result(result)
    deserialized = deserialize_execution_result(serialized)

    assert deserialized["answer_source"] == "repaired"
