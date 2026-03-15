"""
Serialization utilities for EDSL objects.

Handles conversion between EDSL objects (Job, Results, etc.) and JSON
for HTTP transport between client and cloud API.
"""

import json
import base64
import time
import logging
from typing import Any

logger = logging.getLogger(__name__)

# EDSL imports - relative since this module lives inside edsl package
from ..surveys import Survey
from ..scenarios import Scenario
from ..agents import Agent
from ..language_models import LanguageModel
from ..results import Results


class SerializationError(Exception):
    """Error during serialization or deserialization."""

    pass


# =============================================================================
# Job Serialization
# =============================================================================


def serialize_job(job: Any) -> dict:
    """
    Serialize an EDSL Job to a dictionary for JSON transport.

    The Job is decomposed into its constituent parts:
    - survey
    - scenarios
    - agents
    - models

    Args:
        job: EDSL Job object

    Returns:
        Dictionary that can be JSON-encoded
    """
    try:
        # Prepare the job - fills in defaults
        job.replace_missing_objects()

        # Extract components
        survey = job.survey if hasattr(job, "survey") else job._survey
        scenarios = list(job.scenarios)
        agents = list(job.agents)
        models = list(job.models)

        return {
            "_type": "Job",
            "_version": "1.0",
            "survey": _to_dict(survey),
            "scenarios": [_to_dict(s) for s in scenarios],
            "agents": [_to_dict(a) for a in agents],
            "models": [_to_dict(m) for m in models],
        }
    except Exception as e:
        raise SerializationError(f"Failed to serialize job: {e}") from e


def deserialize_job(data: dict) -> Any:
    """
    Deserialize a dictionary back to an EDSL Job.

    Args:
        data: Dictionary from JSON

    Returns:
        EDSL Job object
    """
    try:
        t0 = time.time()
        if data.get("_type") != "Job":
            raise SerializationError(f"Expected Job type, got {data.get('_type')}")

        # Count items for logging
        n_questions = len(data.get("survey", {}).get("questions", []))
        n_scenarios = len(data.get("scenarios", []))
        n_agents = len(data.get("agents", []))
        n_models = len(data.get("models", []))
        logger.info(
            f"[DESER] Starting: {n_questions} questions, {n_scenarios} scenarios, {n_agents} agents, {n_models} models"
        )

        # Deserialize components with timing
        t1 = time.time()
        survey = Survey.from_dict(data["survey"])
        t2 = time.time()
        logger.info(f"[DESER] Survey.from_dict: {(t2-t1)*1000:.1f}ms")

        scenarios = [Scenario.from_dict(s) for s in data.get("scenarios", [])]
        t3 = time.time()
        logger.info(f"[DESER] Scenarios ({n_scenarios}): {(t3-t2)*1000:.1f}ms")

        agents = [Agent.from_dict(a) for a in data.get("agents", [])]
        t4 = time.time()
        logger.info(f"[DESER] Agents ({n_agents}): {(t4-t3)*1000:.1f}ms")

        models = [_deserialize_model(m) for m in data.get("models", [])]
        t5 = time.time()
        logger.info(f"[DESER] Models ({n_models}): {(t5-t4)*1000:.1f}ms")

        # Reconstruct job
        job = survey.to_jobs()
        t6 = time.time()
        logger.info(f"[DESER] survey.to_jobs(): {(t6-t5)*1000:.1f}ms")

        if scenarios:
            job = job.by(*scenarios) if len(scenarios) > 1 else job.by(scenarios[0])
        t7 = time.time()
        if scenarios:
            logger.info(f"[DESER] job.by(scenarios): {(t7-t6)*1000:.1f}ms")

        if agents:
            job = job.by(*agents) if len(agents) > 1 else job.by(agents[0])
        t8 = time.time()
        if agents:
            logger.info(f"[DESER] job.by(agents): {(t8-t7)*1000:.1f}ms")

        if models:
            job = job.by(*models) if len(models) > 1 else job.by(models[0])
        t9 = time.time()
        if models:
            logger.info(f"[DESER] job.by(models): {(t9-t8)*1000:.1f}ms")

        total_ms = (t9 - t0) * 1000
        logger.info(f"[DESER] TOTAL deserialize_job: {total_ms:.1f}ms")

        return job
    except SerializationError:
        raise
    except Exception as e:
        raise SerializationError(f"Failed to deserialize job: {e}") from e


# =============================================================================
# Results Serialization
# =============================================================================


def serialize_results(results: Any) -> dict:
    """
    Serialize EDSL Results to a dictionary for JSON transport.

    Args:
        results: EDSL Results object

    Returns:
        Dictionary that can be JSON-encoded
    """
    try:
        # Results have a to_dict method
        if hasattr(results, "to_dict"):
            return {
                "_type": "Results",
                "_version": "1.0",
                "data": results.to_dict(),
            }

        # Fallback: serialize individual results
        result_list = []
        for result in results:
            if hasattr(result, "to_dict"):
                result_list.append(result.to_dict())
            else:
                result_list.append(_to_dict(result))

        return {
            "_type": "Results",
            "_version": "1.0",
            "results": result_list,
        }
    except Exception as e:
        raise SerializationError(f"Failed to serialize results: {e}") from e


def deserialize_results(data: dict) -> Any:
    """
    Deserialize a dictionary back to EDSL Results.

    Args:
        data: Dictionary from JSON

    Returns:
        EDSL Results object
    """
    try:
        if data.get("_type") != "Results":
            raise SerializationError(f"Expected Results type, got {data.get('_type')}")

        # Try to use from_dict if available
        if "data" in data and hasattr(Results, "from_dict"):
            return Results.from_dict(data["data"])

        # Fallback: construct from result list
        if "results" in data:
            return Results.from_dict({"data": data["results"]})

        raise SerializationError("Results data not found in payload")
    except SerializationError:
        raise
    except Exception as e:
        raise SerializationError(f"Failed to deserialize results: {e}") from e


# =============================================================================
# Progress Serialization
# =============================================================================


def serialize_progress(progress: dict) -> dict:
    """
    Serialize job progress to a dictionary.

    Progress is already a dict, but we add type info for consistency.

    Args:
        progress: Progress dictionary from JobService

    Returns:
        Dictionary that can be JSON-encoded
    """
    return {
        "_type": "Progress",
        "_version": "1.0",
        **progress,
    }


def deserialize_progress(data: dict) -> dict:
    """
    Deserialize progress dictionary.

    Args:
        data: Dictionary from JSON

    Returns:
        Progress dictionary
    """
    # Remove type metadata and return progress data
    result = dict(data)
    result.pop("_type", None)
    result.pop("_version", None)
    return result


# =============================================================================
# Job Submission Request/Response
# =============================================================================


def serialize_submit_request(
    job: Any,
    user_id: str = "anonymous",
    n: int = 1,
    cache: bool = True,
    stop_on_exception: bool = False,
    mock_llm: bool = None,
) -> dict:
    """
    Serialize a job submission request.

    Args:
        job: EDSL Job object
        user_id: User identifier
        n: Number of iterations
        cache: Whether to use caching
        stop_on_exception: Whether to stop on first exception
        mock_llm: If True, use mock LLM responses. If False, use real LLM.
                  If None, use server default.

    Returns:
        Dictionary for JSON transport
    """
    result = {
        "_type": "SubmitRequest",
        "_version": "1.0",
        "job": serialize_job(job),
        "user_id": user_id,
        "n": n,
        "cache": cache,
        "stop_on_exception": stop_on_exception,
    }
    # Only include mock_llm if explicitly set (not None)
    if mock_llm is not None:
        result["mock_llm"] = mock_llm
    return result


def deserialize_submit_request(data: dict) -> dict:
    """
    Deserialize a job submission request.

    Args:
        data: Dictionary from JSON

    Returns:
        Dictionary with deserialized job and options
    """
    if data.get("_type") != "SubmitRequest":
        raise SerializationError(
            f"Expected SubmitRequest type, got {data.get('_type')}"
        )

    result = {
        "job": deserialize_job(data["job"]),
        "user_id": data.get("user_id", "anonymous"),
        "n": data.get("n", 1),
        "cache": data.get("cache", True),
        "stop_on_exception": data.get("stop_on_exception", False),
    }
    # Only include mock_llm if present in the request
    if "mock_llm" in data:
        result["mock_llm"] = data["mock_llm"]
    return result


def serialize_submit_response(job_id: str) -> dict:
    """
    Serialize a job submission response.

    Args:
        job_id: The assigned job ID

    Returns:
        Dictionary for JSON transport
    """
    return {
        "_type": "SubmitResponse",
        "_version": "1.0",
        "job_id": job_id,
    }


def deserialize_submit_response(data: dict) -> str:
    """
    Deserialize a job submission response.

    Args:
        data: Dictionary from JSON

    Returns:
        Job ID
    """
    if data.get("_type") != "SubmitResponse":
        raise SerializationError(
            f"Expected SubmitResponse type, got {data.get('_type')}"
        )

    return data["job_id"]


# =============================================================================
# Task Serialization (for worker)
# =============================================================================


def serialize_task(rendered_prompt: Any) -> dict:
    """
    Serialize a RenderedPrompt for worker execution.

    Args:
        rendered_prompt: RenderedPrompt dataclass

    Returns:
        Dictionary for JSON transport
    """
    from .render import RenderedPrompt

    if isinstance(rendered_prompt, RenderedPrompt):
        return {
            "_type": "Task",
            "_version": "1.0",
            "task_id": rendered_prompt.task_id,
            "job_id": rendered_prompt.job_id,
            "interview_id": rendered_prompt.interview_id,
            "question_name": rendered_prompt.question_name,
            "system_prompt": rendered_prompt.system_prompt,
            "user_prompt": rendered_prompt.user_prompt,
            "model_id": rendered_prompt.model_id,
            "service_name": rendered_prompt.service_name,
            "model_name": rendered_prompt.model_name,
            "estimated_tokens": rendered_prompt.estimated_tokens,
            "cache_key": rendered_prompt.cache_key,
            "files_list": rendered_prompt.files_list,
            "iteration": rendered_prompt.iteration,
        }

    # If it's already a dict, wrap it
    if isinstance(rendered_prompt, dict):
        return {
            "_type": "Task",
            "_version": "1.0",
            **rendered_prompt,
        }

    raise SerializationError(f"Cannot serialize task of type {type(rendered_prompt)}")


def deserialize_task(data: dict) -> dict:
    """
    Deserialize a task for worker execution.

    Returns a dictionary rather than RenderedPrompt to avoid import issues.
    The worker can construct RenderedPrompt if needed.

    Args:
        data: Dictionary from JSON

    Returns:
        Task dictionary
    """
    if data.get("_type") != "Task":
        raise SerializationError(f"Expected Task type, got {data.get('_type')}")

    # Remove type metadata and return task data
    result = dict(data)
    result.pop("_type", None)
    result.pop("_version", None)
    return result


# =============================================================================
# Execution Result Serialization
# =============================================================================


def serialize_execution_result(result: Any) -> dict:
    """
    Serialize an ExecutionResult from worker.

    Args:
        result: ExecutionResult dataclass

    Returns:
        Dictionary for JSON transport
    """
    from .executor import ExecutionResult

    if isinstance(result, ExecutionResult):
        return {
            "_type": "ExecutionResult",
            "_version": "1.0",
            "task_id": result.task_id,
            "job_id": result.job_id,
            "interview_id": result.interview_id,
            "success": result.success,
            "answer": result.answer,
            "comment": result.comment,
            "system_prompt": result.system_prompt,
            "user_prompt": result.user_prompt,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "raw_model_response": result.raw_model_response,
            "generated_tokens": result.generated_tokens,
            "cached": result.cached,
            "error_type": result.error_type,
            "error_message": result.error_message,
        }

    if isinstance(result, dict):
        return {
            "_type": "ExecutionResult",
            "_version": "1.0",
            **result,
        }

    raise SerializationError(f"Cannot serialize result of type {type(result)}")


def deserialize_execution_result(data: dict) -> dict:
    """
    Deserialize an execution result.

    Args:
        data: Dictionary from JSON

    Returns:
        Result dictionary
    """
    if data.get("_type") != "ExecutionResult":
        raise SerializationError(
            f"Expected ExecutionResult type, got {data.get('_type')}"
        )

    result = dict(data)
    result.pop("_type", None)
    result.pop("_version", None)
    return result


# =============================================================================
# Helper Functions
# =============================================================================


def _to_dict(obj: Any) -> dict:
    """Convert an object to a dict for serialization."""
    if obj is None:
        return None
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if isinstance(obj, dict):
        return obj
    # Fallback
    return {"_repr": repr(obj), "_type": type(obj).__name__}


def _deserialize_model(data: dict) -> Any:
    """Deserialize a model dict to an EDSL Model."""
    if data is None:
        return None

    return LanguageModel.from_dict(data)


# =============================================================================
# JSON Helpers
# =============================================================================


def to_json(obj: Any) -> str:
    """
    Convert a serialized object to JSON string.

    Args:
        obj: Dictionary to serialize

    Returns:
        JSON string
    """
    return json.dumps(obj, default=_json_default)


def from_json(json_str: str) -> dict:
    """
    Parse a JSON string to dictionary.

    Args:
        json_str: JSON string

    Returns:
        Dictionary
    """
    return json.loads(json_str)


def _json_default(obj: Any) -> Any:
    """Default JSON encoder for non-standard types."""
    if isinstance(obj, bytes):
        return base64.b64encode(obj).decode("utf-8")
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
