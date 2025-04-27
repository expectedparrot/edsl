from fastapi import APIRouter, HTTPException

router = APIRouter()

@router.get("/hello")
async def hello():
    """A simple example endpoint for the example variant"""
    return {"message": "Hello from the example variant!"}

@router.get("/items")
async def get_items():
    """Return a list of example items"""
    return {"items": [
        {"id": 1, "name": "Example Item 1"},
        {"id": 2, "name": "Example Item 2"},
        {"id": 3, "name": "Example Item 3"}
    ]}