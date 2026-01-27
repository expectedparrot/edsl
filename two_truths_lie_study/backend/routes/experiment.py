"""Experiment execution endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime

router = APIRouter()

# Pydantic models for request/response validation
class ExperimentConfig(BaseModel):
    gameType: str
    rounds: int
    wordCountMin: int
    wordCountMax: int
    storytellerModel: str
    judgeModel: str
    storytellerTemp: float
    judgeTemp: float
    storytellerStrategy: str
    judgeStrategy: str
    factCategories: list[str]

class ExperimentStart(BaseModel):
    config: ExperimentConfig

# In-memory storage for active experiments (replace with persistent storage later)
active_experiments: Dict[str, Dict[str, Any]] = {}

@router.post("/start")
async def start_experiment(request: ExperimentStart) -> Dict[str, Any]:
    """
    Start a new experiment with the given configuration.
    Returns experiment ID and initial status.
    """
    # Generate experiment ID
    exp_id = f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Store experiment config
    active_experiments[exp_id] = {
        "id": exp_id,
        "config": request.config.model_dump(),
        "status": "starting",
        "current_round": 0,
        "total_rounds": request.config.rounds,
        "created_at": datetime.now().isoformat()
    }

    # TODO: Actually start the experiment using GameEngine
    # from adapters.game_runner import run_experiment
    # run_experiment(exp_id, request.config)

    return {
        "experiment_id": exp_id,
        "status": "started",
        "message": "Experiment initialized successfully"
    }

@router.get("/status/{experiment_id}")
async def get_experiment_status(experiment_id: str) -> Dict[str, Any]:
    """Get current status of a running experiment."""
    if experiment_id not in active_experiments:
        raise HTTPException(status_code=404, detail="Experiment not found")

    return active_experiments[experiment_id]

@router.post("/stop/{experiment_id}")
async def stop_experiment(experiment_id: str) -> Dict[str, str]:
    """Stop a running experiment."""
    if experiment_id not in active_experiments:
        raise HTTPException(status_code=404, detail="Experiment not found")

    active_experiments[experiment_id]["status"] = "stopped"

    return {
        "experiment_id": experiment_id,
        "status": "stopped"
    }

@router.get("/results/{experiment_id}")
async def get_experiment_results(experiment_id: str) -> Dict[str, Any]:
    """Get results of a completed experiment."""
    # TODO: Load from ResultStore
    return {
        "experiment_id": experiment_id,
        "rounds": [],
        "metrics": {
            "accuracy": 0.85,
            "avg_confidence": 0.78
        }
    }

@router.get("/list")
async def list_experiments(
    limit: int = 10,
    offset: int = 0
) -> Dict[str, Any]:
    """List all experiments with pagination."""
    # TODO: Load from ResultStore with filtering
    return {
        "total": len(active_experiments),
        "experiments": list(active_experiments.values())[offset:offset+limit]
    }
