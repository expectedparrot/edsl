"""Configuration endpoints for models, facts, and presets."""
from fastapi import APIRouter
from typing import List, Dict, Any

from backend.services.model_service import get_model_service

router = APIRouter()

@router.get("/models")
async def get_available_models() -> Dict[str, Any]:
    """Get list of available LLM models from EDSL.

    Returns models in multiple formats:
    - models: Flat list of all models with name and service
    - grouped: Models grouped by service provider
    - popular: Curated list of popular models
    - last_updated: ISO timestamp of when models were cached
    """
    service = get_model_service()
    return {
        "models": service.get_all_models(),
        "grouped": service.get_grouped_models(),
        "popular": service.get_popular_models(),
        "last_updated": service.get_cache_timestamp()
    }

@router.get("/facts")
async def get_fact_database() -> Dict[str, Any]:
    """Get the fact database with categories."""
    # TODO: Load from actual fact database JSON
    return {
        "total": 99,
        "categories": [
            "science", "history", "biology", "geography",
            "technology", "culture", "sports", "arts"
        ],
        "sample": [
            {
                "id": "fact_001",
                "category": "science",
                "statement": "The Eiffel Tower can be 15 cm taller during summer.",
                "veracity": True
            }
        ]
    }

@router.get("/presets")
async def get_presets() -> List[Dict[str, Any]]:
    """Get saved experiment presets."""
    # TODO: Load from file storage
    return [
        {
            "id": "preset_001",
            "name": "Quick Test",
            "config": {
                "gameType": "standard",
                "rounds": 5,
                "storytellerModel": "claude-sonnet-4-5-20250929",
                "judgeModel": "chatgpt-4o-latest"
            }
        }
    ]

@router.post("/presets")
async def save_preset(preset: Dict[str, Any]) -> Dict[str, str]:
    """Save a new experiment preset."""
    # TODO: Save to file storage
    return {"id": "preset_new", "status": "saved"}
