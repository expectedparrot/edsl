from pydantic import BaseModel
from typing import Any


class LLMResponse(BaseModel):
    """Pydantic data model for the LLM response."""

    answer: Any
