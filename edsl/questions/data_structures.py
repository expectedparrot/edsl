from typing import Any, Optional, TypedDict
from pydantic import BaseModel


class RawEdslAnswerDict(TypedDict):
    answer: Any
    comment: Optional[str]
    generated_tokens: Optional[str]


class BaseResponse(BaseModel):
    answer: Any
    comment: Optional[str] = None
    generated_tokens: Optional[str] = None


class EdslAnswerDict(TypedDict):
    answer: Any
    comment: Optional[str]
    generated_tokens: Optional[str]
