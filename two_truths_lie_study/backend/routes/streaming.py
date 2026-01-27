"""Server-Sent Events streaming for live experiment updates."""
from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
from typing import AsyncGenerator

router = APIRouter()

async def experiment_event_generator(experiment_id: str) -> AsyncGenerator[dict, None]:
    """
    Generate Server-Sent Events for experiment progress.
    Yields events as the experiment runs.
    """
    # TODO: Connect to actual GameEngine events
    # For now, simulate events for demonstration

    # Simulate experiment phases
    phases = [
        {"phase": "story", "message": "Generating stories..."},
        {"phase": "questions", "message": "Judge asking questions..."},
        {"phase": "verdict", "message": "Judge making decision..."},
        {"phase": "complete", "message": "Round complete"}
    ]

    for i, phase_info in enumerate(phases):
        await asyncio.sleep(2)  # Simulate processing time

        event_data = {
            "experiment_id": experiment_id,
            "round": 1,
            "phase": phase_info["phase"],
            "message": phase_info["message"],
            "timestamp": asyncio.get_event_loop().time()
        }

        yield {
            "event": "experiment_update",
            "data": json.dumps(event_data)
        }

    # Final event
    yield {
        "event": "experiment_complete",
        "data": json.dumps({
            "experiment_id": experiment_id,
            "status": "completed"
        })
    }

@router.get("/{experiment_id}")
async def stream_experiment(experiment_id: str):
    """
    Stream live updates for an experiment using Server-Sent Events.
    Connect to this endpoint from the frontend to receive real-time updates.
    """
    # TODO: Verify experiment exists
    # if experiment_id not in active_experiments:
    #     raise HTTPException(status_code=404, detail="Experiment not found")

    return EventSourceResponse(experiment_event_generator(experiment_id))
